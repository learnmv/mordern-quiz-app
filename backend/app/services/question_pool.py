"""Question pool monitoring and management."""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select, and_
from typing import Dict, List, Any

from app.models.quiz import TopicQuestion
from app.services.quiz_generator import ALL_TOPICS

ALLOWED_GRADES = ["6", "7", "8"]
ALLOWED_DIFFICULTIES = ["easy", "medium", "hard"]
MIN_QUESTIONS_THRESHOLD = 5  # Alert if fewer than 5 questions available


async def get_question_pool_stats(db: AsyncSession) -> Dict[str, Any]:
    """Get statistics on the pre-generated question pool."""

    # Count questions by combination
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
    low_stock = []

    for row in result.all():
        key = f"{row[0]}/{row[1]}/{row[2]}"
        combinations[key] = row[3]

        if row[3] < MIN_QUESTIONS_THRESHOLD:
            low_stock.append({
                "grade": row[0],
                "topic": row[1],
                "difficulty": row[2],
                "count": row[3]
            })

    total_combinations = len(ALLOWED_GRADES) * len(ALL_TOPICS) * len(ALLOWED_DIFFICULTIES)

    return {
        "total_combinations": total_combinations,
        "covered_combinations": len(combinations),
        "coverage_percent": (len(combinations) / total_combinations) * 100 if total_combinations > 0 else 0,
        "total_questions": sum(combinations.values()),
        "low_stock_combinations": low_stock,
        "low_stock_count": len(low_stock)
    }


async def get_questions_for_combination(
    db: AsyncSession,
    grade: str,
    topic: str,
    difficulty: str
) -> int:
    """Get count of available questions for a specific combination."""
    result = await db.execute(
        select(func.count()).select_from(TopicQuestion).where(
            and_(
                TopicQuestion.grade == grade,
                TopicQuestion.topic == topic,
                TopicQuestion.difficulty == difficulty
            )
        )
    )
    return result.scalar()


async def get_coverage_by_grade(db: AsyncSession) -> Dict[str, Dict[str, Any]]:
    """Get question coverage statistics broken down by grade."""
    stats = {}

    for grade in ALLOWED_GRADES:
        expected = len(ALL_TOPICS) * len(ALLOWED_DIFFICULTIES)

        result = await db.execute(
            select(
                TopicQuestion.topic,
                TopicQuestion.difficulty,
                func.count().label('count')
            ).where(
                TopicQuestion.grade == grade
            ).group_by(
                TopicQuestion.topic,
                TopicQuestion.difficulty
            )
        )

        covered = result.all()
        covered_count = len(covered)

        # Get topic coverage
        topics_covered = set(row[0] for row in covered)
        topics_missing = [t for t in ALL_TOPICS if t not in topics_covered]

        stats[grade] = {
            "expected_combinations": expected,
            "covered_combinations": covered_count,
            "coverage_percent": (covered_count / expected) * 100 if expected > 0 else 0,
            "topics_covered": len(topics_covered),
            "topics_total": len(ALL_TOPICS),
            "topics_missing": topics_missing[:10],  # Limit to first 10
            "total_questions": sum(row[2] for row in covered)
        }

    return stats


async def get_pool_health(db: AsyncSession) -> Dict[str, Any]:
    """Get overall health status of the question pool."""
    stats = await get_question_pool_stats(db)

    # Determine health status
    if stats["coverage_percent"] >= 90 and stats["low_stock_count"] == 0:
        status = "healthy"
        message = "Question pool is well-stocked"
    elif stats["coverage_percent"] >= 70 and stats["low_stock_count"] < 10:
        status = "degraded"
        message = "Question pool needs attention"
    else:
        status = "critical"
        message = "Question pool requires immediate attention"

    return {
        "status": status,
        "message": message,
        "coverage_percent": stats["coverage_percent"],
        "low_stock_count": stats["low_stock_count"],
        "recommendations": _generate_recommendations(stats)
    }


def _generate_recommendations(stats: Dict[str, Any]) -> List[str]:
    """Generate recommendations based on pool statistics."""
    recommendations = []

    if stats["coverage_percent"] < 100:
        missing = stats["total_combinations"] - stats["covered_combinations"]
        recommendations.append(f"Generate questions for {missing} uncovered combinations")

    if stats["low_stock_count"] > 0:
        recommendations.append(f"Replenish {stats['low_stock_count']} low-stock combinations")

    if stats["coverage_percent"] >= 90 and stats["low_stock_count"] == 0:
        recommendations.append("Pool is healthy - maintain current levels")

    return recommendations
