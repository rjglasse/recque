"""SQLAlchemy ORM models for recque database."""

import json
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    sessionmaker,
)

from recque_tui.config import get_config


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


class User(Base):
    """User model for future multi-user support."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    sessions: Mapped[list["LearningSession"]] = relationship(back_populates="user")
    journeys: Mapped[list["LearningJourney"]] = relationship(back_populates="created_by")
    mastery_levels: Mapped[list["TopicMastery"]] = relationship(back_populates="user")


class Topic(Base):
    """A learning topic."""
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    skills: Mapped[list["Skill"]] = relationship(back_populates="topic", cascade="all, delete-orphan")
    sessions: Mapped[list["LearningSession"]] = relationship(back_populates="topic")
    journey_steps: Mapped[list["JourneyStep"]] = relationship(back_populates="topic")
    prerequisites_for: Mapped[list["TopicPrerequisite"]] = relationship(
        foreign_keys="TopicPrerequisite.topic_id", back_populates="topic"
    )
    prerequisite_of: Mapped[list["TopicPrerequisite"]] = relationship(
        foreign_keys="TopicPrerequisite.prerequisite_topic_id", back_populates="prerequisite_topic"
    )


class Skill(Base):
    """A skill/concept within a topic."""
    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(primary_key=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sequence_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    topic: Mapped["Topic"] = relationship(back_populates="skills")
    questions: Mapped[list["CachedQuestion"]] = relationship(back_populates="skill")

    __table_args__ = (
        Index("idx_skill_topic", "topic_id"),
    )


class CachedQuestion(Base):
    """Cached AI-generated question for reuse."""
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id"))
    question_text: Mapped[str] = mapped_column(Text)
    correct_answer: Mapped[str] = mapped_column(Text)
    incorrect_answers_json: Mapped[str] = mapped_column(Text)  # JSON array
    difficulty_level: Mapped[int] = mapped_column(Integer, default=0)
    parent_question_id: Mapped[Optional[int]] = mapped_column(ForeignKey("questions.id"), nullable=True)
    prior_answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    question_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    skill: Mapped["Skill"] = relationship(back_populates="questions")
    parent_question: Mapped[Optional["CachedQuestion"]] = relationship(remote_side=[id])
    attempts: Mapped[list["QuestionAttempt"]] = relationship(back_populates="question")

    @property
    def incorrect_answers(self) -> list[str]:
        """Get incorrect answers as a list."""
        return json.loads(self.incorrect_answers_json)

    @incorrect_answers.setter
    def incorrect_answers(self, value: list[str]) -> None:
        """Set incorrect answers from a list."""
        self.incorrect_answers_json = json.dumps(value)

    __table_args__ = (
        Index("idx_question_skill", "skill_id"),
        Index("idx_question_hash", "question_hash"),
    )


class LearningSession(Base):
    """A learning session tracking user progress."""
    __tablename__ = "learning_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"))
    journey_id: Mapped[Optional[int]] = mapped_column(ForeignKey("learning_journeys.id"), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active, paused, completed, abandoned

    # Relationships
    user: Mapped["User"] = relationship(back_populates="sessions")
    topic: Mapped["Topic"] = relationship(back_populates="sessions")
    journey: Mapped[Optional["LearningJourney"]] = relationship(back_populates="sessions")
    progress: Mapped[list["SessionProgress"]] = relationship(back_populates="session", cascade="all, delete-orphan")
    attempts: Mapped[list["QuestionAttempt"]] = relationship(back_populates="session", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_session_user", "user_id"),
        Index("idx_session_status", "status"),
    )


class SessionProgress(Base):
    """Progress within a session for each skill."""
    __tablename__ = "session_progress"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("learning_sessions.id"))
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id"))
    stack_state_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array of question IDs
    skill_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    session: Mapped["LearningSession"] = relationship(back_populates="progress")
    skill: Mapped["Skill"] = relationship()

    @property
    def stack_state(self) -> list[int]:
        """Get stack state as a list of question IDs."""
        if self.stack_state_json:
            return json.loads(self.stack_state_json)
        return []

    @stack_state.setter
    def stack_state(self, value: list[int]) -> None:
        """Set stack state from a list of question IDs."""
        self.stack_state_json = json.dumps(value)

    __table_args__ = (
        Index("idx_progress_session", "session_id"),
    )


class QuestionAttempt(Base):
    """A single question attempt for analytics."""
    __tablename__ = "question_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("learning_sessions.id"))
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"))
    selected_answer: Mapped[str] = mapped_column(Text)
    is_correct: Mapped[bool] = mapped_column(Boolean)
    time_taken_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    stack_depth: Mapped[int] = mapped_column(Integer, default=0)
    attempted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    session: Mapped["LearningSession"] = relationship(back_populates="attempts")
    question: Mapped["CachedQuestion"] = relationship(back_populates="attempts")

    __table_args__ = (
        Index("idx_attempt_session", "session_id"),
        Index("idx_attempt_question", "question_id"),
    )


class LearningJourney(Base):
    """A curriculum path or learning journey."""
    __tablename__ = "learning_journeys"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_predefined: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    created_by: Mapped[Optional["User"]] = relationship(back_populates="journeys")
    steps: Mapped[list["JourneyStep"]] = relationship(back_populates="journey", cascade="all, delete-orphan")
    sessions: Mapped[list["LearningSession"]] = relationship(back_populates="journey")


class JourneyStep(Base):
    """A step (topic) within a learning journey."""
    __tablename__ = "journey_steps"

    id: Mapped[int] = mapped_column(primary_key=True)
    journey_id: Mapped[int] = mapped_column(ForeignKey("learning_journeys.id"))
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"))
    step_order: Mapped[int] = mapped_column(Integer)
    is_optional: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    journey: Mapped["LearningJourney"] = relationship(back_populates="steps")
    topic: Mapped["Topic"] = relationship(back_populates="journey_steps")

    __table_args__ = (
        Index("idx_journey_step_order", "journey_id", "step_order", unique=True),
    )


class TopicPrerequisite(Base):
    """Knowledge graph edge: topic requires prerequisite topic."""
    __tablename__ = "topic_prerequisites"

    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"), primary_key=True)
    prerequisite_topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"), primary_key=True)
    strength: Mapped[float] = mapped_column(Float, default=1.0)  # 0-1, importance of prerequisite

    # Relationships
    topic: Mapped["Topic"] = relationship(foreign_keys=[topic_id], back_populates="prerequisites_for")
    prerequisite_topic: Mapped["Topic"] = relationship(foreign_keys=[prerequisite_topic_id], back_populates="prerequisite_of")


class TopicMastery(Base):
    """User mastery level for a topic (for adaptive paths)."""
    __tablename__ = "topic_mastery"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"), primary_key=True)
    mastery_level: Mapped[float] = mapped_column(Float, default=0.0)  # 0-1 scale
    questions_answered: Mapped[int] = mapped_column(Integer, default=0)
    questions_correct: Mapped[int] = mapped_column(Integer, default=0)
    last_practiced_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="mastery_levels")
    topic: Mapped["Topic"] = relationship()

    __table_args__ = (
        Index("idx_mastery_user", "user_id"),
    )


# Database initialization
def get_engine():
    """Get the SQLAlchemy engine."""
    config = get_config()
    config.db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{config.db_path}", echo=False)


def get_session_factory():
    """Get a session factory for the database."""
    engine = get_engine()
    return sessionmaker(bind=engine)


def init_database():
    """Initialize the database schema."""
    engine = get_engine()
    Base.metadata.create_all(engine)


def get_or_create_default_user(session) -> User:
    """Get or create the default local user."""
    user = session.query(User).filter_by(username="local").first()
    if not user:
        user = User(username="local")
        session.add(user)
        session.commit()
    return user
