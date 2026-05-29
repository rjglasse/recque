"""Tests for the SessionService application service."""

from recque_tui.application import SessionService
from recque_tui.core.learning_stack import LearningStack
from recque_tui.core.models import Question
from recque_tui.database.schema import SessionProgress, Skill, Topic


class TestSessionServiceLifecycle:
    """Lifecycle: create, pause, resume, complete."""

    def test_create_session_creates_topic_and_skills(self, db_session):
        service = SessionService(db_session)
        session = service.create_session("Topic A", ["s1", "s2", "s3"])

        topic = db_session.query(Topic).filter_by(name="Topic A").one()
        skill_names = {s.name for s in topic.skills}

        assert session.topic_id == topic.id
        assert session.status == "active"
        assert skill_names == {"s1", "s2", "s3"}

    def test_create_session_reuses_existing_topic(self, db_session):
        service = SessionService(db_session)
        first = service.create_session("Reused", ["a", "b"])
        second = service.create_session("Reused", ["a", "b"])

        assert first.topic_id == second.topic_id
        skill_count = db_session.query(Skill).filter_by(topic_id=first.topic_id).count()
        assert skill_count == 2  # skills not duplicated

    def test_pause_and_resume(self, db_session):
        service = SessionService(db_session)
        session = service.create_session("Topic", ["s1"])

        service.pause_session(session)
        assert session.status == "paused"

        service.resume_session(session)
        assert session.status == "active"

    def test_complete_session(self, db_session):
        service = SessionService(db_session)
        session = service.create_session("Topic", ["s1"])

        service.complete_session(session)
        assert session.status == "completed"
        assert session.ended_at is not None


class TestSessionServiceProgress:
    """Progress save/restore preserves the learning stack."""

    def test_save_and_restore_stack(self, db_session):
        service = SessionService(db_session)
        session = service.create_session("Topic", ["skill1", "skill2"])

        stack = LearningStack()
        stack.push(Question(
            question_text="Q1?",
            correct_answer="yes",
            incorrect_answers=["no", "maybe", "nope"],
        ))

        service.save_progress(session, current_skill_index=0, stack=stack, skills=["skill1", "skill2"])

        state = service.get_session_state(session)
        assert state is not None
        assert state["topic"] == "Topic"
        assert state["current_skill_index"] == 0
        assert len(state["stack_data"]) == 1
        assert state["stack_data"][0]["question"]["question_text"] == "Q1?"

    def test_descent_depth_persists_and_restores_per_skill(self, db_session):
        service = SessionService(db_session)
        skills = ["s1", "s2", "s3"]
        session = service.create_session("Topic", skills)

        # s1 completed at column height 3 (empty stack -> completed).
        service.save_progress(session, 0, LearningStack(), skills, descent_depth=3)
        # s2 in progress at column height 2.
        stack = LearningStack()
        stack.push(Question(
            question_text="Q2?", correct_answer="y", incorrect_answers=["n", "m", "o"],
        ))
        service.save_progress(session, 1, stack, skills, descent_depth=2)

        state = service.get_session_state(session)
        assert state["current_skill_index"] == 1
        assert state["descent_depths"] == [3, 2, 0]   # s3 untouched -> 0

    def test_descent_depth_never_shrinks_on_save(self, db_session):
        service = SessionService(db_session)
        session = service.create_session("Topic", ["s1"])
        stack = LearningStack()
        stack.push(Question(question_text="Q?", correct_answer="y", incorrect_answers=["a", "b", "c"]))

        service.save_progress(session, 0, stack, ["s1"], descent_depth=3)
        service.save_progress(session, 0, stack, ["s1"], descent_depth=1)  # transient lower value

        state = service.get_session_state(session)
        assert state["descent_depths"] == [3]   # monotonic — keeps the recorded skyline

    def test_empty_stack_marks_skill_completed(self, db_session):
        service = SessionService(db_session)
        session = service.create_session("Topic", ["skill1"])

        empty_stack = LearningStack()
        service.save_progress(session, 0, empty_stack, ["skill1"])

        progress = (
            db_session.query(SessionProgress)
            .filter_by(session_id=session.id)
            .one()
        )
        assert progress.skill_completed is True
        assert progress.completed_at is not None


class TestSessionServiceQueries:
    """Read-side queries for the UI."""

    def test_resumable_sessions_includes_active_and_paused(self, db_session):
        service = SessionService(db_session)
        service.create_session("Active", ["a"])
        paused = service.create_session("Paused", ["p"])
        service.pause_session(paused)
        completed = service.create_session("Completed", ["c"])
        service.complete_session(completed)

        resumable = service.get_resumable_sessions()
        topics = {entry["topic"] for entry in resumable}
        assert "Active" in topics
        assert "Paused" in topics
        assert "Completed" not in topics

    def test_completed_sessions(self, db_session):
        service = SessionService(db_session)
        session = service.create_session("Topic", ["s1"])
        service.complete_session(session)

        completed = service.get_completed_sessions()
        assert len(completed) == 1
        assert completed[0]["topic"] == "Topic"
