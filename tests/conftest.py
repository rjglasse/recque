"""Pytest configuration and fixtures."""

import os
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from recque_tui.database.schema import Base, User


@pytest.fixture(scope="session")
def temp_db_path():
    """Create a temporary database file for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_recque.db"
        yield db_path


@pytest.fixture
def db_engine(temp_db_path):
    """Create a test database engine."""
    engine = create_engine(f"sqlite:///{temp_db_path}", echo=False)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture
def db_session(db_engine):
    """Create a test database session."""
    Session = sessionmaker(bind=db_engine)
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
def mock_openai_response(monkeypatch):
    """Mock OpenAI API responses."""
    class MockCompletion:
        class Message:
            def __init__(self, parsed):
                self.parsed = parsed

        class Choice:
            def __init__(self, parsed):
                self.message = MockCompletion.Message(parsed)

        def __init__(self, parsed):
            self.choices = [MockCompletion.Choice(parsed)]

    class MockBeta:
        class Chat:
            class Completions:
                @staticmethod
                def parse(**kwargs):
                    response_format = kwargs.get("response_format")
                    if response_format.__name__ == "SkillMap":
                        return MockCompletion(response_format(
                            skills=["Skill 1", "Skill 2", "Skill 3"]
                        ))
                    elif response_format.__name__ == "Question":
                        return MockCompletion(response_format(
                            question_text="Test question?",
                            correct_answer="Correct",
                            incorrect_answers=["Wrong 1", "Wrong 2"]
                        ))
                    elif response_format.__name__ == "Review":
                        return MockCompletion(response_format(
                            valid=True,
                            correct_answer="Correct"
                        ))
                    return None

            completions = Completions()

        chat = Chat()

    class MockClient:
        beta = MockBeta()

    monkeypatch.setattr("recque_tui.core.ai_client.OpenAI", lambda: MockClient())
    return MockClient()
