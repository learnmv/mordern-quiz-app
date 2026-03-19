#!/usr/bin/env python3
"""Pre-generate questions for all grade/topic/difficulty combinations."""
import asyncio
import argparse
import logging
from datetime import date
from typing import List, Dict, Any, Optional

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.database import AsyncSessionLocal
from app.services.quiz_generator import (
    generate_quiz_with_ollama,
    generate_diagram_quiz,
    store_question,
    ALL_TOPICS,
)

# Diagram topics that require visual representation
DIAGRAM_TOPICS = [
    "Area of Polygons", "Volume of Prisms", "Surface Area",
    "Coordinate Plane", "Coordinate Plane Polygons", "Number Line",
    "Dot Plots", "Histograms", "Box Plots"
]
from app.models.quiz import TopicQuestion

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

ALLOWED_GRADES = ["6", "7", "8"]
ALLOWED_DIFFICULTIES = ["easy", "medium", "hard"]
QUESTIONS_PER_COMBINATION = 5


async def get_existing_question_count(
    db,
    grade: str,
    topic: str,
    difficulty: str
) -> int:
    """Get count of existing questions for a combination."""
    from sqlalchemy import select, func, and_

    result = await db.execute(
        select(TopicQuestion).where(
            and_(
                TopicQuestion.grade == grade,
                TopicQuestion.topic == topic,
                TopicQuestion.difficulty == difficulty
            )
        )
    )
    rows = result.scalars().all()

    total = 0
    for row in rows:
        questions = row.question_data.get('questions', [])
        total += len(questions)

    return total


async def pregenerate_questions(
    grades: Optional[List[str]] = None,
    topics: Optional[List[str]] = None,
    difficulties: Optional[List[str]] = None,
    count_per_combo: int = 10,
    dry_run: bool = False,
    skip_existing: bool = True
):
    """Pre-generate questions for specified combinations.

    Args:
        grades: List of grades to generate for (default: all)
        topics: List of topics to generate for (default: all)
        difficulties: List of difficulties (default: all)
        count_per_combo: Number of questions per combination
        dry_run: If True, don't actually store questions
        skip_existing: If True, skip combinations that already have enough questions
    """
    grades = grades or ALLOWED_GRADES
    topics = topics or ALL_TOPICS
    difficulties = difficulties or ALLOWED_DIFFICULTIES

    total_combinations = len(grades) * len(topics) * len(difficulties)
    total_questions = total_combinations * count_per_combo

    print(f"Pre-generating questions...")
    print(f"  Grades: {grades}")
    print(f"  Topics: {len(topics)} topics")
    print(f"  Difficulties: {difficulties}")
    print(f"  Questions per combination: {count_per_combo}")
    print(f"  Total combinations: {total_combinations}")
    print(f"  Total questions (if all generated): {total_questions}")
    print(f"  Dry run: {dry_run}")
    print(f"  Skip existing: {skip_existing}")
    print()

    async with AsyncSessionLocal() as db:
        generated_count = 0
        failed_count = 0
        skipped_count = 0
        processed_count = 0

        for grade in grades:
            for topic in topics:
                for difficulty in difficulties:
                    processed_count += 1

                    # Check existing questions if skip_existing
                    if skip_existing and not dry_run:
                        existing = await get_existing_question_count(db, grade, topic, difficulty)
                        if existing >= count_per_combo:
                            print(f"[{processed_count}/{total_combinations}] Skipping {grade}/{topic}/{difficulty} - already has {existing} questions")
                            skipped_count += 1
                            continue

                    print(f"[{processed_count}/{total_combinations}] Generating {count_per_combo} questions for "
                          f"Grade {grade}, {topic}, {difficulty}...")

                    try:
                        if dry_run:
                            is_diagram = topic in DIAGRAM_TOPICS
                            print(f"  ✓ Would generate {count_per_combo} questions (dry run){' [DIAGRAM]' if is_diagram else ''}")
                            generated_count += count_per_combo
                            continue

                        # Use diagram generation for diagram topics
                        if topic in DIAGRAM_TOPICS:
                            quiz_data = await generate_diagram_quiz(
                                grade=grade,
                                topic=topic,
                                difficulty=difficulty,
                                count=count_per_combo
                            )
                        else:
                            quiz_data = await generate_quiz_with_ollama(
                                grade=grade,
                                topic=topic,
                                difficulty=difficulty,
                                count=count_per_combo
                            )

                        if quiz_data and quiz_data.get('questions'):
                            # Store each question (force=True for diagram topics to regenerate)
                            stored = 0
                            for question in quiz_data['questions']:
                                # For diagram topics, use force=True to allow regeneration
                                if topic in DIAGRAM_TOPICS:
                                    # Direct insert for diagram topics
                                    from datetime import date
                                    from sqlalchemy import select, and_
                                    today = date.today()
                                    result = await db.execute(
                                        select(TopicQuestion).where(
                                            and_(
                                                TopicQuestion.grade == grade,
                                                TopicQuestion.topic == topic,
                                                TopicQuestion.difficulty == difficulty,
                                                TopicQuestion.created_date == today
                                            )
                                        )
                                    )
                                    row = result.scalar_one_or_none()
                                    if row:
                                        questions = row.question_data.get('questions', [])
                                        questions.append(question)
                                        row.question_data = {'questions': questions}
                                    else:
                                        new_entry = TopicQuestion(
                                            grade=grade,
                                            topic=topic,
                                            difficulty=difficulty,
                                            question_data={'questions': [question]},
                                            created_date=today
                                        )
                                        db.add(new_entry)
                                    success = True
                                else:
                                    success = await store_question(
                                        db, grade, topic, difficulty, question
                                    )
                                if success:
                                    stored += 1

                            await db.commit()
                            generated_count += stored
                            print(f"  ✓ Generated and stored {stored}/{len(quiz_data['questions'])} questions")
                        else:
                            print(f"  ✗ No questions generated")
                            failed_count += 1

                    except Exception as e:
                        print(f"  ✗ Error: {e}")
                        logger.error(f"Failed to generate for {grade}/{topic}/{difficulty}: {e}")
                        failed_count += 1
                        continue

        print()
        print("=" * 60)
        print("Pre-generation Complete!")
        print(f"  Combinations processed: {processed_count}")
        print(f"  Combinations skipped (existing): {skipped_count}")
        print(f"  Questions generated: {generated_count}")
        print(f"  Failed combinations: {failed_count}")
        print("=" * 60)

        return {
            "processed": processed_count,
            "skipped": skipped_count,
            "generated": generated_count,
            "failed": failed_count
        }


async def show_stats():
    """Show current question pool statistics."""
    from sqlalchemy import select, func, and_

    async with AsyncSessionLocal() as db:
        # Get counts by grade/topic/difficulty
        result = await db.execute(
            select(
                TopicQuestion.grade,
                TopicQuestion.topic,
                TopicQuestion.difficulty,
                func.count().label('count')
            ).group_by(
                TopicQuestion.grade,
                TopicQuestion.topic,
                TopicQuestion.difficulty
            )
        )

        combinations = {}
        total_questions = 0

        for row in result.all():
            key = f"{row[0]}/{row[1]}/{row[2]}"
            combinations[key] = row[3]
            total_questions += row[3]

        total_combinations = len(ALLOWED_GRADES) * len(ALL_TOPICS) * len(ALLOWED_DIFFICULTIES)
        covered = len(combinations)

        print("=" * 60)
        print("Question Pool Statistics")
        print("=" * 60)
        print(f"Total possible combinations: {total_combinations}")
        print(f"Covered combinations: {covered}")
        print(f"Coverage: {(covered / total_combinations) * 100:.1f}%")
        print(f"Total question entries: {total_questions}")
        print()

        # Show by grade
        for grade in ALLOWED_GRADES:
            grade_combos = {k: v for k, v in combinations.items() if k.startswith(f"{grade}/")}
            expected = len(ALL_TOPICS) * len(ALLOWED_DIFFICULTIES)
            print(f"Grade {grade}: {len(grade_combos)}/{expected} combinations")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pre-generate quiz questions")
    parser.add_argument("--grades", nargs="+", help="Grades to generate for (6, 7, 8)")
    parser.add_argument("--topics", nargs="+", help="Topics to generate for")
    parser.add_argument("--difficulties", nargs="+", help="Difficulties to generate (easy, medium, hard)")
    parser.add_argument("--count", type=int, default=10,
                       help="Questions per combination (default: 10)")
    parser.add_argument("--dry-run", action="store_true",
                       help="Don't actually store questions")
    parser.add_argument("--no-skip-existing", action="store_true",
                       help="Generate even if questions already exist")
    parser.add_argument("--stats", action="store_true",
                       help="Show current statistics and exit")

    args = parser.parse_args()

    if args.stats:
        asyncio.run(show_stats())
    else:
        asyncio.run(pregenerate_questions(
            grades=args.grades,
            topics=args.topics,
            difficulties=args.difficulties,
            count_per_combo=args.count,
            dry_run=args.dry_run,
            skip_existing=not args.no_skip_existing
        ))
