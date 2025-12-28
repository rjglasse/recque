"""Tests for domain modules."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from recque_tui.core.models import Question
from recque_tui.core.learning_stack import LearningStack


class TestSessionManager:
    """Tests for SessionManager class."""

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session."""
        with patch('recque_tui.domain.journey.get_session_factory') as mock_factory:
            mock_session = MagicMock()
            mock_factory.return_value = MagicMock(return_value=mock_session)
            mock_session.__enter__ = MagicMock(return_value=mock_session)
            mock_session.__exit__ = MagicMock(return_value=None)
            yield mock_session

    def test_session_manager_context(self, mock_db_session):
        """Test SessionManager as context manager."""
        from recque_tui.domain.journey import SessionManager

        with patch('recque_tui.domain.journey.get_session_factory') as mock_factory:
            mock_session = MagicMock()
            mock_factory.return_value = MagicMock(return_value=mock_session)

            with SessionManager() as manager:
                assert manager is not None


class TestKnowledgeGraph:
    """Tests for KnowledgeGraph class."""

    def test_get_learning_path_empty(self):
        """Test getting path for non-existent topic."""
        from recque_tui.domain.knowledge_graph import KnowledgeGraph

        with patch('recque_tui.domain.knowledge_graph.get_session_factory') as mock_factory:
            mock_session = MagicMock()
            mock_factory.return_value = MagicMock(return_value=mock_session)
            mock_session.__enter__ = MagicMock(return_value=mock_session)
            mock_session.__exit__ = MagicMock(return_value=None)
            mock_session.query.return_value.filter_by.return_value.first.return_value = None

            kg = KnowledgeGraph()
            path = kg.get_learning_path("Unknown Topic")

            assert path == ["Unknown Topic"]


class TestAnalytics:
    """Tests for Analytics class."""

    def test_get_overall_metrics_empty(self):
        """Test overall metrics with no data."""
        from recque_tui.domain.analytics import Analytics

        with patch('recque_tui.domain.analytics.get_session_factory') as mock_factory:
            mock_session = MagicMock()
            mock_factory.return_value = MagicMock(return_value=mock_session)
            mock_session.__enter__ = MagicMock(return_value=mock_session)
            mock_session.__exit__ = MagicMock(return_value=None)

            # Mock user
            mock_user = MagicMock()
            mock_user.id = 1

            # Setup query chains
            mock_session.query.return_value.filter_by.return_value.count.return_value = 0
            mock_session.query.return_value.join.return_value.filter.return_value.all.return_value = []

            with patch('recque_tui.domain.analytics.get_or_create_default_user', return_value=mock_user):
                analytics = Analytics()
                metrics = analytics.get_overall_metrics()

                assert metrics.total_questions == 0
                assert metrics.total_sessions == 0
                assert metrics.accuracy == 0

    def test_streak_info_empty(self):
        """Test streak info with no sessions."""
        from recque_tui.domain.analytics import Analytics

        with patch('recque_tui.domain.analytics.get_session_factory') as mock_factory:
            mock_session = MagicMock()
            mock_factory.return_value = MagicMock(return_value=mock_session)
            mock_session.__enter__ = MagicMock(return_value=mock_session)
            mock_session.__exit__ = MagicMock(return_value=None)

            mock_user = MagicMock()
            mock_user.id = 1
            mock_session.query.return_value.filter_by.return_value.order_by.return_value.all.return_value = []

            with patch('recque_tui.domain.analytics.get_or_create_default_user', return_value=mock_user):
                analytics = Analytics()
                streak = analytics.get_streak_info()

                assert streak["current_streak"] == 0
                assert streak["longest_streak"] == 0
                assert streak["total_days"] == 0


class TestLearningCurve:
    """Tests for LearningCurve dataclass."""

    def test_create_learning_curve(self):
        """Test creating a LearningCurve."""
        from recque_tui.domain.analytics import LearningCurve

        curve = LearningCurve(
            date=datetime.now(),
            accuracy=0.8,
            questions_count=10,
            cumulative_accuracy=0.75,
        )

        assert curve.accuracy == 0.8
        assert curve.questions_count == 10


class TestPerformanceMetrics:
    """Tests for PerformanceMetrics dataclass."""

    def test_create_performance_metrics(self):
        """Test creating PerformanceMetrics."""
        from recque_tui.domain.analytics import PerformanceMetrics

        metrics = PerformanceMetrics(
            total_questions=100,
            correct_answers=80,
            accuracy=0.8,
            avg_time_seconds=15.5,
            avg_stack_depth=1.2,
            total_sessions=10,
            completed_sessions=8,
            topics_studied=5,
        )

        assert metrics.total_questions == 100
        assert metrics.accuracy == 0.8
        assert metrics.topics_studied == 5


class TestTopicMetrics:
    """Tests for TopicMetrics dataclass."""

    def test_create_topic_metrics(self):
        """Test creating TopicMetrics."""
        from recque_tui.domain.analytics import TopicMetrics

        metrics = TopicMetrics(
            topic_name="Python",
            questions_answered=50,
            correct_answers=40,
            accuracy=0.8,
            mastery_level=0.75,
            avg_stack_depth=1.5,
            time_spent_seconds=3600,
            last_practiced=datetime.now(),
        )

        assert metrics.topic_name == "Python"
        assert metrics.mastery_level == 0.75


class TestTopicNode:
    """Tests for TopicNode dataclass."""

    def test_create_topic_node(self):
        """Test creating a TopicNode."""
        from recque_tui.domain.knowledge_graph import TopicNode

        node = TopicNode(
            id=1,
            name="Python Basics",
            mastery_level=0.6,
            prerequisites=[],
            is_ready=True,
        )

        assert node.name == "Python Basics"
        assert node.is_ready is True
