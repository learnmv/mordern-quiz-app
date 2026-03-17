import json
import hashlib
import httpx
import logging
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from datetime import date

from app.config import settings
from app.models.quiz import TopicQuestion, CompleteQuiz, QuizRequest

logger = logging.getLogger(__name__)


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


async def get_cached_question(
    db: AsyncSession,
    grade: str,
    topic: str,
    difficulty: str,
    answered_hashes: List[str]
) -> Optional[Dict[str, Any]]:
    """Get a cached question for the topic/difficulty, excluding already answered"""
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

    if not all_questions:
        return None

    # Filter out already answered questions
    answered_set = set(answered_hashes) if answered_hashes else set()
    fresh_questions = [q for q in all_questions if q.get('hash') not in answered_set]

    if not fresh_questions:
        return None

    import random
    return random.choice(fresh_questions)


async def store_question(
    db: AsyncSession,
    grade: str,
    topic: str,
    difficulty: str,
    question: Dict[str, Any]
) -> None:
    """Store a single question for caching"""
    if 'hash' not in question:
        question['hash'] = generate_question_hash(question.get('text', ''))

    today = date.today()

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
        q_hash = question.get('hash')
        exists = any(q.get('hash') == q_hash for q in questions)

        if not exists:
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


async def generate_quiz_with_ollama(
    grade: str,
    topic: str,
    difficulty: str,
    count: int = 1,
    answered_hashes: List[str] = None
) -> Optional[Dict[str, Any]]:
    """Generate quiz questions using Ollama API"""

    personalization_context = ""
    if answered_hashes:
        personalization_context = f"\n\nIMPORTANT: Do NOT generate questions similar to these (already answered): {answered_hashes[:10]}"

    if difficulty == "easy":
        personalization_context += "\n\nMake questions EASIER - focus on basic concepts, simpler numbers."
    elif difficulty == "hard":
        personalization_context += "\n\nMake questions HARDER - multi-step problems, complex reasoning."

    prompt = f"""Create exactly {count} math question{'s' if count > 1 else ''} for {grade}th grade California Common Core standards.
Topic: {topic}{personalization_context}

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

        payload = {
            "model": settings.ollama_model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.7,
                "num_predict": 8000,
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

        return quiz_data

    except Exception as e:
        logger.error(f"Error generating quiz: {e}")
        return None


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
DIAGRAM_TOPICS = [
    "Area of Polygons", "Volume of Prisms", "Surface Area",
    "Coordinate Plane", "Coordinate Plane Polygons", "Number Line",
    "Dot Plots", "Histograms", "Box Plots"
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
- Label all five key values"""
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