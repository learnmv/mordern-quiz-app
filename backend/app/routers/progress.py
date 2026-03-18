import asyncio
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.progress import ProgressResponse, DifficultyRecommendation
from app.routers.auth import get_current_user
from app.services.adaptive_learning import (
    get_user_progress, get_weak_topics, get_strong_topics, get_topic_streaks,
    get_in_progress_topics, get_recommended_difficulty, get_user_stats
)
from app.services.gamification import get_user_badges

router = APIRouter(prefix="/api", tags=["progress"])


@router.get("/progress", response_model=ProgressResponse)
async def get_progress(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get user's progress, weak topics, strong topics, streaks, and badges"""
    user_id = current_user.id

    # Execute all independent queries in parallel using asyncio.gather
    # This reduces 7+ sequential round-trips to a single parallel batch
    progress, weak_topics, strong_topics, streaks, badges, in_progress, stats = await asyncio.gather(
        get_user_progress(db, user_id),
        get_weak_topics(db, user_id),
        get_strong_topics(db, user_id),
        get_topic_streaks(db, user_id),
        get_user_badges(db, user_id),
        get_in_progress_topics(db, user_id),
        get_user_stats(db, user_id)
    )

    # Add streak info to weak and strong topics
    for topic in weak_topics:
        topic["streak"] = streaks.get(topic["topic"], {}).get("current", 0)
        topic["max_streak"] = streaks.get(topic["topic"], {}).get("max", 0)

    for topic in strong_topics:
        topic["streak"] = streaks.get(topic["topic"], {}).get("current", 0)
        topic["max_streak"] = streaks.get(topic["topic"], {}).get("max", 0)

    return {
        "progress": progress,
        "weak_topics": weak_topics,
        "strong_topics": strong_topics,
        "in_progress": in_progress,
        "streaks": streaks,
        "badges": badges,
        "stats": stats
    }


@router.get("/recommend-difficulty", response_model=DifficultyRecommendation)
async def recommend_difficulty(
    topic: str = "",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Recommend difficulty based on user's performance"""
    if not topic:
        return {"difficulty": "medium"}

    difficulty = await get_recommended_difficulty(db, current_user.id, topic)
    return {"difficulty": difficulty}


@router.get("/weak-topics")
async def weak_topics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get user's weak topics"""
    return await get_weak_topics(db, current_user.id)