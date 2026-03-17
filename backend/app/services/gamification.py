from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from datetime import date, timedelta

from app.models.gamification import Badge, UserBadge
from app.models.progress import UserProgress, UserQuizHistory


# Predefined badges
DEFAULT_BADGES = [
    {
        "badge_id": "quiz_novice",
        "name": "Quiz Novice",
        "description": "Answered 10 questions",
        "icon": "🌱",
        "requirement_type": "questions_answered",
        "requirement_value": 10
    },
    {
        "badge_id": "quiz_enthusiast",
        "name": "Quiz Enthusiast",
        "description": "Answered 50 questions",
        "icon": "🔥",
        "requirement_type": "questions_answered",
        "requirement_value": 50
    },
    {
        "badge_id": "quiz_master",
        "name": "Quiz Master",
        "description": "Answered 100 questions",
        "icon": "🏆",
        "requirement_type": "questions_answered",
        "requirement_value": 100
    },
    {
        "badge_id": "accuracy_star",
        "name": "Accuracy Star",
        "description": "Achieved 80% accuracy",
        "icon": "⭐",
        "requirement_type": "accuracy",
        "requirement_value": 80
    },
    {
        "badge_id": "perfect_streak",
        "name": "Hot Streak",
        "description": "5 correct answers in a row",
        "icon": "🔥",
        "requirement_type": "streak",
        "requirement_value": 5
    }
]


async def init_badges(db: AsyncSession) -> None:
    """Initialize default badges in the database"""
    for badge_data in DEFAULT_BADGES:
        result = await db.execute(
            select(Badge).where(Badge.badge_id == badge_data["badge_id"])
        )
        existing = result.scalar_one_or_none()

        if not existing:
            badge = Badge(**badge_data)
            db.add(badge)

    await db.commit()


async def get_user_badges(db: AsyncSession, user_id: int) -> List[Dict[str, Any]]:
    """Calculate earned badges based on user performance"""
    badges = []

    # Get user stats
    result = await db.execute(
        select(
            func.sum(UserProgress.total_count),
            func.sum(UserProgress.correct_count)
        ).where(UserProgress.user_id == user_id)
    )
    row = result.first()
    total = row[0] or 0
    correct = row[1] or 0
    accuracy = (correct / total * 100) if total > 0 else 0

    # Quiz Novice - Answer 10 questions
    if total >= 10:
        badges.append({
            "id": "quiz_novice",
            "name": "Quiz Novice",
            "description": "Answered 10 questions",
            "icon": "🌱",
            "achieved": True
        })

    # Quiz Enthusiast - Answer 50 questions
    if total >= 50:
        badges.append({
            "id": "quiz_enthusiast",
            "name": "Quiz Enthusiast",
            "description": "Answered 50 questions",
            "icon": "🔥",
            "achieved": True
        })

    # Quiz Master - Answer 100 questions
    if total >= 100:
        badges.append({
            "id": "quiz_master",
            "name": "Quiz Master",
            "description": "Answered 100 questions",
            "icon": "🏆",
            "achieved": True
        })

    # Accuracy Star - 80% overall accuracy with min 20 questions
    if accuracy >= 80 and total >= 20:
        badges.append({
            "id": "accuracy_star",
            "name": "Accuracy Star",
            "description": "Achieved 80% accuracy",
            "icon": "⭐",
            "achieved": True
        })

    # Perfect Streak - 5 correct in a row
    result = await db.execute(
        select(UserQuizHistory).where(
            and_(
                UserQuizHistory.user_id == user_id,
                UserQuizHistory.was_correct == 1
            )
        ).order_by(UserQuizHistory.answered_at.desc())
    )
    results = result.scalars().all()

    current_streak = 0
    for row in results:
        if row.was_correct == 1:
            current_streak += 1
            if current_streak >= 5:
                badges.append({
                    "id": "perfect_streak",
                    "name": "Hot Streak",
                    "description": "5 correct answers in a row",
                    "icon": "🔥",
                    "achieved": True
                })
                break
        else:
            break

    # Topic Master badges - 90% accuracy on any topic with 10+ questions
    result = await db.execute(
        select(UserProgress).where(
            and_(
                UserProgress.user_id == user_id,
                UserProgress.total_count >= 10
            )
        )
    )
    topic_masters = []
    for row in result.scalars().all():
        topic = row.topic
        correct = row.correct_count
        total = row.total_count
        acc = (correct / total * 100)
        if acc >= 90:
            topic_masters.append(topic)

    for topic in topic_masters[:3]:  # Limit to 3 badges
        badges.append({
            "id": f"master_{topic.lower().replace(' ', '_')}",
            "name": f"{topic} Master",
            "description": f"Achieved 90% accuracy in {topic}",
            "icon": "🎓",
            "achieved": True
        })

    return badges


async def check_and_award_badges(db: AsyncSession, user_id: int) -> List[Dict[str, Any]]:
    """Check for new badges and award them"""
    # Get current badges
    result = await db.execute(
        select(UserBadge.badge_id).where(UserBadge.user_id == user_id)
    )
    current_badge_ids = {row[0] for row in result.all()}

    # Calculate eligible badges
    eligible_badges = await get_user_badges(db, user_id)

    new_badges = []
    for badge in eligible_badges:
        if badge["id"] not in current_badge_ids:
            # Award the badge
            user_badge = UserBadge(
                user_id=user_id,
                badge_id=badge["id"]
            )
            db.add(user_badge)
            new_badges.append(badge)

    if new_badges:
        await db.commit()

    return new_badges