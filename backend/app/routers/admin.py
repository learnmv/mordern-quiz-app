"""Admin endpoints for question management."""
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime

logger = logging.getLogger(__name__)

from app.database import get_db
from app.routers.auth import get_current_user
from app.models.user import User
from app.models.quiz import TopicQuestion
from app.services.quiz_generator import ALL_TOPICS

router = APIRouter(prefix="/api/admin", tags=["admin"])

ALLOWED_GRADES = ["6", "7", "8"]
ALLOWED_DIFFICULTIES = ["easy", "medium", "hard"]


class PreGenerateRequest(BaseModel):
    grades: Optional[List[str]] = None
    topics: Optional[List[str]] = None
    difficulties: Optional[List[str]] = None
    count_per_combo: int = 10


class PreGenerateResponse(BaseModel):
    task_id: str
    message: str
    estimated_questions: int


class QuestionStatsResponse(BaseModel):
    total_combinations: int
    covered_combinations: int
    coverage_percent: float
    total_questions: int
    by_combination: List[Dict[str, Any]]
    low_stock_combinations: List[Dict[str, Any]]
    low_stock_count: int


def verify_admin(current_user: User) -> None:
    """Verify user has admin privileges."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )


@router.post("/pregenerate", response_model=PreGenerateResponse)
async def trigger_pregeneration(
    request: PreGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Trigger background pre-generation of questions.

    Requires admin privileges.
    """
    verify_admin(current_user)

    from app.tasks.queue import get_queue

    grades = request.grades or ALLOWED_GRADES
    topics = request.topics or ALL_TOPICS
    difficulties = request.difficulties or ALLOWED_DIFFICULTIES

    # Validate inputs
    invalid_grades = [g for g in grades if g not in ALLOWED_GRADES]
    if invalid_grades:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid grades: {invalid_grades}. Allowed: {ALLOWED_GRADES}"
        )

    invalid_difficulties = [d for d in difficulties if d not in ALLOWED_DIFFICULTIES]
    if invalid_difficulties:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid difficulties: {invalid_difficulties}. Allowed: {ALLOWED_DIFFICULTIES}"
        )

    invalid_topics = [t for t in topics if t not in ALL_TOPICS]
    if invalid_topics:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid topics: {invalid_topics[:5]}... (and {len(invalid_topics) - 5} more)"
        )

    estimated = len(grades) * len(topics) * len(difficulties) * request.count_per_combo

    # Start background task
    queue = get_queue("question_generation")

    from app.tasks.question_generator import pregenerate_bulk_task

    task_id = await queue.add(
        pregenerate_bulk_task,
        grades=grades,
        topics=topics,
        difficulties=difficulties,
        count_per_combo=request.count_per_combo
    )

    return PreGenerateResponse(
        task_id=task_id,
        message=f"Pre-generation started. Estimated {estimated} questions.",
        estimated_questions=estimated
    )


@router.get("/pregenerate/status/{task_id}")
async def get_pregeneration_status(
    task_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get status of pre-generation task."""
    verify_admin(current_user)

    from app.tasks.queue import get_queue
    queue = get_queue("question_generation")
    task_status = queue.get_task_status(task_id)

    if not task_status:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )

    return task_status


@router.get("/question-stats", response_model=QuestionStatsResponse)
async def get_question_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get statistics on pre-generated questions."""
    verify_admin(current_user)

    MIN_QUESTIONS_THRESHOLD = 5

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

    stats = []
    low_stock = []

    for row in result.all():
        stat = {
            "grade": row[0],
            "topic": row[1],
            "difficulty": row[2],
            "count": row[3]
        }
        stats.append(stat)

        if row[3] < MIN_QUESTIONS_THRESHOLD:
            low_stock.append(stat)

    # Calculate coverage
    total_combinations = len(ALLOWED_GRADES) * len(ALL_TOPICS) * len(ALLOWED_DIFFICULTIES)
    covered_combinations = len(stats)

    return QuestionStatsResponse(
        total_combinations=total_combinations,
        covered_combinations=covered_combinations,
        coverage_percent=(covered_combinations / total_combinations) * 100 if total_combinations > 0 else 0,
        total_questions=sum(s["count"] for s in stats),
        by_combination=stats,
        low_stock_combinations=low_stock,
        low_stock_count=len(low_stock)
    )


@router.get("/question-stats/{grade}/{topic}/{difficulty}")
async def get_specific_combination_stats(
    grade: str,
    topic: str,
    difficulty: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get detailed stats for a specific grade/topic/difficulty combination."""
    verify_admin(current_user)

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

    total_questions = 0
    question_hashes = []
    created_dates = []

    for row in rows:
        questions = row.question_data.get('questions', [])
        total_questions += len(questions)
        for q in questions:
            if 'hash' in q:
                question_hashes.append(q['hash'])
        created_dates.append(row.created_date.isoformat() if row.created_date else None)

    return {
        "grade": grade,
        "topic": topic,
        "difficulty": difficulty,
        "total_questions": total_questions,
        "unique_hashes": len(set(question_hashes)),
        "created_dates": created_dates,
        "db_entries": len(rows)
    }


@router.post("/users/{user_id}/make-admin")
async def make_user_admin(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Make a user an admin."""
    verify_admin(current_user)

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    user.is_admin = True
    await db.commit()

    return {"message": f"User {user.username} is now an admin"}


class GenerateQuestionsRequest(BaseModel):
    grade: str
    topic: str
    difficulty: str
    count: int = 10


class GenerateQuestionsResponse(BaseModel):
    success: bool
    generated_count: int
    message: str


# Curriculum data for topic lookup
CURRICULUM = {
    "6": {
        "domains": [
            {"id": "6-rp", "name": "Ratios & Proportional Relationships", "topics": ["Unit Rates", "Ratios", "Percentages", "Ratio Reasoning"]},
            {"id": "6-ns", "name": "The Number System", "topics": ["Fractions", "Decimals", "Negative Numbers", "GCF", "LCM", "Absolute Value", "Number Line", "Coordinate Plane"]},
            {"id": "6-ee", "name": "Expressions & Equations", "topics": ["Variables", "Writing Expressions", "One-Step Equations", "One-Step Inequalities", "Evaluating Expressions", "Order of Operations", "Equivalent Expressions"]},
            {"id": "6-g", "name": "Geometry", "topics": ["Area of Polygons", "Volume of Prisms", "Surface Area", "Coordinate Plane Polygons"]},
            {"id": "6-sp", "name": "Statistics & Probability", "topics": ["Statistical Questions", "Mean", "Median", "Mode", "Range", "Dot Plots", "Histograms", "Box Plots"]},
        ]
    },
    "7": {
        "domains": [
            {"id": "7-rp", "name": "Ratios & Proportional Relationships", "topics": ["Unit Rates", "Proportional Relationships", "Constant of Proportionality", "Percentages", "Markup & Discount", "Simple Interest", "Scale Drawings"]},
            {"id": "7-ns", "name": "The Number System", "topics": ["Add & Subtract Rationals", "Multiply & Divide Rationals", "Convert to Decimals", "Real-World Problems", "Properties of Operations", "Complex Fractions"]},
            {"id": "7-ee", "name": "Expressions & Equations", "topics": ["Factor & Expand Linear Expressions", "Rewriting Expressions", "Two-Step Equations", "Two-Step Inequalities", "Word Problems", "Multi-Step Equations"]},
            {"id": "7-g", "name": "Geometry", "topics": ["Scale Drawings", "Drawing Geometric Shapes", "Cross-Sections", "Circles (Area & Circumference)", "Angles", "Area & Perimeter", "Volume & Surface Area", "Surveying Areas"]},
            {"id": "7-sp", "name": "Statistics & Probability", "topics": ["Populations & Samples", "Random Sampling", "Comparing Data Sets", "Mean, Median, IQR", "Probability", "Compound Events", "Tree Diagrams"]},
        ]
    },
    "8": {
        "domains": [
            {"id": "8-ns", "name": "The Number System", "topics": ["Rational Numbers", "Irrational Numbers", "Approximate Irrationals", "Compare Real Numbers", "Scientific Notation", "Operations with Sci Notation"]},
            {"id": "8-ee", "name": "Expressions & Equations", "topics": ["Integer Exponents", "Laws of Exponents", "Scientific Notation", "Linear Equations", "Solving for Variables", "Systems of Equations", "Graphing Lines", "Slope-Intercept Form", "Slope & Rate of Change", "Proportional Relationships"]},
            {"id": "8-g", "name": "Geometry", "topics": ["Transformations", "Congruence", "Similarity", "Pythagorean Theorem", "Volume of Cylinders/Cones/Spheres", "Surface Area", "Coordinate Geometry"]},
            {"id": "8-sp", "name": "Statistics & Probability", "topics": ["Scatter Plots", "Line of Best Fit", "Two-Way Tables", "Probability"]},
        ]
    },
}


@router.post("/generate-questions", response_model=GenerateQuestionsResponse)
async def generate_questions_for_topic(
    request: GenerateQuestionsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generate questions for a specific grade/topic/difficulty combination.

    Requires admin privileges.
    """
    verify_admin(current_user)

    # Validate inputs
    if request.grade not in ALLOWED_GRADES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid grade: {request.grade}. Allowed: {ALLOWED_GRADES}"
        )

    if request.difficulty not in ALLOWED_DIFFICULTIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid difficulty: {request.difficulty}. Allowed: {ALLOWED_DIFFICULTIES}"
        )

    if request.topic not in ALL_TOPICS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid topic: {request.topic}"
        )

    if request.count < 1 or request.count > 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Count must be between 1 and 50"
        )

    # Generate questions using existing service
    from app.services.quiz_generator import generate_quiz_with_ollama, store_question

    quiz_data = await generate_quiz_with_ollama(
        grade=request.grade,
        topic=request.topic,
        difficulty=request.difficulty,
        count=request.count
    )

    if not quiz_data or not quiz_data.get('questions'):
        return GenerateQuestionsResponse(
            success=False,
            generated_count=0,
            message="Failed to generate questions"
        )

    # Store each question
    generated_count = 0
    for question in quiz_data['questions']:
        try:
            await store_question(db, request.grade, request.topic, request.difficulty, question)
            generated_count += 1
        except Exception as e:
            logger.error(f"Failed to store question: {e}")
            continue

    await db.commit()

    return GenerateQuestionsResponse(
        success=True,
        generated_count=generated_count,
        message=f"Successfully generated {generated_count} questions for {request.topic} ({request.grade}th grade, {request.difficulty})"
    )


@router.get("/topics/{grade}")
async def get_topics_by_grade(
    grade: str,
    current_user: User = Depends(get_current_user)
):
    """Get all available topics for a specific grade."""
    verify_admin(current_user)

    if grade not in ALLOWED_GRADES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid grade: {grade}"
        )

    grade_data = CURRICULUM.get(grade, {})
    topics = []

    for domain in grade_data.get('domains', []):
        for topic in domain.get('topics', []):
            topics.append({
                'id': topic,
                'name': topic,
                'domain': domain.get('name'),
                'domain_id': domain.get('id')
            })

    return {
        'grade': grade,
        'topics': topics
    }


@router.get("/question-count/{grade}/{topic}/{difficulty}")
async def get_question_count(
    grade: str,
    topic: str,
    difficulty: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get the number of questions available for a specific combination."""
    verify_admin(current_user)

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
    total_questions = 0

    for row in rows:
        questions = row.question_data.get('questions', [])
        total_questions += len(questions)

    return {
        'grade': grade,
        'topic': topic,
        'difficulty': difficulty,
        'count': total_questions
    }


@router.get("/questions/{grade}/{topic}/{difficulty}")
async def get_questions_for_topic(
    grade: str,
    topic: str,
    difficulty: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all questions for a specific grade/topic/difficulty combination.

    Requires admin privileges.
    """
    verify_admin(current_user)

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
    all_questions = []

    for row in rows:
        questions = row.question_data.get('questions', [])
        for q in questions:
            all_questions.append({
                'id': q.get('id'),
                'hash': q.get('hash'),
                'type': q.get('type'),
                'text': q.get('text'),
                'options': q.get('options'),
                'correct': q.get('correct'),
                'explanation': q.get('explanation'),
                'difficulty': q.get('difficulty'),
                'topic': q.get('topic'),
                'created_date': row.created_date.isoformat() if row.created_date else None
            })

    return {
        'grade': grade,
        'topic': topic,
        'difficulty': difficulty,
        'count': len(all_questions),
        'questions': all_questions
    }


@router.get("/health")
async def admin_health_check(
    current_user: User = Depends(get_current_user)
):
    """Health check with admin privileges."""
    verify_admin(current_user)

    from app.tasks.queue import get_all_queue_stats

    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "queues": get_all_queue_stats()
    }
