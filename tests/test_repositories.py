"""Tests for database/repositories.py."""

import json
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from recque_tui.core.models import Question as QuestionModel
from recque_tui.database.schema import (
    Base,
    CachedQuestion,
    LearningJourney,
    LearningSession,
    Skill,
    Topic,
    TopicMastery,
    User,
)
from recque_tui.database.repositories import (
    JourneyRepository,
    ProgressRepository,
    QuestionRepository,
    SessionRepository,
    TopicRepository,
)


@pytest.fixture
def in_memory_engine():
    """Create an in-memory database engine."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def db_session(in_memory_engine):
    """Create a test database session."""
    Session = sessionmaker(bind=in_memory_engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def test_user(db_session):
    """Create a test user."""
    user = User(username="test_user")
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def test_topic(db_session):
    """Create a test topic with skills."""
    topic = Topic(name="Python Basics", description="Learn Python")
    db_session.add(topic)
    db_session.flush()

    skills = [
        Skill(topic_id=topic.id, name="Variables", sequence_order=0),
        Skill(topic_id=topic.id, name="Functions", sequence_order=1),
        Skill(topic_id=topic.id, name="Classes", sequence_order=2),
    ]
    db_session.add_all(skills)
    db_session.commit()
    return topic


class TestTopicRepository:
    """Tests for TopicRepository."""

    def test_get_or_create_new(self, db_session):
        """Test creating a new topic."""
        repo = TopicRepository(db_session)
        topic = repo.get_or_create("New Topic", "A new topic")

        assert topic.id is not None
        assert topic.name == "New Topic"
        assert topic.description == "A new topic"

    def test_get_or_create_existing(self, db_session, test_topic):
        """Test getting an existing topic."""
        repo = TopicRepository(db_session)
        topic = repo.get_or_create("Python Basics")

        assert topic.id == test_topic.id
        assert topic.name == "Python Basics"

    def test_get_by_id(self, db_session, test_topic):
        """Test getting topic by ID."""
        repo = TopicRepository(db_session)
        topic = repo.get_by_id(test_topic.id)

        assert topic is not None
        assert topic.name == "Python Basics"

    def test_get_by_id_not_found(self, db_session):
        """Test getting non-existent topic."""
        repo = TopicRepository(db_session)
        topic = repo.get_by_id(999)

        assert topic is None

    def test_get_all(self, db_session, test_topic):
        """Test getting all topics."""
        repo = TopicRepository(db_session)

        # Add another topic
        topic2 = Topic(name="JavaScript")
        db_session.add(topic2)
        db_session.commit()

        topics = repo.get_all()
        assert len(topics) == 2

    def test_save_skills(self, db_session, test_topic):
        """Test saving skills for a topic."""
        repo = TopicRepository(db_session)

        # Create a new topic without skills
        new_topic = Topic(name="New Topic")
        db_session.add(new_topic)
        db_session.commit()

        skills = repo.save_skills(new_topic, ["Skill 1", "Skill 2"])

        assert len(skills) == 2
        assert skills[0].name == "Skill 1"
        assert skills[1].sequence_order == 1


class TestQuestionRepository:
    """Tests for QuestionRepository."""

    def test_get_by_hash_not_found(self, db_session):
        """Test getting question by hash when not found."""
        repo = QuestionRepository(db_session)
        question = repo.get_by_hash("nonexistent_hash")

        assert question is None

    def test_save_and_get(self, db_session, test_topic):
        """Test saving and retrieving a question."""
        repo = QuestionRepository(db_session)

        question_model = QuestionModel(
            question_text="What is a variable?",
            correct_answer="A named storage location",
            incorrect_answers=["A function", "A loop"],
        )

        # Get skill
        skill = db_session.query(Skill).filter_by(topic_id=test_topic.id).first()

        cached = repo.save(
            question_model,
            skill_name=skill.name,
            question_hash="test_hash_123",
            skill_id=skill.id,
        )

        assert cached.id is not None
        assert cached.question_hash == "test_hash_123"

        # Retrieve by hash
        retrieved = repo.get_by_hash("test_hash_123")
        assert retrieved is not None
        assert retrieved.question_text == "What is a variable?"

    def test_save_duplicate_hash(self, db_session, test_topic):
        """Test saving question with duplicate hash returns existing."""
        repo = QuestionRepository(db_session)
        skill = db_session.query(Skill).filter_by(topic_id=test_topic.id).first()

        question_model = QuestionModel(
            question_text="Question 1",
            correct_answer="A",
            incorrect_answers=["B"],
        )

        # Save first time
        cached1 = repo.save(
            question_model,
            skill_name=skill.name,
            question_hash="dup_hash",
            skill_id=skill.id,
        )

        # Save again with same hash
        cached2 = repo.save(
            question_model,
            skill_name=skill.name,
            question_hash="dup_hash",
            skill_id=skill.id,
        )

        assert cached1.id == cached2.id

    def test_get_by_skill(self, db_session, test_topic):
        """Test getting questions by skill."""
        repo = QuestionRepository(db_session)
        skill = db_session.query(Skill).filter_by(topic_id=test_topic.id).first()

        # Add some questions
        for i in range(3):
            q = CachedQuestion(
                skill_id=skill.id,
                question_text=f"Question {i}",
                correct_answer="A",
                incorrect_answers_json=json.dumps(["B", "C"]),
                question_hash=f"hash_{i}",
            )
            db_session.add(q)
        db_session.commit()

        questions = repo.get_by_skill(skill.id, limit=10)
        assert len(questions) == 3


class TestSessionRepository:
    """Tests for SessionRepository."""

    def test_create_session(self, db_session, test_user, test_topic):
        """Test creating a learning session."""
        repo = SessionRepository(db_session)

        # Manually set up user lookup since we're not using the real default
        session = LearningSession(
            user_id=test_user.id,
            topic_id=test_topic.id,
        )
        db_session.add(session)
        db_session.commit()

        assert session.id is not None
        assert session.status == "active"

    def test_pause_session(self, db_session, test_user, test_topic):
        """Test pausing a session."""
        repo = SessionRepository(db_session)

        session = LearningSession(
            user_id=test_user.id,
            topic_id=test_topic.id,
        )
        db_session.add(session)
        db_session.commit()

        repo.pause(session)

        assert session.status == "paused"

    def test_resume_session(self, db_session, test_user, test_topic):
        """Test resuming a session."""
        repo = SessionRepository(db_session)

        session = LearningSession(
            user_id=test_user.id,
            topic_id=test_topic.id,
            status="paused",
        )
        db_session.add(session)
        db_session.commit()

        repo.resume(session)

        assert session.status == "active"

    def test_complete_session(self, db_session, test_user, test_topic):
        """Test completing a session."""
        repo = SessionRepository(db_session)

        session = LearningSession(
            user_id=test_user.id,
            topic_id=test_topic.id,
        )
        db_session.add(session)
        db_session.commit()

        repo.complete(session)

        assert session.status == "completed"
        assert session.ended_at is not None

    def test_abandon_session(self, db_session, test_user, test_topic):
        """Test abandoning a session."""
        repo = SessionRepository(db_session)

        session = LearningSession(
            user_id=test_user.id,
            topic_id=test_topic.id,
        )
        db_session.add(session)
        db_session.commit()

        repo.abandon(session)

        assert session.status == "abandoned"
        assert session.ended_at is not None


class TestProgressRepository:
    """Tests for ProgressRepository."""

    def test_update_mastery(self, db_session, test_user, test_topic):
        """Test updating mastery level."""
        repo = ProgressRepository(db_session)

        # First update
        mastery = repo.update_mastery(test_user, test_topic, is_correct=True)
        assert mastery.questions_answered == 1
        assert mastery.questions_correct == 1
        assert mastery.mastery_level == 1.0

        # Second update (incorrect)
        mastery = repo.update_mastery(test_user, test_topic, is_correct=False)
        assert mastery.questions_answered == 2
        assert mastery.questions_correct == 1
        assert mastery.mastery_level == 0.5

    def test_get_accuracy_by_topic(self, db_session, test_user, test_topic):
        """Test getting accuracy by topic."""
        repo = ProgressRepository(db_session)

        # Add mastery data
        mastery = TopicMastery(
            user_id=test_user.id,
            topic_id=test_topic.id,
            questions_answered=10,
            questions_correct=8,
            mastery_level=0.8,
        )
        db_session.add(mastery)
        db_session.commit()

        accuracy = repo.get_accuracy_by_topic(test_user)
        assert "Python Basics" in accuracy
        assert accuracy["Python Basics"] == 0.8


class TestJourneyRepository:
    """Tests for JourneyRepository."""

    def test_create_journey(self, db_session):
        """Test creating a journey."""
        repo = JourneyRepository(db_session)

        journey = repo.create(
            name="Python Path",
            description="Learn Python step by step",
            is_predefined=True,
        )

        assert journey.id is not None
        assert journey.name == "Python Path"
        assert journey.is_predefined is True

    def test_get_all(self, db_session):
        """Test getting all journeys."""
        repo = JourneyRepository(db_session)

        repo.create(name="Journey 1")
        repo.create(name="Journey 2")

        journeys = repo.get_all()
        assert len(journeys) == 2

    def test_get_predefined(self, db_session):
        """Test getting only predefined journeys."""
        repo = JourneyRepository(db_session)

        repo.create(name="Predefined", is_predefined=True)
        repo.create(name="Custom", is_predefined=False)

        predefined = repo.get_predefined()
        assert len(predefined) == 1
        assert predefined[0].name == "Predefined"

    def test_add_step(self, db_session, test_topic):
        """Test adding a step to a journey."""
        repo = JourneyRepository(db_session)

        journey = repo.create(name="Test Journey")
        repo.add_step(journey, test_topic, order=0)

        assert len(journey.steps) == 1
        assert journey.steps[0].topic_id == test_topic.id
