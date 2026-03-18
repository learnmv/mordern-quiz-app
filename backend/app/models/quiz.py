from sqlalchemy import Column, Integer, String, Date, ForeignKey, Text, DateTime, func, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.database import Base


class TopicQuestion(Base):
    __tablename__ = "topic_questions"

    id = Column(Integer, primary_key=True, index=True)
    grade = Column(String(10), nullable=False, index=True)
    topic = Column(String(255), nullable=False, index=True)
    difficulty = Column(String(20), nullable=False, index=True)
    question_data = Column(JSONB, nullable=False)
    created_date = Column(Date, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        # Unique constraint matching the original SQLite schema
        UniqueConstraint('grade', 'topic', 'difficulty', 'created_date', name='uix_topic_question'),
        # Composite index for efficient cache lookups
        Index('idx_topic_lookup', 'grade', 'topic', 'difficulty', 'created_date', postgresql_using='btree'),
    )


class CompleteQuiz(Base):
    __tablename__ = "complete_quizzes"

    id = Column(Integer, primary_key=True, index=True)
    grade = Column(String(10), nullable=False, index=True)
    difficulty = Column(String(20), nullable=False, index=True)
    topics_hash = Column(String(500), nullable=False, index=True)
    question_data = Column(JSONB, nullable=False)
    created_date = Column(Date, nullable=False, index=True)
    use_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        # Unique constraint matching the original SQLite schema
        UniqueConstraint('grade', 'difficulty', 'topics_hash', 'created_date', name='uix_complete_quiz'),
    )


class QuizRequest(Base):
    __tablename__ = "quiz_requests"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    grade = Column(String(10), nullable=True)
    topics = Column(JSONB, nullable=True)
    difficulty = Column(String(20), nullable=True)
    request_date = Column(Date, nullable=True, index=True)
    served_from = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User", back_populates="quiz_requests")