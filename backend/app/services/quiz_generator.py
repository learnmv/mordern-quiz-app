import json
import hashlib
import httpx
import logging
import time
from typing import List, Optional, Dict, Any, AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from datetime import date

from app.config import settings
from app.models.quiz import TopicQuestion, CompleteQuiz, QuizRequest
from app.utils.cache import get_cache_stats

logger = logging.getLogger(__name__)

# JSON Schema for strict question validation
QUESTION_SCHEMA = {
    "type": "object",
    "properties": {
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "type": {"type": "string", "enum": ["single_choice", "multiple_choice"]},
                    "text": {"type": "string", "minLength": 10},
                    "options": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 4,
                        "maxItems": 4
                    },
                    "correct": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1
                    },
                    "explanation": {"type": "string", "minLength": 20},
                    "difficulty": {"type": "string", "enum": ["easy", "medium", "hard"]},
                    "topic": {"type": "string"}
                },
                "required": ["id", "type", "text", "options", "correct", "explanation"]
            }
        }
    },
    "required": ["questions"]
}

# Topics that benefit from thinking mode
COMPLEX_TOPICS = [
    "Systems of Equations",
    "Proportional Relationships",
    "Multi-Step Equations",
    "Surface Area",
    "Volume of Prisms",
]

# Session-based keep_alive management
_active_sessions: Dict[str, float] = {}

# Cache hit/miss counters for monitoring
class CacheMetrics:
    """Simple cache metrics tracking."""
    def __init__(self):
        self.hits = 0
        self.misses = 0

    def hit(self):
        self.hits += 1

    def miss(self):
        self.misses += 1

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    def to_dict(self) -> dict:
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": self.hit_rate,
            "total": self.hits + self.misses
        }

# Global cache metrics
_cache_metrics = CacheMetrics()


def get_cache_metrics() -> dict:
    """Get current cache metrics."""
    return _cache_metrics.to_dict()


def reset_cache_metrics() -> None:
    """Reset cache metrics."""
    _cache_metrics.hits = 0
    _cache_metrics.misses = 0


ALL_TOPICS = [
    "Unit Rates", "Ratios", "Percentages", "Ratio Reasoning",
    "Fractions", "Decimals", "Negative Numbers", "GCF", "LCM",
    "Absolute Value", "Number Line", "Coordinate Plane",
    "Variables", "Writing Expressions", "One-Step Equations",
    "One-Step Inequalities", "Evaluating Expressions",
    "Order of Operations", "Equivalent Expressions",
    "Area of Polygons", "Volume of Prisms", "Surface Area",
    "Coordinate Plane Polygons",
    "Statistical Questions", "Mean", "Median", "Mode", "Range",
    "Dot Plots", "Histograms", "Box Plots"
]


def generate_question_hash(question_text: str) -> str:
    """Generate a hash for question repeat detection"""
    return hashlib.md5(question_text.encode()).hexdigest()[:16]


def get_topic_hash(topics: List[str]) -> str:
    """Generate a hash for a list of topics"""
    sorted_topics = sorted(topics)
    return '+'.join(sorted_topics)


async def get_or_generate_questions(
    db: AsyncSession,
    grade: str,
    topic: str,
    difficulty: str,
    needed: int = 1,
    answered_hashes: List[str] = None
) -> List[Dict[str, Any]]:
    """Get cached questions or generate new ones in batch.

    Args:
        needed: Number of questions needed
        answered_hashes: Hashes of already-answered questions to exclude

    Returns:
        List of question dictionaries
    """
    from datetime import timedelta

    # Try cache first - get up to 'needed' questions
    seven_days_ago = date.today() - timedelta(days=7)
    result = await db.execute(
        select(TopicQuestion).where(
            and_(
                TopicQuestion.grade == grade,
                TopicQuestion.topic == topic,
                TopicQuestion.difficulty == difficulty,
                TopicQuestion.created_date >= seven_days_ago
            )
        )
    )
    recent_rows = result.scalars().all()

    all_questions = []
    for row in recent_rows:
        questions = row.question_data.get('questions', [])
        for q in questions:
            if 'hash' not in q:
                q['hash'] = generate_question_hash(q.get('text', ''))
            all_questions.append(q)

    # Filter out already answered
    answered_set = set(answered_hashes) if answered_hashes else set()
    fresh_questions = [q for q in all_questions if q.get('hash') not in answered_set]

    # If we have enough cached questions, return them
    if len(fresh_questions) >= needed:
        import random
        return random.sample(fresh_questions, needed)

    # Need to generate more - calculate how many to generate
    # Generate extra to fill cache for future requests
    to_generate = max(5, needed * 2)

    # Generate batch of questions
    quiz_data = await generate_quiz_with_ollama(
        grade, topic, difficulty, count=to_generate, answered_hashes=answered_hashes
    )

    if quiz_data and quiz_data.get('questions'):
        new_questions = quiz_data['questions']

        # Store all generated questions in cache
        for q in new_questions:
            await store_question(db, grade, topic, difficulty, q)

        # Add new questions to fresh_questions (avoiding duplicates)
        existing_hashes = {q.get('hash') for q in fresh_questions}
        for q in new_questions:
            if q.get('hash') not in existing_hashes and q.get('hash') not in answered_set:
                fresh_questions.append(q)

    return fresh_questions[:needed]


async def get_cached_question(
    db: AsyncSession,
    grade: str,
    topic: str,
    difficulty: str,
    answered_hashes: List[str],
    recent_only: bool = True
) -> Optional[Dict[str, Any]]:
    """Get a cached question for the topic/difficulty, excluding already answered.

    Args:
        recent_only: If True (default), only look at questions from last 7 days.
                    Falls back to older questions if no recent ones available.
    """
    from datetime import timedelta

    seven_days_ago = date.today() - timedelta(days=7)

    # Build base query conditions
    base_conditions = [
        TopicQuestion.grade == grade,
        TopicQuestion.topic == topic,
        TopicQuestion.difficulty == difficulty
    ]

    # Try recent questions first (last 7 days)
    if recent_only:
        result = await db.execute(
            select(TopicQuestion).where(
                and_(
                    *base_conditions,
                    TopicQuestion.created_date >= seven_days_ago
                )
            )
        )
        recent_rows = result.scalars().all()

        all_questions = []
        for row in recent_rows:
            questions = row.question_data.get('questions', [])
            for q in questions:
                if 'hash' not in q:
                    q['hash'] = generate_question_hash(q.get('text', ''))
                all_questions.append(q)

        # Filter out already answered questions
        answered_set = set(answered_hashes) if answered_hashes else set()
        fresh_questions = [q for q in all_questions if q.get('hash') not in answered_set]

        if fresh_questions:
            _cache_metrics.hit()
            logger.debug(f"Cache hit for {grade}/{topic}/{difficulty}")
            import random
            return random.choice(fresh_questions)

    # Fall back to all questions (or if recent_only is False)
    result = await db.execute(
        select(TopicQuestion).where(
            and_(*base_conditions)
        )
    )
    rows = result.scalars().all()

    all_questions = []
    for row in rows:
        questions = row.question_data.get('questions', [])
        for q in questions:
            if 'hash' not in q:
                q['hash'] = generate_question_hash(q.get('text', ''))
            all_questions.append(q)

    if not all_questions:
        return None

    # Filter out already answered questions
    answered_set = set(answered_hashes) if answered_hashes else set()
    fresh_questions = [q for q in all_questions if q.get('hash') not in answered_set]

    if not fresh_questions:
        _cache_metrics.miss()
        logger.debug(f"Cache miss for {grade}/{topic}/{difficulty}")
        return None

    _cache_metrics.hit()
    logger.debug(f"Cache hit (fallback) for {grade}/{topic}/{difficulty}")
    import random
    return random.choice(fresh_questions)


async def get_pregenerated_questions(
    db: AsyncSession,
    grade: str,
    topic: str,
    difficulty: str,
    count: int = 1,
    exclude_hashes: List[str] = None
) -> List[Dict[str, Any]]:
    """Get pre-generated questions from database.

    Unlike get_cached_question, this returns ALL questions for the
    combination (not just recent), filtering out answered ones.

    Args:
        db: Database session
        grade: Grade level
        topic: Topic name
        difficulty: Difficulty level
        count: Number of questions needed
        exclude_hashes: Question hashes to exclude (already answered)

    Returns:
        List of question dictionaries
    """
    # Get all questions for this combination
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
            if 'hash' not in q:
                q['hash'] = generate_question_hash(q.get('text', ''))
            all_questions.append(q)

    # Filter out answered questions
    exclude_set = set(exclude_hashes) if exclude_hashes else set()
    available = [q for q in all_questions if q.get('hash') not in exclude_set]

    # Return up to count questions
    if len(available) > count:
        return random.sample(available, count)
    return available


async def store_question(
    db: AsyncSession,
    grade: str,
    topic: str,
    difficulty: str,
    question: Dict[str, Any]
) -> bool:
    """Store a single question for caching. Returns True if stored, False if duplicate.

    Checks for hash uniqueness across ALL date buckets to prevent duplicates.
    """
    if 'hash' not in question:
        question['hash'] = generate_question_hash(question.get('text', ''))

    q_hash = question.get('hash')
    today = date.today()

    # Check if this exact question hash exists in ANY date bucket for this grade/topic/difficulty
    result = await db.execute(
        select(TopicQuestion).where(
            and_(
                TopicQuestion.grade == grade,
                TopicQuestion.topic == topic,
                TopicQuestion.difficulty == difficulty
            )
        )
    )
    all_rows = result.scalars().all()

    for row in all_rows:
        questions = row.question_data.get('questions', [])
        if any(q.get('hash') == q_hash for q in questions):
            # Duplicate found - don't store
            return False

    # Check if entry exists for today
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

    await db.commit()
    return True


async def generate_quiz_with_ollama(
    grade: str,
    topic: str,
    difficulty: str,
    count: int = 1,
    answered_hashes: List[str] = None,
    use_thinking: bool = None,
    user_id: Optional[str] = None,
    stream: bool = False
) -> Optional[Dict[str, Any]]:
    """Generate quiz questions using Ollama API with enhanced features.

    Args:
        grade: Grade level (6-8)
        topic: Math topic
        difficulty: easy, medium, or hard
        count: Number of questions to generate
        answered_hashes: Hashes of already-answered questions to exclude
        use_thinking: Enable thinking mode (auto-detected if None)
        user_id: User ID for session-based keep_alive
        stream: If True, return AsyncGenerator for streaming
    """
    global _active_sessions

    # Auto-enable thinking for complex topics
    if use_thinking is None:
        use_thinking = topic in COMPLEX_TOPICS and difficulty in ["medium", "hard"]

    personalization_context = ""
    if answered_hashes:
        personalization_context = f"\n\nIMPORTANT: Do NOT generate questions similar to these (already answered): {answered_hashes[:10]}"

    if difficulty == "easy":
        personalization_context += "\n\nMake questions EASIER - focus on basic concepts, simpler numbers."
    elif difficulty == "hard":
        personalization_context += "\n\nMake questions HARDER - multi-step problems, complex reasoning."

    # Add thinking instructions if enabled
    thinking_instruction = ""
    if use_thinking:
        thinking_instruction = """

THINKING MODE: Show your reasoning process for solving this problem step by step.
Include your thinking in the 'thinking' field of each question."""

    prompt = f"""Create exactly {count} math question{'s' if count > 1 else ''} for {grade}th grade California Common Core standards.
Topic: {topic}{personalization_context}{thinking_instruction}

CRITICAL INSTRUCTIONS:
1. You MUST complete all {count} question{'s' if count > 1 else ''} - do not stop early
2. Be creative - use real-world scenarios and fun contexts
3. RETURN ONLY valid JSON, no markdown

Required JSON format:
{{
  "questions": [
    {{"id": 1, "type": "single_choice", "text": "...", "options": ["A...", "B...", "C...", "D..."], "correct": ["B"], "explanation": "..."}}{"," + chr(10) + "    " + chr(123) + '"id": 2, "type": "single_choice", "text": "...", "options": ["A...", "B...", "C...", "D..."], "correct": ["A"], "explanation": "..."}' if count >= 2 else ""}{"," + chr(10) + "    " + chr(123) + '"id": 3, "type": "single_choice", "text": "...", "options": ["A...", "B...", "C...", "D..."], "correct": ["D"], "explanation": "..."}' if count >= 3 else ""}{"," + chr(10) + "    " + chr(123) + '"id": 4, "type": "single_choice", "text": "...", "options": ["A...", "B...", "C...", "D..."], "correct": ["C"], "explanation": "..."}' if count >= 4 else ""}{"," + chr(10) + "    " + chr(123) + '"id": 5, "type": "single_choice", "text": "...", "options": ["A...", "B...", "C...", "D..."], "correct": ["B"], "explanation": "..."}' if count >= 5 else ""}{"," + chr(10) + "    " + chr(123) + '"id": 6, "type": "single_choice", "text": "...", "options": ["A...", "B...", "C...", "D..."], "correct": ["A"], "explanation": "..."}' if count >= 6 else ""}
  ]
}}"""

    try:
        headers = {'Content-Type': 'application/json'}
        if settings.ollama_api_key:
            headers['Authorization'] = f'Bearer {settings.ollama_api_key}'

        ollama_url = f"{settings.ollama_base_url}/api/generate"
        if settings.ollama_base_url.endswith('/api'):
            ollama_url = f"{settings.ollama_base_url}/generate"

        # Determine keep_alive based on session activity
        keep_alive = "5m"  # Default 5 minutes
        if user_id:
            last_activity = _active_sessions.get(user_id)
            if last_activity and (time.time() - last_activity) < 300:  # Active in last 5 min
                keep_alive = "30m"  # Extend for active users
            _active_sessions[user_id] = time.time()

        payload = {
            "model": settings.ollama_model,
            "prompt": prompt,
            "stream": stream,
            "format": QUESTION_SCHEMA if not stream else "json",
            "keep_alive": keep_alive,
            "options": {
                "temperature": 0.7,
                "num_predict": 10000 if use_thinking else 8000,
                "num_ctx": 131072,
                "num_gpu": 99,
                "main_gpu": 0
            }
        }

        # Add thinking parameter if enabled (Ollama API extension)
        if use_thinking:
            payload["think"] = "medium"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                ollama_url,
                headers=headers,
                json=payload,
                timeout=300.0
            )

        if response.status_code != 200:
            logger.error(f"Ollama error {response.status_code}: {response.text[:500]}")
            return None

        result = response.json()
        response_text = result.get('response', '')

        # Parse JSON response
        cleaned = response_text.strip()

        # Remove BOM or other invisible characters
        while cleaned and (cleaned[0] < ' ' or cleaned[0] == '\ufeff'):
            cleaned = cleaned[1:]

        # Find JSON start and end
        start = cleaned.find('{')
        end = cleaned.rfind('}') + 1

        if start >= 0 and end > start:
            cleaned = cleaned[start:end]
            quiz_data = json.loads(cleaned)
        else:
            raise ValueError("No JSON found in response")

        # Validate
        if not isinstance(quiz_data.get('questions'), list):
            raise ValueError("Missing questions array")

        questions = quiz_data['questions']
        if len(questions) != count:
            raise ValueError(f"Expected {count} questions, got {len(questions)}")

        # Add question hashes and topic
        for i, q in enumerate(questions):
            q['hash'] = generate_question_hash(q.get('text', ''))
            q['topic'] = topic
            # Store thinking if present
            if use_thinking and 'thinking' in result:
                q['thinking'] = result.get('thinking')

        return quiz_data

    except Exception as e:
        logger.error(f"Error generating quiz: {e}")
        return None


async def generate_quiz_stream(
    grade: str,
    topic: str,
    difficulty: str,
    count: int = 1
) -> AsyncGenerator[str, None]:
    """Stream quiz generation progress using Server-Sent Events.

    Args:
        grade: Grade level
        topic: Math topic
        difficulty: easy, medium, or hard
        count: Number of questions to generate

    Yields:
        SSE formatted strings with progress updates
    """
    try:
        headers = {'Content-Type': 'application/json'}
        if settings.ollama_api_key:
            headers['Authorization'] = f'Bearer {settings.ollama_api_key}'

        ollama_url = f"{settings.ollama_base_url}/api/generate"
        if settings.ollama_base_url.endswith('/api'):
            ollama_url = f"{settings.ollama_base_url}/generate"

        prompt = f"""Create exactly {count} math question{'s' if count > 1 else ''} for {grade}th grade.
Topic: {topic}
Difficulty: {difficulty}

Return valid JSON with questions array."""

        payload = {
            "model": settings.ollama_model,
            "prompt": prompt,
            "stream": True,
            "format": QUESTION_SCHEMA,
            "options": {
                "temperature": 0.7,
                "num_predict": 8000,
                "num_ctx": 131072,
            }
        }

        accumulated_response = ""
        total_tokens = 0

        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                ollama_url,
                headers=headers,
                json=payload,
                timeout=300.0
            ) as response:
                if response.status_code != 200:
                    error_msg = await response.aread()
                    yield f"data: {json.dumps({'error': f'Ollama error: {response.status_code}'})}\n\n"
                    return

                async for line in response.aiter_lines():
                    if not line:
                        continue

                    try:
                        data = json.loads(line)

                        # Accumulate response text
                        if 'response' in data:
                            accumulated_response += data['response']

                        # Calculate progress based on tokens
                        if 'eval_count' in data:
                            total_tokens = data['eval_count']
                            progress = min(100, int((total_tokens / 8000) * 100))
                            yield f"data: {json.dumps({'progress': progress, 'tokens': total_tokens})}\n\n"

                        # Check if complete
                        if data.get('done'):
                            # Parse final response
                            try:
                                start = accumulated_response.find('{')
                                end = accumulated_response.rfind('}') + 1
                                if start >= 0 and end > start:
                                    quiz_data = json.loads(accumulated_response[start:end])
                                    # Add hashes
                                    for q in quiz_data.get('questions', []):
                                        q['hash'] = generate_question_hash(q.get('text', ''))
                                        q['topic'] = topic
                                    yield f"data: {json.dumps({'complete': True, 'questions': quiz_data.get('questions', [])})}\n\n"
                                else:
                                    yield f"data: {json.dumps({'error': 'Invalid JSON in response'})}\n\n"
                            except json.JSONDecodeError as e:
                                yield f"data: {json.dumps({'error': f'JSON parse error: {str(e)}'})}\n\n"
                            break

                    except json.JSONDecodeError:
                        continue

    except Exception as e:
        logger.error(f"Error in stream generation: {e}")
        yield f"data: {json.dumps({'error': str(e)})}\n\n"


async def log_quiz_request(
    db: AsyncSession,
    grade: str,
    topics: List[str],
    difficulty: str,
    source: str,
    user_id: Optional[int] = None
) -> None:
    """Log a quiz request for analytics"""
    request = QuizRequest(
        user_id=user_id,
        grade=grade,
        topics=topics,
        difficulty=difficulty,
        request_date=date.today(),
        served_from=source
    )
    db.add(request)
    await db.commit()


async def get_popular_combinations(db: AsyncSession, limit: int = 20) -> List[Dict[str, Any]]:
    """Get popular quiz combinations from the last 7 days"""
    from datetime import timedelta

    seven_days_ago = date.today() - timedelta(days=7)

    result = await db.execute(
        select(
            QuizRequest.grade,
            QuizRequest.topics,
            QuizRequest.difficulty,
            func.count().label('cnt')
        ).where(
            QuizRequest.request_date >= seven_days_ago
        ).group_by(
            QuizRequest.grade,
            QuizRequest.topics,
            QuizRequest.difficulty
        ).order_by(
            func.count().desc()
        ).limit(limit)
    )

    rows = result.all()
    return [
        {
            "grade": r[0],
            "topics": r[1] if r[1] else [],
            "difficulty": r[2],
            "count": r[3]
        }
        for r in rows
    ]


async def get_stats(db: AsyncSession) -> Dict[str, Any]:
    """Get daily statistics"""
    today = date.today()

    # Topic questions today
    result = await db.execute(
        select(func.count()).select_from(TopicQuestion).where(
            TopicQuestion.created_date == today
        )
    )
    topic_questions_today = result.scalar()

    # Complete quizzes today
    result = await db.execute(
        select(func.count()).select_from(CompleteQuiz).where(
            CompleteQuiz.created_date == today
        )
    )
    complete_quizzes_today = result.scalar()

    # Requests today
    result = await db.execute(
        select(func.count()).select_from(QuizRequest).where(
            QuizRequest.request_date == today
        )
    )
    requests_today = result.scalar()

    # By source
    result = await db.execute(
        select(QuizRequest.served_from, func.count()).where(
            QuizRequest.request_date == today
        ).group_by(QuizRequest.served_from)
    )
    by_source = dict(result.all())

    return {
        "topic_questions_today": topic_questions_today,
        "complete_quizzes_today": complete_quizzes_today,
        "requests_today": requests_today,
        "by_source": by_source
    }


async def get_grade_stats(db: AsyncSession) -> Dict[str, Any]:
    """Get grade distribution statistics"""
    from datetime import timedelta

    seven_days_ago = date.today() - timedelta(days=7)

    result = await db.execute(
        select(
            QuizRequest.grade,
            QuizRequest.difficulty,
            func.count().label('cnt')
        ).where(
            QuizRequest.request_date >= seven_days_ago
        ).group_by(
            QuizRequest.grade,
            QuizRequest.difficulty
        )
    )

    by_grade = {}
    by_difficulty = {}

    for row in result.all():
        g, d, cnt = row[0], row[1], row[2]
        if g not in by_grade:
            by_grade[g] = {}
        by_grade[g][d] = cnt
        by_difficulty[d] = by_difficulty.get(d, 0) + cnt

    return {
        "by_grade": by_grade,
        "by_difficulty": by_difficulty
    }


async def get_topic_stats(db: AsyncSession) -> Dict[str, int]:
    """Get topic coverage statistics"""
    from datetime import timedelta

    seven_days_ago = date.today() - timedelta(days=7)

    result = await db.execute(
        select(
            TopicQuestion.topic,
            func.count().label('cnt')
        ).where(
            TopicQuestion.created_date >= seven_days_ago
        ).group_by(TopicQuestion.topic)
    )

    return {row[0]: row[1] for row in result.all()}


# Diagram topics that require visual representation
# Covers all grades (6, 7, 8) with grade-appropriate diagram topics
DIAGRAM_TOPICS = [
    # Grade 6 diagram topics
    "Area of Polygons", "Volume of Prisms", "Surface Area",
    "Coordinate Plane", "Coordinate Plane Polygons", "Number Line",
    "Dot Plots", "Histograms", "Box Plots",
    # Grade 7 diagram topics
    "Scale Drawings", "Drawing Geometric Shapes", "Cross-Sections",
    "Circles (Area & Circumference)", "Angles", "Area & Perimeter",
    "Volume & Surface Area", "Tree Diagrams",
    # Grade 8 diagram topics
    "Transformations", "Congruence", "Similarity", "Pythagorean Theorem",
    "Volume of Cylinders/Cones/Spheres", "Surface Area", "Coordinate Geometry",
    "Scatter Plots", "Two-Way Tables"
]


async def generate_diagram_for_question(
    question_text: str,
    topic: str,
    grade: str
) -> Optional[Dict[str, Any]]:
    """Generate diagram specs for a specific question using Ollama API.

    Args:
        question_text: The text of the question to generate a diagram for
        topic: The math topic (e.g., "Coordinate Plane", "Histograms")
        grade: The grade level (e.g., "6", "7", "8")

    Returns:
        Dictionary containing diagram data or None if generation fails
    """
    # Determine diagram type based on topic
    coordinate_topics = ["Coordinate Plane", "Coordinate Plane Polygons", "Number Line"]
    chart_topics = ["Histograms", "Dot Plots", "Box Plots"]
    geometry_topics = ["Area of Polygons", "Volume of Prisms", "Surface Area"]

    if topic in coordinate_topics:
        diagram_type = "coordinate"
        type_instructions = """For COORDINATE diagrams:
- Include grid with appropriate bounds (e.g., -10 to 10)
- Show points, lines, or shapes on the grid
- Label key points with letters and coordinates
- Include grid lines and axes"""
    elif topic in chart_topics:
        diagram_type = "chart"
        type_instructions = """For CHART diagrams:
- Specify chartType: "histogram" | "boxplot" | "dotplot"
- Include proper data configuration
- Label axes appropriately
- Include title and legend if needed"""
    elif topic in geometry_topics:
        diagram_type = "svg"
        type_instructions = """For SVG diagrams:
- Include paths for shapes with proper SVG path data
- Label dimensions clearly (length, width, height, base, etc.)
- Use appropriate colors for fills and strokes
- Show all necessary measurements"""
    else:
        diagram_type = "svg"
        type_instructions = """For general diagrams:
- Use SVG type for geometric representations
- Include clear labels and measurements
- Use appropriate colors and styling"""

    prompt = f"""Generate a diagram specification for the following {grade}th grade math question.

Question: {question_text}
Topic: {topic}

{type_instructions}

Return ONLY a JSON object with this exact structure:
{{
  "type": "{diagram_type}",
  "data": {{ /* diagram-specific data */ }},
  "width": 400,
  "height": 300
}}

For "coordinate" type, data should include:
- grid: {{"xMin": -10, "xMax": 10, "yMin": -10, "yMax": 10, "step": 1}}
- points: [{{"x": 3, "y": 4, "label": "A", "color": "red"}}]
- shapes: [{{"type": "polygon", "points": [{{"x": 0, "y": 0}}, {{"x": 4, "y": 0}}, {{"x": 4, "y": 3}}], "fill": "lightblue", "stroke": "blue"}}]
- lines: [{{"x1": 0, "y1": 0, "x2": 4, "y2": 3, "stroke": "black", "strokeWidth": 2}}]

For "chart" type, data should include:
- chartType: "histogram" | "boxplot" | "dotplot"
- config: {{ /* Chart.js compatible configuration */ }}
- options: {{ /* Chart.js compatible options */ }}

For "svg" type, data should include:
- paths: [{{"d": "M50,50 L150,50 L150,100 L50,100 Z", "fill": "lightblue", "stroke": "blue", "strokeWidth": 2}}]
- labels: [{{"x": 100, "y": 75, "text": "5 cm", "fontSize": 14, "color": "black"}}]
- shapes: [{{"type": "rect", "x": 50, "y": 50, "width": 100, "height": 50, "fill": "none", "stroke": "black"}}]

Make the diagram clear, properly labeled, and appropriate for the question difficulty."""

    try:
        headers = {'Content-Type': 'application/json'}
        if settings.ollama_api_key:
            headers['Authorization'] = f'Bearer {settings.ollama_api_key}'

        ollama_url = f"{settings.ollama_base_url}/api/generate"
        if settings.ollama_base_url.endswith('/api'):
            ollama_url = f"{settings.ollama_base_url}/generate"

        payload = {
            "model": settings.ollama_model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.7,
                "num_predict": 4000,
                "num_ctx": 131072,
                "num_gpu": 99,
                "main_gpu": 0
            }
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                ollama_url,
                headers=headers,
                json=payload,
                timeout=120.0
            )

        if response.status_code != 200:
            logger.error(f"Ollama error {response.status_code}: {response.text[:500]}")
            return None

        result = response.json()
        response_text = result.get('response', '')

        # Parse JSON response
        cleaned = response_text.strip()

        # Remove BOM or other invisible characters
        while cleaned and (cleaned[0] < ' ' or cleaned[0] == '\ufeff'):
            cleaned = cleaned[1:]

        # Find JSON start and end
        start = cleaned.find('{')
        end = cleaned.rfind('}') + 1

        if start >= 0 and end > start:
            cleaned = cleaned[start:end]
            diagram_data = json.loads(cleaned)
        else:
            raise ValueError("No JSON found in response")

        # Validate required fields
        if 'type' not in diagram_data or 'data' not in diagram_data:
            raise ValueError("Missing required fields: type and data")

        # Ensure width and height defaults
        if 'width' not in diagram_data:
            diagram_data['width'] = 400
        if 'height' not in diagram_data:
            diagram_data['height'] = 300

        return diagram_data

    except Exception as e:
        logger.error(f"Error generating diagram for question: {e}")
        return None


async def generate_diagram_quiz(
    grade: str,
    topic: str,
    difficulty: str,
    count: int = 1,
    answered_hashes: List[str] = None
) -> Optional[Dict[str, Any]]:
    """Generate diagram-based quiz questions using Ollama API"""

    personalization_context = ""
    if answered_hashes:
        personalization_context = f"\n\nIMPORTANT: Do NOT generate questions similar to these (already answered): {answered_hashes[:10]}"

    if difficulty == "easy":
        personalization_context += "\n\nMake questions EASIER - focus on basic concepts, simpler numbers."
    elif difficulty == "hard":
        personalization_context += "\n\nMake questions HARDER - multi-step problems, complex reasoning."

    # Topic-specific diagram instructions
    diagram_instructions = {
        "Area of Polygons": """
For AREA OF POLYGONS questions:
- Include a diagram showing the polygon with labeled dimensions
- Use "type": "coordinate" for polygons on coordinate plane
- Use "type": "svg" for regular geometric shapes
- Include all necessary dimensions (base, height, side lengths)""",

        "Volume of Prisms": """
For VOLUME OF PRISMS questions:
- Include a 3D diagram or 2D net of the prism
- Label dimensions: length, width, height
- Use "type": "svg" with 3D perspective drawing""",

        "Surface Area": """
For SURFACE AREA questions:
- Show the 3D shape with all faces visible or a net diagram
- Label all dimensions clearly
- Use "type": "svg" with proper 3D perspective""",

        "Coordinate Plane": """
For COORDINATE PLANE questions:
- Use "type": "coordinate"
- Include grid with appropriate bounds (e.g., -10 to 10)
- Show points, lines, or shapes on the grid
- Label key points with letters""",

        "Coordinate Plane Polygons": """
For COORDINATE PLANE POLYGONS questions:
- Use "type": "coordinate"
- Show polygon vertices on coordinate grid
- Include grid lines and axes
- Label vertices with coordinates""",

        "Number Line": """
For NUMBER LINE questions:
- Use "type": "coordinate" with y-axis hidden or minimal
- Show number line with tick marks
- Mark points, intervals, or inequalities""",

        "Dot Plots": """
For DOT PLOTS questions:
- Use "type": "chart"
- Include data values on x-axis
- Show frequency with dots stacked vertically
- Include title and labels""",

        "Histograms": """
For HISTOGRAMS questions:
- Use "type": "chart"
- Show frequency distribution with bars
- Label x-axis with intervals (e.g., "0-10", "10-20")
- Include y-axis with frequency counts""",

        "Box Plots": """
For BOX PLOTS questions:
- Use "type": "chart"
- Show minimum, Q1, median, Q3, maximum
- Display whiskers and box clearly
- Label all five key values""",

        # Grade 7 diagram topics
        "Scale Drawings": """
For SCALE DRAWINGS questions:
- Use "type": "svg" or "coordinate"
- Show the original and scaled figures
- Label the scale factor (e.g., "1:50" or "1 cm = 5 ft")
- Include measurements for both figures""",

        "Drawing Geometric Shapes": """
For DRAWING GEOMETRIC SHAPES questions:
- Use "type": "svg"
- Show the shape with proper construction lines
- Label angles, sides, and vertices
- Include compass/ruler construction marks if applicable""",

        "Cross-Sections": """
For CROSS-SECTIONS questions:
- Use "type": "svg"
- Show the 3D solid being sliced
- Show the resulting 2D cross-section shape
- Label the cutting plane""",

        "Circles (Area & Circumference)": """
For CIRCLES questions:
- Use "type": "svg"
- Show the circle with center point and radius
- Label radius, diameter, or circumference as needed
- Include grid background if helpful""",

        "Angles": """
For ANGLES questions:
- Use "type": "svg"
- Show intersecting lines, parallel lines with transversal, or angle pairs
- Label angle measures with variables or values
- Mark congruent angles and right angles""",

        "Area & Perimeter": """
For AREA & PERIMETER questions:
- Use "type": "svg" or "coordinate"
- Show the shape with labeled dimensions
- Include grid if using coordinate type
- Label all sides needed for calculation""",

        "Volume & Surface Area": """
For VOLUME & SURFACE AREA questions:
- Use "type": "svg"
- Show 3D shapes with visible faces or nets
- Label all dimensions (length, width, height, radius)
- Show formulas or component areas if helpful""",

        "Tree Diagrams": """
For TREE DIAGRAMS questions:
- Use "type": "chart"
- Show branching structure for probability
- Label each branch with outcomes and probabilities
- Include all possible paths""",

        # Grade 8 diagram topics
        "Transformations": """
For TRANSFORMATIONS questions:
- Use "type": "coordinate"
- Show original figure and transformed figure
- Label transformation type (translation, rotation, reflection, dilation)
- Show center of rotation, line of reflection, or scale factor""",

        "Congruence": """
For CONGRUENCE questions:
- Use "type": "svg" or "coordinate"
- Show two congruent figures with corresponding parts marked
- Use tick marks for equal sides, arcs for equal angles
- Label corresponding vertices""",

        "Similarity": """
For SIMILARITY questions:
- Use "type": "svg" or "coordinate"
- Show similar figures with proportional sides
- Label scale factor and corresponding angles
- Mark congruent angles""",

        "Pythagorean Theorem": """
For PYTHAGOREAN THEOREM questions:
- Use "type": "svg" or "coordinate"
- Show right triangle with legs and hypotenuse labeled
- Include square on each side if helpful
- Label known and unknown sides""",

        "Volume of Cylinders/Cones/Spheres": """
For VOLUME OF CYLINDERS/CONES/SPHERES questions:
- Use "type": "svg"
- Show 3D solid with labeled dimensions (radius, height)
- Show radius and height clearly
- Include formula hint if helpful""",

        "Coordinate Geometry": """
For COORDINATE GEOMETRY questions:
- Use "type": "coordinate"
- Show points, lines, or shapes on coordinate grid
- Label coordinates of key points
- Show slope triangles or distance calculations if needed""",

        "Scatter Plots": """
For SCATTER PLOTS questions:
- Use "type": "chart"
- Show data points on x-y coordinate system
- Include line of best fit if applicable
- Label axes with variables and units""",

        "Two-Way Tables": """
For TWO-WAY TABLES questions:
- Use "type": "chart"
- Show frequency table with rows and columns
- Label categories clearly
- Include totals in margins"""
    }

    topic_instructions = diagram_instructions.get(topic, "")

    prompt = f"""Create exactly {count} math question{'s' if count > 1 else ''} for {grade}th grade California Common Core standards.
Topic: {topic}{personalization_context}

This topic REQUIRES A DIAGRAM. Include a "diagram" field in each question with:{topic_instructions}

Diagram JSON format:
{{
  "type": "coordinate" | "chart" | "svg",
  "data": {{ /* specific to diagram type */ }},
  "width": 400,
  "height": 300
}}

For "coordinate" type, data includes:
- grid: {{"xMin": -10, "xMax": 10, "yMin": -10, "yMax": 10, "step": 1}}
- points: [{{"x": 3, "y": 4, "label": "A"}}]
- shapes: [{{"type": "polygon", "points": [{{"x": 0, "y": 0}}, ...]}}]

For "chart" type, data includes:
- chartType: "histogram" | "boxplot" | "dotplot"
- config: Chart.js configuration object
- options: Chart.js options

For "svg" type, data includes:
- paths: [{{"d": "M50,50 L150,50...", "fill": "color", "stroke": "color"}}]
- labels: [{{"x": 100, "y": 75, "text": "5 cm"}}]

CRITICAL INSTRUCTIONS:
1. You MUST complete all {count} question{'s' if count > 1 else ''} - do not stop early
2. Include the "diagram" field in EVERY question
3. Make the diagram clear and properly labeled
4. RETURN ONLY valid JSON, no markdown

Required JSON format:
{{
  "questions": [
    {{"id": 1, "type": "single_choice", "text": "...", "options": ["A...", "B...", "C...", "D..."], "correct": ["B"], "explanation": "...", "diagram": {{"type": "...", "data": {{...}}, "width": 400, "height": 300}}, "requires_canvas": false}}
  ]
}}"""

    try:
        headers = {'Content-Type': 'application/json'}
        if settings.ollama_api_key:
            headers['Authorization'] = f'Bearer {settings.ollama_api_key}'

        ollama_url = f"{settings.ollama_base_url}/api/generate"
        if settings.ollama_base_url.endswith('/api'):
            ollama_url = f"{settings.ollama_base_url}/generate"

        payload = {
            "model": settings.ollama_model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.7,
                "num_predict": 10000,  # Increased for diagram complexity
                "num_ctx": 131072,
                "num_gpu": 99,
                "main_gpu": 0
            }
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                ollama_url,
                headers=headers,
                json=payload,
                timeout=300.0
            )

        if response.status_code != 200:
            logger.error(f"Ollama error {response.status_code}: {response.text[:500]}")
            return None

        result = response.json()
        response_text = result.get('response', '')

        # Parse JSON response
        cleaned = response_text.strip()

        # Remove BOM or other invisible characters
        while cleaned and (cleaned[0] < ' ' or cleaned[0] == '\ufeff'):
            cleaned = cleaned[1:]

        # Find JSON start and end
        start = cleaned.find('{')
        end = cleaned.rfind('}') + 1

        if start >= 0 and end > start:
            cleaned = cleaned[start:end]
            quiz_data = json.loads(cleaned)
        else:
            raise ValueError("No JSON found in response")

        # Validate
        if not isinstance(quiz_data.get('questions'), list):
            raise ValueError("Missing questions array")

        questions = quiz_data['questions']
        if len(questions) != count:
            raise ValueError(f"Expected {count} questions, got {len(questions)}")

        # Add question hashes and topic
        for i, q in enumerate(questions):
            q['hash'] = generate_question_hash(q.get('text', ''))
            q['topic'] = topic
            # Ensure diagram field exists
            if 'diagram' not in q:
                q['diagram'] = None
            if 'requires_canvas' not in q:
                q['requires_canvas'] = False

        return quiz_data

    except Exception as e:
        logger.error(f"Error generating diagram quiz: {e}")
        return None