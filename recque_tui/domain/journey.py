"""Learning journey and session management."""

import json
from datetime import datetime
from typing import TYPE_CHECKING

from recque_tui.core.learning_stack import LearningStack
from recque_tui.core.models import Question
from recque_tui.database.schema import (
    LearningSession,
    SessionProgress,
    Skill,
    Topic,
    User,
    get_or_create_default_user,
    get_session_factory,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session as DBSession


class SessionManager:
    """Manages learning sessions for persistence and resume."""

    def __init__(self, db_session: "DBSession | None" = None):
        """Initialize session manager.

        Args:
            db_session: SQLAlchemy session. If None, creates a new one.
        """
        if db_session:
            self._db = db_session
            self._owns_session = False
        else:
            factory = get_session_factory()
            self._db = factory()
            self._owns_session = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._owns_session:
            if exc_type:
                self._db.rollback()
            self._db.close()

    def create_session(
        self,
        topic_name: str,
        skills: list[str],
        journey_id: int | None = None,
    ) -> LearningSession:
        """Create a new learning session.

        Args:
            topic_name: The topic being learned.
            skills: List of skill names for the topic.
            journey_id: Optional journey this session is part of.

        Returns:
            The created LearningSession.
        """
        user = get_or_create_default_user(self._db)

        # Get or create topic
        topic = self._db.query(Topic).filter_by(name=topic_name).first()
        if not topic:
            topic = Topic(name=topic_name)
            self._db.add(topic)
            self._db.flush()

            # Add skills
            for i, skill_name in enumerate(skills):
                skill = Skill(topic_id=topic.id, name=skill_name, sequence_order=i)
                self._db.add(skill)

        # Create session
        session = LearningSession(
            user_id=user.id,
            topic_id=topic.id,
            journey_id=journey_id,
            status="active",
        )
        self._db.add(session)
        self._db.commit()

        return session

    def save_progress(
        self,
        session: LearningSession,
        current_skill_index: int,
        stack: LearningStack,
        skills: list[str],
    ) -> None:
        """Save current progress for a session.

        Args:
            session: The learning session.
            current_skill_index: Index of current skill.
            stack: The current learning stack.
            skills: List of skill names.
        """
        # Get or create the skill
        topic = self._db.query(Topic).get(session.topic_id)
        if not topic:
            return

        skill = (
            self._db.query(Skill)
            .filter_by(topic_id=topic.id, name=skills[current_skill_index])
            .first()
        )

        if not skill:
            skill = Skill(
                topic_id=topic.id,
                name=skills[current_skill_index],
                sequence_order=current_skill_index,
            )
            self._db.add(skill)
            self._db.flush()

        # Find or create progress entry
        progress = (
            self._db.query(SessionProgress)
            .filter_by(session_id=session.id, skill_id=skill.id)
            .first()
        )

        if not progress:
            progress = SessionProgress(session_id=session.id, skill_id=skill.id)
            self._db.add(progress)

        # Serialize stack state
        progress.stack_state_json = json.dumps(stack.to_dict())
        progress.skill_completed = stack.is_empty

        if progress.skill_completed:
            progress.completed_at = datetime.utcnow()

        self._db.commit()

    def pause_session(self, session: LearningSession) -> None:
        """Pause a session for later resumption.

        Args:
            session: The session to pause.
        """
        session.status = "paused"
        self._db.commit()

    def resume_session(self, session: LearningSession) -> None:
        """Resume a paused session.

        Args:
            session: The session to resume.
        """
        session.status = "active"
        self._db.commit()

    def complete_session(self, session: LearningSession) -> None:
        """Mark a session as completed.

        Args:
            session: The session to complete.
        """
        session.status = "completed"
        session.ended_at = datetime.utcnow()
        self._db.commit()

    def get_resumable_sessions(self) -> list[dict]:
        """Get all sessions that can be resumed.

        Returns:
            List of session info dicts.
        """
        user = get_or_create_default_user(self._db)

        sessions = (
            self._db.query(LearningSession)
            .filter(
                LearningSession.user_id == user.id,
                LearningSession.status.in_(["active", "paused"]),
            )
            .order_by(LearningSession.started_at.desc())
            .all()
        )

        result = []
        for session in sessions:
            topic = self._db.query(Topic).get(session.topic_id)

            # Get progress info
            progress_entries = (
                self._db.query(SessionProgress)
                .filter_by(session_id=session.id)
                .all()
            )
            skills_completed = sum(1 for p in progress_entries if p.skill_completed)
            total_skills = len(topic.skills) if topic else 0

            result.append({
                "id": session.id,
                "topic": topic.name if topic else "Unknown",
                "status": session.status,
                "started_at": session.started_at,
                "skills_completed": skills_completed,
                "total_skills": total_skills,
                "session": session,
            })

        return result

    def get_session_state(self, session: LearningSession) -> dict | None:
        """Get the saved state for resuming a session.

        Args:
            session: The session to get state for.

        Returns:
            Dict with session state or None if no state saved.
        """
        topic = self._db.query(Topic).get(session.topic_id)
        if not topic:
            return None

        # Get skills in order
        skills = (
            self._db.query(Skill)
            .filter_by(topic_id=topic.id)
            .order_by(Skill.sequence_order)
            .all()
        )

        # Find current skill (first incomplete)
        current_skill_index = 0
        stack_data = []

        for i, skill in enumerate(skills):
            progress = (
                self._db.query(SessionProgress)
                .filter_by(session_id=session.id, skill_id=skill.id)
                .first()
            )

            if progress:
                if not progress.skill_completed:
                    current_skill_index = i
                    if progress.stack_state_json:
                        stack_data = json.loads(progress.stack_state_json)
                    break
            else:
                current_skill_index = i
                break

        return {
            "topic": topic.name,
            "skills": [s.name for s in skills],
            "current_skill_index": current_skill_index,
            "stack_data": stack_data,
        }

    def get_completed_sessions(self, limit: int = 10) -> list[dict]:
        """Get recently completed sessions.

        Args:
            limit: Maximum number of sessions to return.

        Returns:
            List of session info dicts.
        """
        user = get_or_create_default_user(self._db)

        sessions = (
            self._db.query(LearningSession)
            .filter_by(user_id=user.id, status="completed")
            .order_by(LearningSession.ended_at.desc())
            .limit(limit)
            .all()
        )

        result = []
        for session in sessions:
            topic = self._db.query(Topic).get(session.topic_id)
            result.append({
                "id": session.id,
                "topic": topic.name if topic else "Unknown",
                "started_at": session.started_at,
                "ended_at": session.ended_at,
            })

        return result
