"""Cron job tasks for automated question generation.

9 cron jobs total:
- grade-6-easy, grade-6-medium, grade-6-hard
- grade-7-easy, grade-7-medium, grade-7-hard
- grade-8-easy, grade-8-medium, grade-8-hard

Each runs every 5 minutes and cycles through grade-specific topics.
"""
import logging
from typing import Dict, Any
from datetime import datetime

from app.database import AsyncSessionLocal
from app.services.quiz_generator import (
    generate_quiz_with_ollama,
    generate_diagram_quiz,
    DIAGRAM_TOPICS,
    store_question,
    get_pregenerated_questions
)
from app.services.topic_cycler import TopicCycler

logger = logging.getLogger(__name__)

# Generation config
QUESTIONS_PER_RUN = 3  # Generate 3 questions per cron execution
MIN_QUESTIONS_THRESHOLD = 20  # Skip if already have 20+ questions for this combo


async def generate_questions_for_grade_difficulty(
    grade: str,
    difficulty: str
) -> Dict[str, Any]:
    """Generate questions for a specific grade/difficulty combination.

    This is the main cron job function that:
    1. Determines the next topic to generate (cycles through grade-specific topics)
    2. Checks if we need more questions for this grade/topic/difficulty
    3. Generates questions using Ollama API
    4. Stores them in the database

    Args:
        grade: Grade level ("6", "7", or "8")
        difficulty: Difficulty level ("easy", "medium", or "hard")

    Returns:
        Dict with generation results and metadata
    """
    cycler = TopicCycler()

    # Get next topic to generate (grade-specific)
    try:
        topic, topic_index = cycler.get_next_topic(grade, difficulty)
    except ValueError as e:
        logger.error(f"Failed to get next topic: {e}")
        return {
            "status": "error",
            "grade": grade,
            "difficulty": difficulty,
            "error": str(e)
        }

    async with AsyncSessionLocal() as db:
        try:
            # Check current question count for this combination
            existing = await get_pregenerated_questions(
                db, grade, topic, difficulty, count=100
            )
            existing_count = len(existing)

            if existing_count >= MIN_QUESTIONS_THRESHOLD:
                logger.info(
                    f"Cron[{grade}/{difficulty}]: Skipping {topic}, "
                    f"already have {existing_count} questions"
                )
                return {
                    "status": "skipped",
                    "grade": grade,
                    "difficulty": difficulty,
                    "topic": topic,
                    "reason": "sufficient_questions",
                    "existing_count": existing_count
                }

            # Generate questions (use diagram-aware generator for diagram topics)
            logger.info(
                f"Cron[{grade}/{difficulty}]: Generating {QUESTIONS_PER_RUN} "
                f"questions for topic '{topic}' (index {topic_index})"
            )

            if topic in DIAGRAM_TOPICS:
                logger.info(f"Cron[{grade}/{difficulty}]: Using diagram-aware generator for {topic}")
                quiz_data = await generate_diagram_quiz(
                    grade=grade,
                    topic=topic,
                    difficulty=difficulty,
                    count=QUESTIONS_PER_RUN,
                    answered_hashes=[]
                )
            else:
                quiz_data = await generate_quiz_with_ollama(
                    grade=grade,
                    topic=topic,
                    difficulty=difficulty,
                    count=QUESTIONS_PER_RUN,
                    answered_hashes=[]
                )

            if not quiz_data or not quiz_data.get('questions'):
                logger.warning(
                    f"Cron[{grade}/{difficulty}]: Failed to generate questions for {topic}"
                )
                return {
                    "status": "failed",
                    "grade": grade,
                    "difficulty": difficulty,
                    "topic": topic,
                    "reason": "generation_failed"
                }

            # Store generated questions
            stored_count = 0
            for question in quiz_data['questions']:
                success = await store_question(db, grade, topic, difficulty, question)
                if success:
                    stored_count += 1

            logger.info(
                f"Cron[{grade}/{difficulty}]: Stored {stored_count}/"
                f"{len(quiz_data['questions'])} questions for {topic}"
            )

            return {
                "status": "success",
                "grade": grade,
                "difficulty": difficulty,
                "topic": topic,
                "topic_index": topic_index,
                "generated": len(quiz_data['questions']),
                "stored": stored_count,
                "existing_before": existing_count
            }

        except Exception as e:
            logger.error(
                f"Cron[{grade}/{difficulty}]: Error generating for {topic}: {e}"
            )
            return {
                "status": "error",
                "grade": grade,
                "difficulty": difficulty,
                "topic": topic,
                "error": str(e)
            }


# Individual cron job functions for each grade/difficulty

async def cron_grade_6_easy():
    """Cron job for Grade 6 Easy - runs every 5 minutes."""
    return await generate_questions_for_grade_difficulty("6", "easy")

async def cron_grade_6_medium():
    """Cron job for Grade 6 Medium - runs every 5 minutes."""
    return await generate_questions_for_grade_difficulty("6", "medium")

async def cron_grade_6_hard():
    """Cron job for Grade 6 Hard - runs every 5 minutes."""
    return await generate_questions_for_grade_difficulty("6", "hard")

async def cron_grade_7_easy():
    """Cron job for Grade 7 Easy - runs every 5 minutes."""
    return await generate_questions_for_grade_difficulty("7", "easy")

async def cron_grade_7_medium():
    """Cron job for Grade 7 Medium - runs every 5 minutes."""
    return await generate_questions_for_grade_difficulty("7", "medium")

async def cron_grade_7_hard():
    """Cron job for Grade 7 Hard - runs every 5 minutes."""
    return await generate_questions_for_grade_difficulty("7", "hard")

async def cron_grade_8_easy():
    """Cron job for Grade 8 Easy - runs every 5 minutes."""
    return await generate_questions_for_grade_difficulty("8", "easy")

async def cron_grade_8_medium():
    """Cron job for Grade 8 Medium - runs every 5 minutes."""
    return await generate_questions_for_grade_difficulty("8", "medium")

async def cron_grade_8_hard():
    """Cron job for Grade 8 Hard - runs every 5 minutes."""
    return await generate_questions_for_grade_difficulty("8", "hard")
