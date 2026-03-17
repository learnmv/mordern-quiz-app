from pydantic import BaseModel, ConfigDict
from typing import List, Dict, Optional, Any
from datetime import date


class TopicProgress(BaseModel):
    correct: int
    total: int
    accuracy: float
    last_quiz: Optional[date] = None


class WeakTopic(BaseModel):
    topic: str
    accuracy: float
    total: int
    streak: int = 0
    max_streak: int = 0


class StrongTopic(BaseModel):
    topic: str
    accuracy: float
    total: int
    streak: int = 0
    max_streak: int = 0


class InProgressTopic(BaseModel):
    topic: str
    accuracy: float
    total: int


class TopicStreak(BaseModel):
    current: int
    max: int


class UserStats(BaseModel):
    total_questions: int
    overall_accuracy: float
    topics_attempted: int
    active_days_week: int


class ProgressResponse(BaseModel):
    progress: Dict[str, TopicProgress]
    weak_topics: List[WeakTopic]
    strong_topics: List[StrongTopic]
    in_progress: List[InProgressTopic]
    streaks: Dict[str, TopicStreak]
    badges: List[Dict[str, Any]]
    stats: UserStats


class DifficultyRecommendation(BaseModel):
    difficulty: str