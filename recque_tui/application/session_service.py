"""Session orchestration service.

Sits between UI screens and persistence. Owns the database session lifecycle
(borrow-or-create pattern) and uses repositories for data access. Keeps UI
screens out of the SQLAlchemy query layer and gives one canonical path for
session create / pause / resume / progress.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING

from recque_tui.core.learning_stack import LearningStack
from recque_tui.database.repositories import SessionRepository, TopicRepository
from recque_tui.database.schema import (
    LearningSession,
    SessionProgress,
    Skill,
    Topic,
    get_session_factory,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session as DBSession


class SessionService:
    """Application service for learning-session lifecycle and progress."""

    def __init__(self, db_session: "DBSession | None" = None):
        if db_session is not None:
            self._db = db_session
            self._owns_session = False
        else:
            factory = get_session_factory()
            self._db = factory()
            self._owns_session = True

        self._topics = TopicRepository(self._db)
        self._sessions = SessionRepository(self._db)

    def __enter__(self) -> "SessionService":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._owns_session:
            if exc_type:
                self._db.rollback()
            self._db.close()

    # ------------------------------------------------------------------ create

    def create_session(
        self,
        topic_name: str,
        skills: list[str],
        journey_id: int | None = None,
    ) -> LearningSession:
        """Create a new learning session, creating topic + skills if absent."""
        topic = self._topics.get_or_create(topic_name)

        if not topic.skills:
            self._topics.save_skills(topic, skills)

        return self._sessions.create(topic, journey_id=journey_id)

    # ------------------------------------------------------------------ progress

    def save_progress(
        self,
        session: LearningSession,
        current_skill_index: int,
        stack: LearningStack,
        skills: list[str],
    ) -> None:
        """Persist the learner's current position and stack for resume."""
        topic = self._db.get(Topic, session.topic_id)
        if not topic:
            return

        skill_name = skills[current_skill_index]
        skill = (
            self._db.query(Skill)
            .filter_by(topic_id=topic.id, name=skill_name)
            .first()
        )
        if not skill:
            skill = Skill(
                topic_id=topic.id,
                name=skill_name,
                sequence_order=current_skill_index,
            )
            self._db.add(skill)
            self._db.flush()

        progress = (
            self._db.query(SessionProgress)
            .filter_by(session_id=session.id, skill_id=skill.id)
            .first()
        )
        if not progress:
            progress = SessionProgress(session_id=session.id, skill_id=skill.id)
            self._db.add(progress)

        progress.stack_state_json = json.dumps(stack.to_dict())
        progress.skill_completed = stack.is_empty
        if progress.skill_completed:
            progress.completed_at = datetime.utcnow()

        self._db.commit()

    # ------------------------------------------------------------------ lifecycle

    def pause_session(self, session: LearningSession) -> None:
        self._sessions.pause(session)

    def resume_session(self, session: LearningSession) -> None:
        self._sessions.resume(session)

    def complete_session(self, session: LearningSession) -> None:
        self._sessions.complete(session)

    # ------------------------------------------------------------------ queries

    def get_resumable_sessions(self) -> list[dict]:
        """Return active + paused sessions enriched with topic and skill progress."""
        sessions = self._sessions.get_active() + self._sessions.get_paused()
        sessions.sort(key=lambda s: s.started_at, reverse=True)

        result = []
        for session in sessions:
            topic = self._db.get(Topic, session.topic_id)
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
        """Reconstruct the resume payload (skills + current index + stack data)."""
        topic = self._db.get(Topic, session.topic_id)
        if not topic:
            return None

        skills = (
            self._db.query(Skill)
            .filter_by(topic_id=topic.id)
            .order_by(Skill.sequence_order)
            .all()
        )

        current_skill_index = 0
        stack_data: list[dict] = []

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
        from recque_tui.database.schema import get_or_create_default_user

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
            topic = self._db.get(Topic, session.topic_id)
            result.append({
                "id": session.id,
                "topic": topic.name if topic else "Unknown",
                "started_at": session.started_at,
                "ended_at": session.ended_at,
            })
        return result
