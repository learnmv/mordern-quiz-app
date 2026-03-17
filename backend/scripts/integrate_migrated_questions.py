#!/usr/bin/env python3
"""
Integration script to add migrated diagram questions to modern-quiz-app PostgreSQL database.

This script reads the migrated questions from quiz-app and inserts them into
the mordern-quiz-app PostgreSQL database with the proper format.
"""

import asyncio
import json
import sys
import hashlib
from datetime import date
from typing import List, Dict, Any

# Add parent directory to path for imports
sys.path.insert(0, '/home/sysadmin/mordern-quiz-app/backend')

from sqlalchemy import select, and_
from app.database import AsyncSessionLocal
from app.models.quiz import TopicQuestion

# Import migrated questions from quiz-app
sys.path.insert(0, '/home/sysadmin/quiz-app')
from question_migration import migrated_questions


def generate_question_hash(question_text: str) -> str:
    """Generate a hash for question repeat detection"""
    return hashlib.md5(question_text.encode()).hexdigest()[:16]


def convert_to_modern_format(migrated_q: Dict[str, Any]) -> Dict[str, Any]:
    """Convert migrated question format to modern-quiz-app format."""

    # Generate hash
    q_hash = migrated_q.get('hash') or generate_question_hash(migrated_q['question_text'])

    # Build the question in modern format
    modern_q = {
        "text": migrated_q['question_text'],
        "type": "diagram",  # New type for diagram-based questions
        "question_type": migrated_q['question_type'],  # Specific diagram type
        "answer": str(migrated_q['answer']),
        "answer_unit": migrated_q.get('answer_unit', ''),
        "explanation": migrated_q['explanation'],
        "difficulty": migrated_q['difficulty'],
        "grade": str(migrated_q['grade_level']),
        "topic": migrated_q['topic'],
        "sub_topic": migrated_q.get('sub_topic', ''),
        "hash": q_hash,
        "requires_canvas": True,
    }

    # Add diagram data if present
    if 'diagram_data' in migrated_q:
        modern_q['diagram'] = migrated_q['diagram_data']

    return modern_q


async def clear_old_diagram_questions(session, topics: List[str]):
    """Remove old diagram questions from specified topics."""
    result = await session.execute(
        select(TopicQuestion).where(TopicQuestion.topic.in_(topics))
    )
    rows = result.scalars().all()

    deleted_count = 0
    for row in rows:
        await session.delete(row)
        deleted_count += 1

    await session.commit()
    print(f"Cleared {deleted_count} old diagram topic entries")
    return deleted_count


async def insert_migrated_questions(session):
    """Insert migrated questions into the database."""

    today = date.today()
    inserted_count = 0

    # Group questions by grade, topic, difficulty
    grouped = {}
    for mq in migrated_questions:
        grade = str(mq['grade_level'])
        topic = mq['topic']
        difficulty = mq['difficulty']

        key = (grade, topic, difficulty)
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(mq)

    # Insert each group
    for (grade, topic, difficulty), questions in grouped.items():
        # Convert all questions in this group
        modern_questions = [convert_to_modern_format(q) for q in questions]

        # Check if entry exists for today
        result = await session.execute(
            select(TopicQuestion).where(
                and_(
                    TopicQuestion.grade == grade,
                    TopicQuestion.topic == topic,
                    TopicQuestion.difficulty == difficulty,
                    TopicQuestion.created_date == today
                )
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            # Append to existing questions
            existing_data = existing.question_data
            existing_questions = existing_data.get('questions', [])

            # Check for duplicates by hash
            existing_hashes = {q.get('hash') for q in existing_questions}
            new_questions = [q for q in modern_questions if q.get('hash') not in existing_hashes]

            if new_questions:
                existing_questions.extend(new_questions)
                existing.question_data = {'questions': existing_questions}
                print(f"Appended {len(new_questions)} questions to {topic} ({grade}, {difficulty})")
                inserted_count += len(new_questions)
        else:
            # Create new entry
            new_entry = TopicQuestion(
                grade=grade,
                topic=topic,
                difficulty=difficulty,
                question_data={'questions': modern_questions},
                created_date=today
            )
            session.add(new_entry)
            print(f"Created new entry for {topic} ({grade}, {difficulty}) with {len(modern_questions)} questions")
            inserted_count += len(modern_questions)

    await session.commit()
    return inserted_count


async def verify_integration(session):
    """Verify the integration was successful."""

    # Count total questions
    result = await session.execute(select(TopicQuestion))
    all_entries = result.scalars().all()

    total_questions = 0
    diagram_questions = 0
    topic_counts = {}

    for entry in all_entries:
        questions = entry.question_data.get('questions', [])
        total_questions += len(questions)

        for q in questions:
            q_type = q.get('question_type') or q.get('type', '')
            if q_type in ['bar_chart', 'line_graph', 'pie_chart', 'coordinate_plane', 'geometric_shape', 'diagram']:
                diagram_questions += 1
                topic_counts[entry.topic] = topic_counts.get(entry.topic, 0) + 1

    print("\n" + "=" * 60)
    print("VERIFICATION")
    print("=" * 60)
    print(f"Total topic entries: {len(all_entries)}")
    print(f"Total questions: {total_questions}")
    print(f"Diagram questions: {diagram_questions}")
    print(f"Topics with diagram questions: {list(topic_counts.keys())}")
    print("=" * 60)

    return diagram_questions


async def main():
    """Main integration function."""

    print("=" * 60)
    print("INTEGRATING MIGRATED QUESTIONS TO MODERN-QUIZ-APP")
    print("=" * 60)

    async with AsyncSessionLocal() as session:
        try:
            # Step 1: Clear old diagram questions
            print("\nStep 1: Clearing old diagram questions...")
            diagram_topics = ['data_analysis', 'geometry']
            await clear_old_diagram_questions(session, diagram_topics)

            # Step 2: Insert migrated questions
            print("\nStep 2: Inserting migrated questions...")
            inserted = await insert_migrated_questions(session)
            print(f"Inserted {inserted} migrated questions")

            # Step 3: Verify
            print("\nStep 3: Verifying integration...")
            await verify_integration(session)

            print("\n" + "=" * 60)
            print("INTEGRATION COMPLETE")
            print("=" * 60)

        except Exception as e:
            print(f"Error: {e}")
            await session.rollback()
            raise


if __name__ == '__main__':
    asyncio.run(main())
