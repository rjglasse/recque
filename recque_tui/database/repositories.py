"""Data access layer for recque database."""

import json
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from recque_tui.core.models import Question as QuestionModel
from recque_tui.database.schema import (
    CachedQuestion,
    LearningJourney,
    LearningSession,
    QuestionAttempt,
    SessionProgress,
    Skill,
    Topic,
    TopicMastery,
    TopicPrerequisite,
    User,
    get_or_create_default_user,
    get_session_factory,
    init_database,
)


class BaseRepository:
    """Base class for repositories with session management."""

    def __init__(self, session: Session | None = None):
        """Initialize with an optional session.

        Args:
            session: SQLAlchemy session. If None, creates a new one.
        """
        if session:
            self._session = session
            self._owns_session = False
        else:
            factory = get_session_factory()
            self._session = factory()
            self._owns_session = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._owns_session:
            if exc_type:
                self._session.rollback()
            self._session.close()

    def commit(self):
        """Commit the current transaction."""
        self._session.commit()

    def rollback(self):
        """Rollback the current transaction."""
        self._session.rollback()


class TopicRepository(BaseRepository):
    """Repository for Topic operations."""

    def get_or_create(self, name: str, description: str | None = None) -> Topic:
        """Get an existing topic or create a new one.

        Args:
            name: The topic name.
            description: Optional description.

        Returns:
            The Topic object.
        """
        topic = self._session.query(Topic).filter_by(name=name).first()
        if not topic:
            topic = Topic(name=name, description=description)
            self._session.add(topic)
            self._session.commit()
        return topic

    def get_by_id(self, topic_id: int) -> Topic | None:
        """Get a topic by ID."""
        return self._session.query(Topic).get(topic_id)

    def get_all(self) -> list[Topic]:
        """Get all topics."""
        return self._session.query(Topic).all()

    def save_skills(self, topic: Topic, skill_names: list[str]) -> list[Skill]:
        """Save skills for a topic.

        Args:
            topic: The topic.
            skill_names: List of skill names.

        Returns:
            List of Skill objects.
        """
        skills = []
        for i, name in enumerate(skill_names):
            skill = Skill(
                topic_id=topic.id,
                name=name,
                sequence_order=i,
            )
            self._session.add(skill)
            skills.append(skill)
        self._session.commit()
        return skills


class QuestionRepository(BaseRepository):
    """Repository for cached question operations."""

    def get_by_hash(self, question_hash: str) -> QuestionModel | None:
        """Get a cached question by its hash.

        Args:
            question_hash: The question hash.

        Returns:
            A Question model if found, None otherwise.
        """
        cached = self._session.query(CachedQuestion).filter_by(
            question_hash=question_hash
        ).first()

        if cached:
            return QuestionModel(
                question_text=cached.question_text,
                correct_answer=cached.correct_answer,
                incorrect_answers=cached.incorrect_answers,
            )
        return None

    def save(
        self,
        question: QuestionModel,
        skill_name: str,
        question_hash: str,
        skill_id: int | None = None,
        parent_question_id: int | None = None,
        prior_answer: str | None = None,
        difficulty_level: int = 0,
    ) -> CachedQuestion:
        """Save a question to the cache.

        Args:
            question: The Question model.
            skill_name: Name of the skill (used if skill_id not provided).
            question_hash: The unique hash for this question.
            skill_id: Optional skill ID.
            parent_question_id: ID of the parent question (for simpler variations).
            prior_answer: The incorrect answer that led to this question.
            difficulty_level: Difficulty level (0=base, negative=simpler, positive=harder).

        Returns:
            The CachedQuestion object.
        """
        # Check if already exists
        existing = self._session.query(CachedQuestion).filter_by(
            question_hash=question_hash
        ).first()
        if existing:
            return existing

        # Create skill if needed
        if not skill_id:
            # Try to find skill by name or create a placeholder
            skill = self._session.query(Skill).filter_by(name=skill_name).first()
            if skill:
                skill_id = skill.id
            else:
                # Create a placeholder skill under a placeholder topic
                topic = self._session.query(Topic).filter_by(name="_uncategorized").first()
                if not topic:
                    topic = Topic(name="_uncategorized", description="Uncategorized questions")
                    self._session.add(topic)
                    self._session.flush()

                skill = Skill(topic_id=topic.id, name=skill_name)
                self._session.add(skill)
                self._session.flush()
                skill_id = skill.id

        cached = CachedQuestion(
            skill_id=skill_id,
            question_text=question.question_text,
            correct_answer=question.correct_answer,
            incorrect_answers_json=json.dumps(question.incorrect_answers),
            question_hash=question_hash,
            parent_question_id=parent_question_id,
            prior_answer=prior_answer,
            difficulty_level=difficulty_level,
        )
        self._session.add(cached)
        self._session.commit()
        return cached

    def get_by_skill(self, skill_id: int, limit: int = 10) -> list[CachedQuestion]:
        """Get cached questions for a skill.

        Args:
            skill_id: The skill ID.
            limit: Maximum number of questions to return.

        Returns:
            List of CachedQuestion objects.
        """
        return (
            self._session.query(CachedQuestion)
            .filter_by(skill_id=skill_id)
            .limit(limit)
            .all()
        )


class SessionRepository(BaseRepository):
    """Repository for learning session operations."""

    def create(
        self,
        topic: Topic,
        user: User | None = None,
        journey_id: int | None = None,
    ) -> LearningSession:
        """Create a new learning session.

        Args:
            topic: The topic being learned.
            user: The user (defaults to local user).
            journey_id: Optional journey this session is part of.

        Returns:
            The LearningSession object.
        """
        if not user:
            user = get_or_create_default_user(self._session)

        session = LearningSession(
            user_id=user.id,
            topic_id=topic.id,
            journey_id=journey_id,
        )
        self._session.add(session)
        self._session.commit()
        return session

    def get_active(self, user: User | None = None) -> list[LearningSession]:
        """Get active (resumable) sessions.

        Args:
            user: The user (defaults to local user).

        Returns:
            List of active LearningSession objects.
        """
        if not user:
            user = get_or_create_default_user(self._session)

        return (
            self._session.query(LearningSession)
            .filter_by(user_id=user.id, status="active")
            .order_by(LearningSession.started_at.desc())
            .all()
        )

    def get_paused(self, user: User | None = None) -> list[LearningSession]:
        """Get paused sessions that can be resumed.

        Args:
            user: The user (defaults to local user).

        Returns:
            List of paused LearningSession objects.
        """
        if not user:
            user = get_or_create_default_user(self._session)

        return (
            self._session.query(LearningSession)
            .filter_by(user_id=user.id, status="paused")
            .order_by(LearningSession.started_at.desc())
            .all()
        )

    def pause(self, session: LearningSession) -> None:
        """Pause a session for later resumption."""
        session.status = "paused"
        self._session.commit()

    def resume(self, session: LearningSession) -> None:
        """Resume a paused session."""
        session.status = "active"
        self._session.commit()

    def complete(self, session: LearningSession) -> None:
        """Mark a session as completed."""
        session.status = "completed"
        session.ended_at = datetime.utcnow()
        self._session.commit()

    def abandon(self, session: LearningSession) -> None:
        """Mark a session as abandoned."""
        session.status = "abandoned"
        session.ended_at = datetime.utcnow()
        self._session.commit()

    def save_progress(
        self,
        session: LearningSession,
        skill: Skill,
        stack_state: list[int],
        completed: bool = False,
    ) -> SessionProgress:
        """Save or update progress for a skill within a session.

        Args:
            session: The learning session.
            skill: The current skill.
            stack_state: List of question IDs in the stack.
            completed: Whether the skill is completed.

        Returns:
            The SessionProgress object.
        """
        progress = (
            self._session.query(SessionProgress)
            .filter_by(session_id=session.id, skill_id=skill.id)
            .first()
        )

        if not progress:
            progress = SessionProgress(
                session_id=session.id,
                skill_id=skill.id,
            )
            self._session.add(progress)

        progress.stack_state = stack_state
        progress.skill_completed = completed
        if completed:
            progress.completed_at = datetime.utcnow()

        self._session.commit()
        return progress


class ProgressRepository(BaseRepository):
    """Repository for analytics and progress tracking."""

    def record_attempt(
        self,
        session: LearningSession,
        question: CachedQuestion,
        selected_answer: str,
        is_correct: bool,
        time_taken: int | None = None,
        stack_depth: int = 0,
    ) -> QuestionAttempt:
        """Record a question attempt.

        Args:
            session: The learning session.
            question: The question being answered.
            selected_answer: The user's answer.
            is_correct: Whether the answer was correct.
            time_taken: Time in seconds to answer.
            stack_depth: Current stack depth.

        Returns:
            The QuestionAttempt object.
        """
        attempt = QuestionAttempt(
            session_id=session.id,
            question_id=question.id,
            selected_answer=selected_answer,
            is_correct=is_correct,
            time_taken_seconds=time_taken,
            stack_depth=stack_depth,
        )
        self._session.add(attempt)
        self._session.commit()
        return attempt

    def update_mastery(
        self,
        user: User,
        topic: Topic,
        is_correct: bool,
    ) -> TopicMastery:
        """Update mastery level after an attempt.

        Args:
            user: The user.
            topic: The topic.
            is_correct: Whether the answer was correct.

        Returns:
            The updated TopicMastery object.
        """
        mastery = (
            self._session.query(TopicMastery)
            .filter_by(user_id=user.id, topic_id=topic.id)
            .first()
        )

        if not mastery:
            mastery = TopicMastery(
                user_id=user.id,
                topic_id=topic.id,
                questions_answered=0,
                questions_correct=0,
                mastery_level=0.0,
            )
            self._session.add(mastery)

        mastery.questions_answered += 1
        if is_correct:
            mastery.questions_correct += 1

        # Simple mastery calculation: accuracy with recency boost
        if mastery.questions_answered > 0:
            mastery.mastery_level = mastery.questions_correct / mastery.questions_answered

        mastery.last_practiced_at = datetime.utcnow()
        self._session.commit()
        return mastery

    def get_accuracy_by_topic(self, user: User) -> dict[str, float]:
        """Get accuracy rates by topic.

        Args:
            user: The user.

        Returns:
            Dict mapping topic names to accuracy rates.
        """
        results = {}
        masteries = (
            self._session.query(TopicMastery)
            .filter_by(user_id=user.id)
            .all()
        )

        for m in masteries:
            topic = self._session.query(Topic).get(m.topic_id)
            if topic and m.questions_answered > 0:
                results[topic.name] = m.questions_correct / m.questions_answered

        return results

    def get_session_stats(self, session: LearningSession) -> dict:
        """Get statistics for a session.

        Args:
            session: The learning session.

        Returns:
            Dict with session statistics.
        """
        attempts = session.attempts
        total = len(attempts)
        correct = sum(1 for a in attempts if a.is_correct)
        avg_time = (
            sum(a.time_taken_seconds for a in attempts if a.time_taken_seconds)
            / total
            if total > 0
            else 0
        )
        max_depth = max((a.stack_depth for a in attempts), default=0)

        return {
            "total_questions": total,
            "correct_answers": correct,
            "accuracy": correct / total if total > 0 else 0,
            "average_time_seconds": avg_time,
            "max_stack_depth": max_depth,
        }


class JourneyRepository(BaseRepository):
    """Repository for learning journey operations."""

    def create(
        self,
        name: str,
        description: str | None = None,
        is_predefined: bool = False,
        user: User | None = None,
    ) -> LearningJourney:
        """Create a new learning journey.

        Args:
            name: Journey name.
            description: Optional description.
            is_predefined: Whether this is a curated journey.
            user: The creator (for custom journeys).

        Returns:
            The LearningJourney object.
        """
        journey = LearningJourney(
            name=name,
            description=description,
            is_predefined=is_predefined,
            created_by_user_id=user.id if user else None,
        )
        self._session.add(journey)
        self._session.commit()
        return journey

    def get_all(self) -> list[LearningJourney]:
        """Get all journeys."""
        return self._session.query(LearningJourney).all()

    def get_predefined(self) -> list[LearningJourney]:
        """Get predefined (curated) journeys."""
        return (
            self._session.query(LearningJourney)
            .filter_by(is_predefined=True)
            .all()
        )

    def add_step(
        self,
        journey: LearningJourney,
        topic: Topic,
        order: int,
        is_optional: bool = False,
    ) -> None:
        """Add a topic step to a journey.

        Args:
            journey: The journey.
            topic: The topic to add.
            order: The step order (0-indexed).
            is_optional: Whether this step is optional.
        """
        from recque_tui.database.schema import JourneyStep

        step = JourneyStep(
            journey_id=journey.id,
            topic_id=topic.id,
            step_order=order,
            is_optional=is_optional,
        )
        self._session.add(step)
        self._session.commit()


def initialize_database():
    """Initialize the database and create default data."""
    init_database()

    # Create default user
    factory = get_session_factory()
    with factory() as session:
        get_or_create_default_user(session)
