from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import List, Optional, Dict, Any
from datetime import date, datetime
import re

# Allowed values
ALLOWED_GRADES = ["6", "7", "8"]
ALLOWED_DIFFICULTIES = ["easy", "medium", "hard"]
ALLOWED_QUESTION_TYPES = ["single_choice", "multiple_choice"]
ALLOWED_TOPICS = [
    "Unit Rates", "Ratios", "Percentages", "Ratio Reasoning",
    "Fractions", "Decimals", "Negative Numbers", "GCF", "LCM",
    "Absolute Value", "Number Line", "Coordinate Plane",
    "Variables", "Writing Expressions", "One-Step Equations",
    "One-Step Inequalities", "Evaluating Expressions",
    "Order of Operations", "Equivalent Expressions",
    "Area of Polygons", "Volume of Prisms", "Surface Area",
    "Coordinate Plane Polygons",
    "Statistical Questions", "Mean", "Median", "Mode", "Range",
    "Dot Plots", "Histograms", "Box Plots",
    "Systems of Equations", "Proportional Relationships",
    "Multi-Step Equations"
]

DIAGRAM_TOPICS = [
    "Area of Polygons", "Volume of Prisms", "Surface Area",
    "Coordinate Plane", "Coordinate Plane Polygons", "Number Line",
    "Dot Plots", "Histograms", "Box Plots"
]


class Question(BaseModel):
    """Quiz question model with validation."""
    model_config = ConfigDict(strict=False)

    id: int = Field(..., ge=1, description="Question ID starting from 1")
    type: str = Field(..., description="Question type")
    text: str = Field(..., min_length=10, max_length=2000, description="Question text")
    options: List[str] = Field(
        ...,
        min_length=4,
        max_length=4,
        description="Four answer options"
    )
    correct: List[str] = Field(
        ...,
        min_length=1,
        description="Correct answer(s)"
    )
    explanation: str = Field(
        ...,
        min_length=20,
        max_length=5000,
        description="Explanation of the answer"
    )
    hash: Optional[str] = Field(
        None,
        pattern=r"^[a-f0-9]{16}$",
        description="MD5 hash of question text (first 16 chars)"
    )
    topic: Optional[str] = Field(None, description="Topic of the question")
    difficulty: Optional[str] = Field(
        None,
        description="Difficulty level"
    )
    thinking: Optional[str] = Field(
        None,
        description="Step-by-step thinking for complex problems"
    )

    @field_validator('type')
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in ALLOWED_QUESTION_TYPES:
            raise ValueError(f"Invalid question type. Must be one of: {ALLOWED_QUESTION_TYPES}")
        return v

    @field_validator('difficulty')
    @classmethod
    def validate_difficulty(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ALLOWED_DIFFICULTIES:
            raise ValueError(f"Invalid difficulty. Must be one of: {ALLOWED_DIFFICULTIES}")
        return v

    @field_validator('topic')
    @classmethod
    def validate_topic(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ALLOWED_TOPICS:
            raise ValueError(f"Invalid topic. Must be one of: {ALLOWED_TOPICS}")
        return v


class QuizRequest(BaseModel):
    """Quiz generation request with validation."""
    model_config = ConfigDict(strict=False)

    grade: str = Field(
        default="6",
        pattern=r"^[6-8]$",
        description="Grade level (6-8)"
    )
    topics: Optional[List[str]] = Field(
        default=None,
        max_length=10,
        description="List of topics to include"
    )
    count: int = Field(
        default=1,
        ge=1,
        le=20,
        description="Number of questions to generate (1-20)"
    )

    @field_validator('topics')
    @classmethod
    def validate_topics(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is not None:
            for topic in v:
                if topic not in ALLOWED_TOPICS:
                    raise ValueError(f"Invalid topic: {topic}. Must be one of: {ALLOWED_TOPICS}")
        return v


class QuizResponse(BaseModel):
    """Quiz generation response."""
    model_config = ConfigDict(strict=False)

    questions: List[Question]


class TopicStats(BaseModel):
    """Topic statistics."""
    model_config = ConfigDict(strict=False)

    topic: str
    count: int = Field(..., ge=0)


class PopularCombination(BaseModel):
    """Popular quiz combination."""
    model_config = ConfigDict(strict=False)

    grade: str
    topics: List[str]
    difficulty: str
    count: int = Field(..., ge=0)


class GradeStats(BaseModel):
    """Grade distribution statistics."""
    model_config = ConfigDict(strict=False)

    by_grade: Dict[str, Dict[str, int]]
    by_difficulty: Dict[str, int]


class DailyStats(BaseModel):
    """Daily statistics."""
    model_config = ConfigDict(strict=False)

    topic_questions_today: int = Field(..., ge=0)
    complete_quizzes_today: int = Field(..., ge=0)
    requests_today: int = Field(..., ge=0)
    by_source: Dict[str, int]


class AnswerSubmission(BaseModel):
    """Answer submission with validation."""
    model_config = ConfigDict(strict=False)

    question_hash: str = Field(
        ...,
        pattern=r"^[a-f0-9]{16}$",
        description="MD5 hash of question text (16 hex characters)"
    )
    topic: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="Topic of the question"
    )
    was_correct: bool = Field(..., description="Whether the answer was correct")
    time_spent: int = Field(
        default=0,
        ge=0,
        le=3600,
        description="Time spent on question in seconds (max 1 hour)"
    )

    @field_validator('topic')
    @classmethod
    def validate_topic(cls, v: str) -> str:
        if v not in ALLOWED_TOPICS:
            raise ValueError(f"Invalid topic. Must be one of: {ALLOWED_TOPICS}")
        return v


class AnswerResponse(BaseModel):
    """Answer submission response."""
    model_config = ConfigDict(strict=False)

    success: bool


class WeakTopicsQuizRequest(BaseModel):
    """Request for weak topics quiz."""
    model_config = ConfigDict(strict=False)

    pass  # No fields needed, uses user's weak topics


class WeakTopicsQuizResponse(BaseModel):
    """Response for weak topics quiz."""
    model_config = ConfigDict(strict=False)

    weak_topics: List[Dict[str, Any]]
    message: str = Field(..., min_length=1, max_length=500)


# Diagram-related schemas
class DiagramSpec(BaseModel):
    """Specification for a diagram to be rendered."""
    model_config = ConfigDict(strict=False)

    type: str = Field(
        ...,
        pattern=r"^(coordinate|chart|svg|geometric)$",
        description="Type of diagram"
    )
    data: Dict[str, Any] = Field(
        ...,
        description="Diagram-specific data"
    )
    width: int = Field(default=400, ge=100, le=2000)
    height: int = Field(default=300, ge=100, le=2000)


class DiagramQuestion(Question):
    """Question with optional diagram."""
    model_config = ConfigDict(strict=False)

    diagram: Optional[DiagramSpec] = None
    requires_canvas: bool = Field(
        default=False,
        description="If user needs to draw/interact on the diagram"
    )


class DiagramQuizRequest(BaseModel):
    """Request for generating a diagram-based quiz."""
    model_config = ConfigDict(strict=False)

    grade: str = Field(
        ...,
        pattern=r"^[6-8]$",
        description="Grade level (6-8)"
    )
    topic: str = Field(
        ...,
        description="Specific topic requiring diagram"
    )
    difficulty: str = Field(
        default="medium",
        pattern=r"^(easy|medium|hard)$",
        description="Difficulty level"
    )
    count: int = Field(
        default=1,
        ge=1,
        le=10,
        description="Number of questions (1-10)"
    )

    @field_validator('topic')
    @classmethod
    def validate_diagram_topic(cls, v: str) -> str:
        if v not in DIAGRAM_TOPICS:
            raise ValueError(f"Topic '{v}' does not support diagrams. Choose from: {DIAGRAM_TOPICS}")
        return v


class DiagramQuizResponse(BaseModel):
    """Response with diagram questions."""
    model_config = ConfigDict(strict=False)

    questions: List[DiagramQuestion]


class QuizStreamRequest(BaseModel):
    """Request for streaming quiz generation."""
    model_config = ConfigDict(strict=False)

    grade: str = Field(
        ...,
        pattern=r"^[6-8]$",
        description="Grade level (6-8)"
    )
    topic: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="Math topic"
    )
    difficulty: str = Field(
        default="medium",
        pattern=r"^(easy|medium|hard)$",
        description="Difficulty level"
    )
    count: int = Field(
        default=1,
        ge=1,
        le=5,
        description="Number of questions (1-5 for streaming)"
    )

    @field_validator('topic')
    @classmethod
    def validate_topic(cls, v: str) -> str:
        if v not in ALLOWED_TOPICS:
            raise ValueError(f"Invalid topic. Must be one of: {ALLOWED_TOPICS}")
        return v
