from sqlalchemy import Column, Integer, String, Date, ForeignKey, DateTime, func, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from app.database import Base


class UserProgress(Base):
    __tablename__ = "user_progress"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    topic = Column(String(255), nullable=False)
    correct_count = Column(Integer, default=0)
    total_count = Column(Integer, default=0)
    last_quiz_date = Column(Date, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="progress")

    __table_args__ = (
        UniqueConstraint('user_id', 'topic', name='uix_user_topic'),
        Index('idx_progress_user_topic', 'user_id', 'topic', postgresql_using='btree'),
    )


class UserQuizHistory(Base):
    __tablename__ = "user_quiz_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    question_hash = Column(String(32), nullable=False, index=True)
    topic = Column(String(255), nullable=False, index=True)
    was_correct = Column(Integer, nullable=False)  # 0 or 1
    time_spent = Column(Integer, default=0)  # Time in seconds
    answered_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User", back_populates="quiz_history")

    __table_args__ = (
        Index('idx_quiz_history_user_topic', 'user_id', 'topic', 'answered_at', postgresql_using='btree'),
    )