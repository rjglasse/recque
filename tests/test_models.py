"""Tests for core/models.py."""

import pytest

from recque_tui.core.models import (
    Question,
    QuestionAttempt,
    Review,
    SessionState,
    SkillMap,
)


class TestQuestion:
    """Tests for Question model."""

    def test_create_question(self):
        """Test creating a Question instance."""
        q = Question(
            question_text="What is 2+2?",
            correct_answer="4",
            incorrect_answers=["3", "5", "6"],
        )
        assert q.question_text == "What is 2+2?"
        assert q.correct_answer == "4"
        assert len(q.incorrect_answers) == 3

    def test_all_answers(self):
        """Test getting all answers."""
        q = Question(
            question_text="Test?",
            correct_answer="A",
            incorrect_answers=["B", "C"],
        )
        answers = q.all_answers()
        assert len(answers) == 3
        assert "A" in answers
        assert "B" in answers
        assert "C" in answers

    def test_question_serialization(self):
        """Test Question can be serialized to dict."""
        q = Question(
            question_text="Test?",
            correct_answer="A",
            incorrect_answers=["B", "C"],
        )
        data = q.model_dump()
        assert data["question_text"] == "Test?"
        assert data["correct_answer"] == "A"
        assert data["incorrect_answers"] == ["B", "C"]

    def test_question_from_dict(self):
        """Test Question can be created from dict."""
        data = {
            "question_text": "Test?",
            "correct_answer": "A",
            "incorrect_answers": ["B", "C"],
        }
        q = Question(**data)
        assert q.question_text == "Test?"


class TestSkillMap:
    """Tests for SkillMap model."""

    def test_create_skillmap(self):
        """Test creating a SkillMap."""
        sm = SkillMap(skills=["Skill 1", "Skill 2", "Skill 3"])
        assert len(sm.skills) == 3

    def test_empty_skillmap(self):
        """Test empty skillmap."""
        sm = SkillMap(skills=[])
        assert len(sm.skills) == 0


class TestReview:
    """Tests for Review model."""

    def test_valid_review(self):
        """Test creating a valid Review."""
        r = Review(valid=True, correct_answer="A")
        assert r.valid is True
        assert r.correct_answer == "A"

    def test_invalid_review(self):
        """Test creating an invalid Review."""
        r = Review(valid=False, correct_answer="B")
        assert r.valid is False


class TestQuestionAttempt:
    """Tests for QuestionAttempt model."""

    def test_create_attempt(self):
        """Test creating a QuestionAttempt."""
        attempt = QuestionAttempt(
            selected_answer="A",
            is_correct=True,
            time_taken_seconds=10,
            stack_depth=2,
        )
        assert attempt.selected_answer == "A"
        assert attempt.is_correct is True
        assert attempt.time_taken_seconds == 10
        assert attempt.stack_depth == 2

    def test_attempt_defaults(self):
        """Test QuestionAttempt default values."""
        attempt = QuestionAttempt(
            selected_answer="A",
            is_correct=False,
        )
        assert attempt.question_id is None
        assert attempt.time_taken_seconds is None
        assert attempt.stack_depth == 0


class TestSessionState:
    """Tests for SessionState model."""

    def test_create_session_state(self):
        """Test creating a SessionState."""
        state = SessionState(
            topic="Python",
            current_skill_index=1,
            skills=["Variables", "Functions", "Classes"],
        )
        assert state.topic == "Python"
        assert state.current_skill_index == 1
        assert len(state.skills) == 3

    def test_session_state_defaults(self):
        """Test SessionState default values."""
        state = SessionState(topic="Math")
        assert state.current_skill_index == 0
        assert state.skills == []
        assert state.question_stack == []
        assert state.marked_incorrect == {}
