"""Tests for database/schema.py."""

import json
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from recque_tui.database.schema import (
    Base,
    CachedQuestion,
    JourneyStep,
    LearningJourney,
    LearningSession,
    QuestionAttempt,
    SessionProgress,
    Skill,
    Topic,
    TopicMastery,
    TopicPrerequisite,
    User,
)


@pytest.fixture
def in_memory_db():
    """Create an in-memory database for testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestUserModel:
    """Tests for User model."""

    def test_create_user(self, in_memory_db):
        """Test creating a user."""
        user = User(username="testuser")
        in_memory_db.add(user)
        in_memory_db.commit()

        assert user.id is not None
        assert user.username == "testuser"
        assert user.created_at is not None

    def test_user_unique_username(self, in_memory_db):
        """Test username uniqueness constraint."""
        user1 = User(username="testuser")
        user2 = User(username="testuser")
        in_memory_db.add(user1)
        in_memory_db.commit()

        in_memory_db.add(user2)
        with pytest.raises(Exception):  # IntegrityError
            in_memory_db.commit()


class TestTopicModel:
    """Tests for Topic model."""

    def test_create_topic(self, in_memory_db):
        """Test creating a topic."""
        topic = Topic(name="Python Basics", description="Learn Python")
        in_memory_db.add(topic)
        in_memory_db.commit()

        assert topic.id is not None
        assert topic.name == "Python Basics"

    def test_topic_with_skills(self, in_memory_db):
        """Test topic with related skills."""
        topic = Topic(name="Python")
        in_memory_db.add(topic)
        in_memory_db.flush()

        skill1 = Skill(topic_id=topic.id, name="Variables", sequence_order=0)
        skill2 = Skill(topic_id=topic.id, name="Functions", sequence_order=1)
        in_memory_db.add_all([skill1, skill2])
        in_memory_db.commit()

        assert len(topic.skills) == 2
        assert topic.skills[0].name in ["Variables", "Functions"]


class TestSkillModel:
    """Tests for Skill model."""

    def test_create_skill(self, in_memory_db):
        """Test creating a skill."""
        topic = Topic(name="Python")
        in_memory_db.add(topic)
        in_memory_db.flush()

        skill = Skill(topic_id=topic.id, name="Variables", sequence_order=0)
        in_memory_db.add(skill)
        in_memory_db.commit()

        assert skill.id is not None
        assert skill.topic_id == topic.id


class TestCachedQuestionModel:
    """Tests for CachedQuestion model."""

    def test_create_cached_question(self, in_memory_db):
        """Test creating a cached question."""
        topic = Topic(name="Python")
        in_memory_db.add(topic)
        in_memory_db.flush()

        skill = Skill(topic_id=topic.id, name="Variables")
        in_memory_db.add(skill)
        in_memory_db.flush()

        question = CachedQuestion(
            skill_id=skill.id,
            question_text="What is a variable?",
            correct_answer="A named storage location",
            incorrect_answers_json=json.dumps(["A function", "A loop"]),
            question_hash="abc123",
        )
        in_memory_db.add(question)
        in_memory_db.commit()

        assert question.id is not None
        assert question.incorrect_answers == ["A function", "A loop"]

    def test_incorrect_answers_property(self, in_memory_db):
        """Test incorrect_answers property getter/setter."""
        topic = Topic(name="Python")
        in_memory_db.add(topic)
        in_memory_db.flush()

        skill = Skill(topic_id=topic.id, name="Variables")
        in_memory_db.add(skill)
        in_memory_db.flush()

        question = CachedQuestion(
            skill_id=skill.id,
            question_text="Test?",
            correct_answer="A",
            incorrect_answers_json="[]",
            question_hash="xyz789",
        )
        in_memory_db.add(question)

        # Test setter
        question.incorrect_answers = ["B", "C", "D"]
        in_memory_db.commit()

        # Test getter
        assert question.incorrect_answers == ["B", "C", "D"]


class TestLearningSessionModel:
    """Tests for LearningSession model."""

    def test_create_session(self, in_memory_db):
        """Test creating a learning session."""
        user = User(username="test")
        topic = Topic(name="Python")
        in_memory_db.add_all([user, topic])
        in_memory_db.flush()

        session = LearningSession(user_id=user.id, topic_id=topic.id)
        in_memory_db.add(session)
        in_memory_db.commit()

        assert session.id is not None
        assert session.status == "active"
        assert session.started_at is not None

    def test_session_status_transitions(self, in_memory_db):
        """Test session status changes."""
        user = User(username="test")
        topic = Topic(name="Python")
        in_memory_db.add_all([user, topic])
        in_memory_db.flush()

        session = LearningSession(user_id=user.id, topic_id=topic.id)
        in_memory_db.add(session)
        in_memory_db.commit()

        assert session.status == "active"

        session.status = "paused"
        in_memory_db.commit()
        assert session.status == "paused"

        session.status = "completed"
        session.ended_at = datetime.utcnow()
        in_memory_db.commit()
        assert session.status == "completed"
        assert session.ended_at is not None


class TestSessionProgressModel:
    """Tests for SessionProgress model."""

    def test_create_progress(self, in_memory_db):
        """Test creating session progress."""
        user = User(username="test")
        topic = Topic(name="Python")
        in_memory_db.add_all([user, topic])
        in_memory_db.flush()

        skill = Skill(topic_id=topic.id, name="Variables")
        in_memory_db.add(skill)
        in_memory_db.flush()

        session = LearningSession(user_id=user.id, topic_id=topic.id)
        in_memory_db.add(session)
        in_memory_db.flush()

        progress = SessionProgress(session_id=session.id, skill_id=skill.id)
        in_memory_db.add(progress)
        in_memory_db.commit()

        assert progress.id is not None
        assert progress.skill_completed is False

    def test_stack_state_property(self, in_memory_db):
        """Test stack_state property getter/setter."""
        user = User(username="test")
        topic = Topic(name="Python")
        in_memory_db.add_all([user, topic])
        in_memory_db.flush()

        skill = Skill(topic_id=topic.id, name="Variables")
        session = LearningSession(user_id=user.id, topic_id=topic.id)
        in_memory_db.add_all([skill, session])
        in_memory_db.flush()

        progress = SessionProgress(session_id=session.id, skill_id=skill.id)
        in_memory_db.add(progress)

        # Test setter
        progress.stack_state = [1, 2, 3]
        in_memory_db.commit()

        # Test getter
        assert progress.stack_state == [1, 2, 3]


class TestQuestionAttemptModel:
    """Tests for QuestionAttempt model."""

    def test_create_attempt(self, in_memory_db):
        """Test creating a question attempt."""
        user = User(username="test")
        topic = Topic(name="Python")
        in_memory_db.add_all([user, topic])
        in_memory_db.flush()

        skill = Skill(topic_id=topic.id, name="Variables")
        in_memory_db.add(skill)
        in_memory_db.flush()

        question = CachedQuestion(
            skill_id=skill.id,
            question_text="Test?",
            correct_answer="A",
            incorrect_answers_json="[]",
            question_hash="test123",
        )
        session = LearningSession(user_id=user.id, topic_id=topic.id)
        in_memory_db.add_all([question, session])
        in_memory_db.flush()

        attempt = QuestionAttempt(
            session_id=session.id,
            question_id=question.id,
            selected_answer="A",
            is_correct=True,
            time_taken_seconds=10,
            stack_depth=1,
        )
        in_memory_db.add(attempt)
        in_memory_db.commit()

        assert attempt.id is not None
        assert attempt.is_correct is True


class TestLearningJourneyModel:
    """Tests for LearningJourney model."""

    def test_create_journey(self, in_memory_db):
        """Test creating a learning journey."""
        journey = LearningJourney(
            name="Python Mastery",
            description="Complete Python learning path",
            is_predefined=True,
        )
        in_memory_db.add(journey)
        in_memory_db.commit()

        assert journey.id is not None
        assert journey.is_predefined is True

    def test_journey_with_steps(self, in_memory_db):
        """Test journey with topic steps."""
        topic1 = Topic(name="Python Basics")
        topic2 = Topic(name="Python Advanced")
        journey = LearningJourney(name="Python Path")
        in_memory_db.add_all([topic1, topic2, journey])
        in_memory_db.flush()

        step1 = JourneyStep(journey_id=journey.id, topic_id=topic1.id, step_order=0)
        step2 = JourneyStep(journey_id=journey.id, topic_id=topic2.id, step_order=1)
        in_memory_db.add_all([step1, step2])
        in_memory_db.commit()

        assert len(journey.steps) == 2


class TestTopicPrerequisiteModel:
    """Tests for TopicPrerequisite model."""

    def test_create_prerequisite(self, in_memory_db):
        """Test creating a topic prerequisite."""
        topic1 = Topic(name="Python Basics")
        topic2 = Topic(name="Python Advanced")
        in_memory_db.add_all([topic1, topic2])
        in_memory_db.flush()

        prereq = TopicPrerequisite(
            topic_id=topic2.id,
            prerequisite_topic_id=topic1.id,
            strength=0.8,
        )
        in_memory_db.add(prereq)
        in_memory_db.commit()

        assert prereq.strength == 0.8


class TestTopicMasteryModel:
    """Tests for TopicMastery model."""

    def test_create_mastery(self, in_memory_db):
        """Test creating topic mastery."""
        user = User(username="test")
        topic = Topic(name="Python")
        in_memory_db.add_all([user, topic])
        in_memory_db.flush()

        mastery = TopicMastery(
            user_id=user.id,
            topic_id=topic.id,
            mastery_level=0.75,
            questions_answered=20,
            questions_correct=15,
        )
        in_memory_db.add(mastery)
        in_memory_db.commit()

        assert mastery.mastery_level == 0.75
        assert mastery.questions_answered == 20
