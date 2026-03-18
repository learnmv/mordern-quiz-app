from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import random

from app.database import get_db
from app.models.user import User
from app.schemas.quiz import (
    QuizRequest, QuizResponse, AnswerSubmission, AnswerResponse,
    DailyStats, PopularCombination, GradeStats, TopicStats,
    WeakTopicsQuizResponse, DiagramQuizRequest, DiagramQuizResponse
)
from app.routers.auth import get_current_user, get_current_user_optional
from app.services.quiz_generator import (
    generate_quiz_with_ollama, get_cached_question, store_question,
    log_quiz_request, get_popular_combinations, get_stats, get_grade_stats,
    get_topic_stats, ALL_TOPICS, generate_diagram_quiz, get_cache_metrics
)
from app.services.adaptive_learning import (
    get_total_questions_answered, get_all_topics_accuracy, get_topic_difficulty,
    get_recent_streak, get_answered_questions, get_weak_topics
)

router = APIRouter(prefix="/api", tags=["quiz"])


@router.post("/generate-quiz", response_model=QuizResponse)
async def generate_quiz(
    request: QuizRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_optional)
):
    """Generate a quiz with personalization"""
    user_id = current_user.id if current_user else None

    # Determine topic and difficulty
    topic_for_question = None
    difficulty = "medium"
    adaptive_mode = False

    if user_id:
        total_answered = await get_total_questions_answered(db, user_id)

        if total_answered >= 5:
            # Adaptive mode: cycle through topics
            topics_accuracy = await get_all_topics_accuracy(db, user_id)
            question_num = total_answered
            topic_index = question_num % len(ALL_TOPICS)
            topic_for_question = ALL_TOPICS[topic_index]

            # Check for wrong streak
            wrong_streak = await get_recent_streak(db, user_id, topic_for_question, correct=False)
            if wrong_streak >= 3:
                difficulty = "easy"
                adaptive_mode = True
            else:
                topic_accuracy = topics_accuracy.get(topic_for_question, {})
                total_for_topic = topic_accuracy.get("total", 0)
                difficulty, reason = await get_topic_difficulty(db, user_id, topic_for_question, total_for_topic)
                adaptive_mode = True
        else:
            # New user
            topic_index = 0
            topic_for_question = ALL_TOPICS[topic_index]
            difficulty = "medium"

        # Get answered hashes
        answered_hashes = list(await get_answered_questions(db, user_id, [topic_for_question])) if topic_for_question else []
    else:
        # Guest user
        topic_for_question = random.choice(ALL_TOPICS)
        answered_hashes = []

    # Try cache first
    cached = await get_cached_question(db, request.grade, topic_for_question, difficulty, answered_hashes)

    if cached:
        await log_quiz_request(db, request.grade, [topic_for_question], difficulty, "cache", user_id)
        return {"questions": [cached]}

    # Generate new question
    quiz_data = await generate_quiz_with_ollama(
        request.grade,
        topic_for_question,
        difficulty,
        request.count,
        answered_hashes
    )

    if not quiz_data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate quiz"
        )

    # Store in cache
    for q in quiz_data["questions"]:
        await store_question(db, request.grade, topic_for_question, difficulty, q)

    await log_quiz_request(db, request.grade, [topic_for_question], difficulty, "fresh", user_id)

    return quiz_data


@router.post("/answer", response_model=AnswerResponse)
async def record_answer(
    submission: AnswerSubmission,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Record user's answer and update progress"""
    from app.services.adaptive_learning import update_user_progress, record_question_attempt

    await update_user_progress(db, current_user.id, submission.topic, submission.was_correct)
    await record_question_attempt(
        db, current_user.id, submission.question_hash, submission.topic,
        submission.was_correct, submission.time_spent
    )

    return {"success": True}


@router.get("/answered-questions")
async def get_answered(
    topics: str = "",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get questions user has already answered"""
    topic_list = [t.strip() for t in topics.split(",") if t.strip()]
    hashes = await get_answered_questions(db, current_user.id, topic_list)

    return {"hashes": list(hashes)}


@router.post("/generate-weak-topics-quiz", response_model=WeakTopicsQuizResponse)
async def generate_weak_topics_quiz(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generate a quiz focused on user's weak topics"""
    weak = await get_weak_topics(db, current_user.id)

    if not weak:
        return {
            "weak_topics": [],
            "message": "No weak topics found! You're doing great!"
        }

    # Get the weakest topics (up to 3)
    weakest = weak[:3]
    topic_names = [t["topic"] for t in weakest]

    return {
        "weak_topics": weakest,
        "message": f"Starting focused practice on: {', '.join(topic_names)}"
    }


@router.get("/stats", response_model=DailyStats)
async def api_stats(db: AsyncSession = Depends(get_db)):
    """Get daily statistics"""
    return await get_stats(db)


@router.get("/popular", response_model=List[PopularCombination])
async def api_popular(
    limit: int = 20,
    db: AsyncSession = Depends(get_db)
):
    """Get popular quiz combinations"""
    return await get_popular_combinations(db, limit)


@router.get("/grade-stats", response_model=GradeStats)
async def api_grade_stats(db: AsyncSession = Depends(get_db)):
    """Get grade distribution statistics"""
    return await get_grade_stats(db)


@router.get("/topic-stats")
async def api_topic_stats(db: AsyncSession = Depends(get_db)):
    """Get topic coverage statistics"""
    return await get_topic_stats(db)


@router.get("/cache-metrics")
async def api_cache_metrics():
    """Get question cache hit/miss metrics"""
    return get_cache_metrics()


@router.post("/generate-diagram-quiz", response_model=DiagramQuizResponse)
async def generate_diagram_quiz_endpoint(
    request: DiagramQuizRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_optional)
):
    """Generate a quiz with diagram-based questions for visual topics"""
    user_id = current_user.id if current_user else None

    # Diagram topics that require visual representation
    DIAGRAM_TOPICS = [
        "Area of Polygons", "Volume of Prisms", "Surface Area",
        "Coordinate Plane", "Coordinate Plane Polygons", "Number Line",
        "Dot Plots", "Histograms", "Box Plots"
    ]

    # Validate topic
    if request.topic not in DIAGRAM_TOPICS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Topic '{request.topic}' does not support diagrams. Choose from: {', '.join(DIAGRAM_TOPICS)}"
        )

    # Get answered hashes to avoid repeats
    answered_hashes = []
    if user_id:
        from app.services.adaptive_learning import get_answered_questions
        answered_hashes = list(await get_answered_questions(db, user_id, [request.topic]))

    # Try cache first
    cached = await get_cached_question(db, request.grade, request.topic, request.difficulty, answered_hashes)

    if cached:
        await log_quiz_request(db, request.grade, [request.topic], request.difficulty, "cache", user_id)
        # Check if cached question has diagram data
        if "diagram" in cached:
            return {"questions": [cached]}

    # Generate new diagram question
    quiz_data = await generate_diagram_quiz(
        request.grade,
        request.topic,
        request.difficulty,
        request.count,
        answered_hashes
    )

    if not quiz_data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate diagram quiz"
        )

    # Store in cache
    for q in quiz_data["questions"]:
        await store_question(db, request.grade, request.topic, request.difficulty, q)

    await log_quiz_request(db, request.grade, [request.topic], request.difficulty, "fresh", user_id)

    return quiz_data