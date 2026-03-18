"""Background tasks for pre-generating quiz questions."""
import asyncio
import logging
from typing import List, Tuple
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.database import AsyncSessionLocal
from app.models.quiz import TopicQuestion
from app.services.quiz_generator import generate_quiz_with_ollama, store_question

logger = logging.getLogger(__name__)

# Minimum number of cached questions to maintain per topic/difficulty combination
MIN_CACHE_THRESHOLD = 10

# Popular topic/difficulty combinations to pre-generate
POPULAR_COMBINATIONS: List[Tuple[str, str, str]] = [
    # Grade 6 topics
    ("6", "Fractions", "medium"),
    ("6", "Fractions", "easy"),
    ("6", "Decimals", "medium"),
    ("6", "Percentages", "medium"),
    ("6", "Ratios", "medium"),
    ("6", "Unit Rates", "medium"),
    ("6", "One-Step Equations", "medium"),
    ("6", "Area of Polygons", "medium"),
    ("6", "Volume of Prisms", "medium"),
    ("6", "Mean", "medium"),
    ("6", "Median", "medium"),
    # Grade 7 topics
    ("7", "Proportional Relationships", "medium"),
    ("7", "Percentages", "medium"),
    ("7", "Two-Step Equations", "medium"),
    ("7", "Inequalities", "medium"),
    ("7", "Circumference", "medium"),
    ("7", "Area of Circles", "medium"),
    ("7", "Volume", "medium"),
    ("7", "Surface Area", "medium"),
    # Grade 8 topics
    ("8", "Linear Equations", "medium"),
    ("8", "Systems of Equations", "medium"),
    ("8", "Functions", "medium"),
    ("8", "Pythagorean Theorem", "medium"),
    ("8", "Transformations", "medium"),
    ("8", "Scatter Plots", "medium"),
]


async def get_cache_count(
    db: AsyncSession,
    grade: str,
    topic: str,
    difficulty: str
) -> int:
    """Get the number of cached questions for a specific combination."""
    seven_days_ago = date.today() - __import__('datetime').timedelta(days=7)

    result = await db.execute(
        select(func.count()).select_from(TopicQuestion).where(
            and_(
                TopicQuestion.grade == grade,
                TopicQuestion.topic == topic,
                TopicQuestion.difficulty == difficulty,
                TopicQuestion.created_date >= seven_days_ago
            )
        )
    )

    # Also count questions in the JSONB data
    result2 = await db.execute(
        select(TopicQuestion).where(
            and_(
                TopicQuestion.grade == grade,
                TopicQuestion.topic == topic,
                TopicQuestion.difficulty == difficulty,
                TopicQuestion.created_date >= seven_days_ago
            )
        )
    )
    rows = result2.scalars().all()

    total_questions = 0
    for row in rows:
        questions = row.question_data.get('questions', [])
        total_questions += len(questions)

    return total_questions


async def generate_and_store_questions(
    db: AsyncSession,
    grade: str,
    topic: str,
    difficulty: str,
    count: int = 5
) -> int:
    """Generate and store questions for a specific combination.

    Returns:
        Number of questions successfully generated and stored.
    """
    try:
        logger.info(f"Generating {count} questions for grade={grade}, topic={topic}, difficulty={difficulty}")

        quiz_data = await generate_quiz_with_ollama(
            grade=grade,
            topic=topic,
            difficulty=difficulty,
            count=count,
            answered_hashes=[]
        )

        if not quiz_data or not quiz_data.get('questions'):
            logger.warning(f"Failed to generate questions for {grade}/{topic}/{difficulty}")
            return 0

        stored_count = 0
        for question in quiz_data['questions']:
            success = await store_question(db, grade, topic, difficulty, question)
            if success:
                stored_count += 1

        logger.info(f"Stored {stored_count}/{len(quiz_data['questions'])} questions for {grade}/{topic}/{difficulty}")
        return stored_count

    except Exception as e:
        logger.error(f"Error generating questions for {grade}/{topic}/{difficulty}: {e}")
        return 0


async def pregenerate_popular_questions(
    db: AsyncSession = None,
    combinations: List[Tuple[str, str, str]] = None
) -> dict:
    """Pre-generate questions for popular topic/difficulty combinations.

    This can be called periodically (e.g., every hour) to ensure cache is well-stocked.

    Args:
        db: Database session (optional - will create one if not provided)
        combinations: List of (grade, topic, difficulty) tuples to pre-generate for

    Returns:
        Dictionary with statistics about the pre-generation run
    """
    should_close_db = False
    if db is None:
        db = AsyncSessionLocal()
        should_close_db = True

    try:
        combos = combinations or POPULAR_COMBINATIONS
        stats = {
            "total_combinations_checked": len(combos),
            "combinations_generated": 0,
            "total_questions_generated": 0,
            "errors": []
        }

        for grade, topic, difficulty in combos:
            try:
                cached_count = await get_cache_count(db, grade, topic, difficulty)

                if cached_count < MIN_CACHE_THRESHOLD:
                    needed = MIN_CACHE_THRESHOLD - cached_count
                    # Generate extra to amortize API call cost
                    to_generate = max(needed, 5)

                    generated = await generate_and_store_questions(
                        db, grade, topic, difficulty, count=to_generate
                    )

                    if generated > 0:
                        stats["combinations_generated"] += 1
                        stats["total_questions_generated"] += generated

                    # Small delay to avoid overwhelming the API
                    await asyncio.sleep(0.5)

            except Exception as e:
                error_msg = f"Error processing {grade}/{topic}/{difficulty}: {str(e)}"
                logger.error(error_msg)
                stats["errors"].append(error_msg)

        logger.info(f"Pre-generation complete: {stats}")
        return stats

    finally:
        if should_close_db:
            await db.close()


async def pregenerate_single_topic(
    grade: str,
    topic: str,
    difficulty: str,
    count: int = 10
) -> int:
    """Pre-generate questions for a single topic/difficulty combination.

    Useful for on-demand pre-generation when a user selects a topic.

    Returns:
        Number of questions generated
    """
    async with AsyncSessionLocal() as db:
        return await generate_and_store_questions(db, grade, topic, difficulty, count)


# For running as a standalone script or scheduled task
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(pregenerate_popular_questions())
