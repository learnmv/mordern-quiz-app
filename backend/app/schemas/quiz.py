from pydantic import BaseModel, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import date, datetime


class Question(BaseModel):
    id: int
    type: str
    text: str
    options: List[str]
    correct: List[str]
    explanation: str
    hash: Optional[str] = None
    topic: Optional[str] = None


class QuizRequest(BaseModel):
    grade: str = "6"
    topics: Optional[List[str]] = None
    count: int = 1


class QuizResponse(BaseModel):
    questions: List[Question]


class TopicStats(BaseModel):
    topic: str
    count: int


class PopularCombination(BaseModel):
    grade: str
    topics: List[str]
    difficulty: str
    count: int


class GradeStats(BaseModel):
    by_grade: Dict[str, Dict[str, int]]
    by_difficulty: Dict[str, int]


class DailyStats(BaseModel):
    topic_questions_today: int
    complete_quizzes_today: int
    requests_today: int
    by_source: Dict[str, int]


class AnswerSubmission(BaseModel):
    question_hash: str
    topic: str
    was_correct: bool
    time_spent: int = 0


class AnswerResponse(BaseModel):
    success: bool


class WeakTopicsQuizRequest(BaseModel):
    pass  # No fields needed, uses user's weak topics


class WeakTopicsQuizResponse(BaseModel):
    weak_topics: List[Dict[str, Any]]
    message: str


# Diagram-related schemas
class DiagramSpec(BaseModel):
    """Specification for a diagram to be rendered"""
    type: str  # "coordinate", "chart", "svg", "geometric"
    data: Dict[str, Any]  # Diagram-specific data (coordinates, chart config, SVG paths, etc.)
    width: int = 400
    height: int = 300


class DiagramQuestion(Question):
    """Question with optional diagram"""
    diagram: Optional[DiagramSpec] = None
    requires_canvas: bool = False  # If user needs to draw/interact on the diagram


class DiagramQuizRequest(BaseModel):
    """Request for generating a diagram-based quiz"""
    grade: str
    topic: str  # Specific topic requiring diagram
    difficulty: str = "medium"
    count: int = 1


class DiagramQuizResponse(BaseModel):
    """Response with diagram questions"""
    questions: List[DiagramQuestion]