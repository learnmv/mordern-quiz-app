from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from datetime import date

from app.models.progress import UserProgress, UserQuizHistory


async def get_total_questions_answered(db: AsyncSession, user_id: int) -> int:
    """Get total questions answered by user"""
    result = await db.execute(
        select(func.sum(UserProgress.total_count)).where(
            UserProgress.user_id == user_id
        )
    )
    total = result.scalar()
    return total or 0


async def get_all_topics_accuracy(db: AsyncSession, user_id: int) -> Dict[str, Dict[str, Any]]:
    """Get accuracy for all topics the user has attempted"""
    result = await db.execute(
        select(
            UserProgress.topic,
            UserProgress.correct_count,
            UserProgress.total_count
        ).where(UserProgress.user_id == user_id)
    )

    topics_accuracy = {}
    for row in result.all():
        topic, correct, total = row
        accuracy = (correct / total * 100) if total > 0 else 0
        topics_accuracy[topic] = {
            "correct": correct,
            "total": total,
            "accuracy": round(accuracy, 1)
        }

    return topics_accuracy


async def get_topic_difficulty(
    db: AsyncSession,
    user_id: int,
    topic: str,
    total_answered: int
) -> Tuple[str, str]:
    """Get difficulty for a topic based on accuracy and time thresholds"""
    if total_answered < 5:
        return "medium", "new_user"

    # Get accuracy
    result = await db.execute(
        select(
            UserProgress.correct_count,
            UserProgress.total_count
        ).where(
            and_(
                UserProgress.user_id == user_id,
                UserProgress.topic == topic
            )
        )
    )
    row = result.first()

    if not row:
        return "medium", "no_data"

    correct, total = row
    accuracy = (correct / total * 100) if total > 0 else 0

    # Check time: if user spends >180s (3 min) AND gets wrong, they're struggling
    result = await db.execute(
        select(func.count()).where(
            and_(
                UserQuizHistory.user_id == user_id,
                UserQuizHistory.topic == topic,
                UserQuizHistory.was_correct == 0,
                UserQuizHistory.time_spent > 180
            )
        )
    )
    slow_wrong_count = result.scalar()

    # Determine difficulty based on accuracy
    if accuracy < 60:
        base_difficulty = "easy"
    elif accuracy <= 80:
        base_difficulty = "medium"
    else:
        base_difficulty = "hard"

    # If struggling (slow + wrong), reduce difficulty
    if slow_wrong_count >= 2:
        if base_difficulty == "hard":
            return "medium", "struggling"
        elif base_difficulty == "medium":
            return "easy", "struggling"
        else:
            return "easy", "struggling"

    return base_difficulty, "normal"


async def get_recent_streak(
    db: AsyncSession,
    user_id: int,
    topic: str,
    correct: bool = True
) -> int:
    """Get streak of correct/incorrect answers for adaptive mode"""
    result = await db.execute(
        select(UserQuizHistory.was_correct).where(
            and_(
                UserQuizHistory.user_id == user_id,
                UserQuizHistory.topic == topic
            )
        ).order_by(UserQuizHistory.answered_at.desc()).limit(10)
    )
    results = result.all()

    streak = 0
    target = 1 if correct else 0
    for row in results:
        if row[0] == target:
            streak += 1
        else:
            break

    return streak


async def get_answered_questions(
    db: AsyncSession,
    user_id: int,
    topics: List[str]
) -> set:
    """Get hashes of questions user has already answered"""
    if not topics:
        return set()

    result = await db.execute(
        select(UserQuizHistory.question_hash).where(
            and_(
                UserQuizHistory.user_id == user_id,
                UserQuizHistory.topic.in_(topics)
            )
        ).distinct()
    )

    return {row[0] for row in result.all()}


async def get_weak_topics(
    db: AsyncSession,
    user_id: int,
    min_questions: int = 3
) -> List[Dict[str, Any]]:
    """Get topics where user needs improvement (accuracy < 70%)"""
    result = await db.execute(
        select(
            UserProgress.topic,
            UserProgress.correct_count,
            UserProgress.total_count
        ).where(
            and_(
                UserProgress.user_id == user_id,
                UserProgress.total_count >= min_questions
            )
        )
    )

    weak = []
    for row in result.all():
        topic, correct, total = row
        accuracy = (correct / total * 100) if total > 0 else 0
        if accuracy < 70:
            weak.append({
                "topic": topic,
                "accuracy": round(accuracy, 1),
                "total": total
            })

    # Sort by accuracy ascending (weakest first)
    weak.sort(key=lambda x: x["accuracy"])
    return weak


async def get_strong_topics(
    db: AsyncSession,
    user_id: int,
    min_questions: int = 5,
    accuracy_threshold: float = 70
) -> List[Dict[str, Any]]:
    """Get topics where user is performing well"""
    result = await db.execute(
        select(
            UserProgress.topic,
            UserProgress.correct_count,
            UserProgress.total_count
        ).where(
            and_(
                UserProgress.user_id == user_id,
                UserProgress.total_count >= min_questions
            )
        )
    )

    strong = []
    for row in result.all():
        topic, correct, total = row
        accuracy = (correct / total * 100) if total > 0 else 0
        if accuracy >= accuracy_threshold:
            strong.append({
                "topic": topic,
                "accuracy": round(accuracy, 1),
                "total": total
            })

    # Sort by accuracy descending (strongest first)
    strong.sort(key=lambda x: x["accuracy"], reverse=True)
    return strong


async def get_topic_streaks(db: AsyncSession, user_id: int) -> Dict[str, Dict[str, int]]:
    """Get current streaks for all topics user has practiced using single query with window functions"""
    from sqlalchemy import text

    # Single query using window functions to calculate streaks efficiently
    query = text("""
        WITH ranked_answers AS (
            SELECT
                topic,
                was_correct,
                ROW_NUMBER() OVER (PARTITION BY topic ORDER BY answered_at DESC) as rn,
                answered_at
            FROM user_quiz_history
            WHERE user_id = :user_id
        ),
        current_streaks AS (
            SELECT
                topic,
                COUNT(*) FILTER (WHERE was_correct = 1 AND rn <= 20) as current_streak
            FROM ranked_answers
            WHERE rn <= 20
            GROUP BY topic
        ),
        all_answers AS (
            SELECT
                topic,
                was_correct,
                LAG(was_correct) OVER (PARTITION BY topic ORDER BY answered_at) as prev_correct
            FROM user_quiz_history
            WHERE user_id = :user_id
        ),
        streak_groups AS (
            SELECT
                topic,
                was_correct,
                SUM(CASE WHEN was_correct = 1 AND (prev_correct = 0 OR prev_correct IS NULL) THEN 1 ELSE 0 END)
                    OVER (PARTITION BY topic ORDER BY answered_at) as streak_group
            FROM all_answers
        ),
        streak_lengths AS (
            SELECT
                topic,
                streak_group,
                COUNT(*) as streak_len
            FROM streak_groups
            WHERE was_correct = 1
            GROUP BY topic, streak_group
        ),
        max_streaks AS (
            SELECT
                topic,
                COALESCE(MAX(streak_len), 0) as max_streak
            FROM streak_lengths
            GROUP BY topic
        )
        SELECT
            cs.topic,
            cs.current_streak,
            COALESCE(ms.max_streak, 0) as max_streak
        FROM current_streaks cs
        LEFT JOIN max_streaks ms ON cs.topic = ms.topic
    """)

    result = await db.execute(query, {"user_id": user_id})

    streaks = {}
    for row in result.all():
        topic, current_streak, max_streak = row
        streaks[topic] = {
            "current": current_streak,
            "max": max_streak
        }

    return streaks


async def get_in_progress_topics(
    db: AsyncSession,
    user_id: int
) -> List[Dict[str, Any]]:
    """Get topics being worked on (1-4 questions answered, not enough data yet)"""
    result = await db.execute(
        select(
            UserProgress.topic,
            UserProgress.correct_count,
            UserProgress.total_count
        ).where(
            and_(
                UserProgress.user_id == user_id,
                UserProgress.total_count >= 1,
                UserProgress.total_count < 5
            )
        )
    )

    in_progress = []
    for row in result.all():
        topic, correct, total = row
        accuracy = (correct / total * 100) if total > 0 else 0
        in_progress.append({
            "topic": topic,
            "accuracy": round(accuracy, 1),
            "total": total
        })

    return in_progress


async def get_recommended_difficulty(
    db: AsyncSession,
    user_id: int,
    topic: str
) -> str:
    """Recommend difficulty based on recent performance"""
    result = await db.execute(
        select(UserQuizHistory.was_correct).where(
            and_(
                UserQuizHistory.user_id == user_id,
                UserQuizHistory.topic == topic
            )
        ).order_by(UserQuizHistory.answered_at.desc()).limit(10)
    )
    results = result.all()

    if len(results) < 5:
        return "medium"

    recent_accuracy = sum(row[0] for row in results) / len(results) * 100

    if recent_accuracy >= 80:
        return "hard"
    elif recent_accuracy >= 50:
        return "medium"
    else:
        return "easy"


async def update_user_progress(
    db: AsyncSession,
    user_id: int,
    topic: str,
    was_correct: bool
) -> None:
    """Update progress after answering a question"""
    today = date.today()

    # Check if progress exists
    result = await db.execute(
        select(UserProgress).where(
            and_(
                UserProgress.user_id == user_id,
                UserProgress.topic == topic
            )
        )
    )
    progress = result.scalar_one_or_none()

    if progress:
        progress.correct_count += 1 if was_correct else 0
        progress.total_count += 1
        progress.last_quiz_date = today
    else:
        progress = UserProgress(
            user_id=user_id,
            topic=topic,
            correct_count=1 if was_correct else 0,
            total_count=1,
            last_quiz_date=today
        )
        db.add(progress)

    await db.commit()


async def record_question_attempt(
    db: AsyncSession,
    user_id: int,
    question_hash: str,
    topic: str,
    was_correct: bool,
    time_spent: int = 0
) -> None:
    """Record individual question attempt for repeat avoidance"""
    attempt = UserQuizHistory(
        user_id=user_id,
        question_hash=question_hash,
        topic=topic,
        was_correct=1 if was_correct else 0,
        time_spent=time_spent
    )
    db.add(attempt)
    await db.commit()


async def get_user_stats(db: AsyncSession, user_id: int) -> Dict[str, Any]:
    """Get overall user statistics"""
    stats = {}

    # Total questions answered
    result = await db.execute(
        select(func.count()).where(
            UserQuizHistory.user_id == user_id
        )
    )
    stats["total_questions"] = result.scalar()

    # Overall accuracy
    result = await db.execute(
        select(
            func.sum(UserQuizHistory.was_correct),
            func.count()
        ).where(UserQuizHistory.user_id == user_id)
    )
    row = result.first()
    correct = row[0] or 0
    total = row[1] or 0
    stats["overall_accuracy"] = round(correct / total * 100, 1) if total > 0 else 0

    # Topics attempted
    result = await db.execute(
        select(func.count(UserProgress.topic)).where(
            UserProgress.user_id == user_id
        )
    )
    stats["topics_attempted"] = result.scalar()

    # Quizzes this week
    from datetime import timedelta
    seven_days_ago = date.today() - timedelta(days=7)
    result = await db.execute(
        select(func.count(func.distinct(func.date(UserQuizHistory.answered_at)))).where(
            and_(
                UserQuizHistory.user_id == user_id,
                UserQuizHistory.answered_at >= seven_days_ago
            )
        )
    )
    stats["active_days_week"] = result.scalar()

    return stats


async def get_user_progress(db: AsyncSession, user_id: int) -> Dict[str, Dict[str, Any]]:
    """Get user's progress per topic"""
    result = await db.execute(
        select(
            UserProgress.topic,
            UserProgress.correct_count,
            UserProgress.total_count,
            UserProgress.last_quiz_date
        ).where(UserProgress.user_id == user_id).order_by(UserProgress.topic)
    )

    progress = {}
    for row in result.all():
        topic, correct, total, last_quiz = row
        accuracy = (correct / total * 100) if total > 0 else 0
        progress[topic] = {
            "correct": correct,
            "total": total,
            "accuracy": round(accuracy, 1),
            "last_quiz": last_quiz
        }

    return progress