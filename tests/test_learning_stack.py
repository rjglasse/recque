"""Tests for core/learning_stack.py."""

import pytest

from recque_tui.core.learning_stack import LearningStack, StackEntry
from recque_tui.core.models import Question


@pytest.fixture
def sample_question():
    """Create a sample question for testing."""
    return Question(
        question_text="What is 2+2?",
        correct_answer="4",
        incorrect_answers=["3", "5", "6"],
    )


@pytest.fixture
def sample_question_2():
    """Create a second sample question."""
    return Question(
        question_text="What is 3+3?",
        correct_answer="6",
        incorrect_answers=["5", "7", "8"],
    )


class TestLearningStack:
    """Tests for LearningStack class."""

    def test_empty_stack(self):
        """Test empty stack properties."""
        stack = LearningStack()
        assert stack.is_empty
        assert stack.depth == 0
        assert stack.peek() is None
        assert stack.pop() is None

    def test_push_single(self, sample_question):
        """Test pushing a single question."""
        stack = LearningStack()
        stack.push(sample_question)

        assert not stack.is_empty
        assert stack.depth == 1
        assert stack.peek() == sample_question

    def test_push_multiple(self, sample_question, sample_question_2):
        """Test pushing multiple questions."""
        stack = LearningStack()
        stack.push(sample_question)
        stack.push(sample_question_2)

        assert stack.depth == 2
        assert stack.peek() == sample_question_2

    def test_pop(self, sample_question, sample_question_2):
        """Test popping questions."""
        stack = LearningStack()
        stack.push(sample_question)
        stack.push(sample_question_2)

        popped = stack.pop()
        assert popped == sample_question_2
        assert stack.depth == 1
        assert stack.peek() == sample_question

    def test_pop_empty(self):
        """Test popping from empty stack."""
        stack = LearningStack()
        assert stack.pop() is None

    def test_mark_incorrect(self, sample_question):
        """Test marking an answer as incorrect."""
        stack = LearningStack()
        stack.push(sample_question)

        stack.mark_incorrect("3")
        entry = stack.current_entry()

        assert "3" in entry.marked_incorrect

    def test_mark_incorrect_no_duplicate(self, sample_question):
        """Test marking same answer twice doesn't duplicate."""
        stack = LearningStack()
        stack.push(sample_question)

        stack.mark_incorrect("3")
        stack.mark_incorrect("3")
        entry = stack.current_entry()

        assert entry.marked_incorrect.count("3") == 1

    def test_prefetched_questions(self, sample_question, sample_question_2):
        """Test storing and retrieving prefetched questions."""
        stack = LearningStack()
        prefetched = {"3": sample_question_2}
        stack.push(sample_question, prefetched)

        assert stack.get_prefetched("3") == sample_question_2
        assert stack.get_prefetched("5") is None

    def test_set_prefetched(self, sample_question, sample_question_2):
        """Test setting prefetched questions after push."""
        stack = LearningStack()
        stack.push(sample_question)

        prefetched = {"3": sample_question_2}
        stack.set_prefetched(prefetched)

        assert stack.get_prefetched("3") == sample_question_2

    def test_breadcrumb(self, sample_question, sample_question_2):
        """Test breadcrumb generation."""
        stack = LearningStack()
        stack.push(sample_question)
        stack.push(sample_question_2)

        breadcrumb = stack.breadcrumb()
        assert len(breadcrumb) == 2
        assert "2+2" in breadcrumb[0]
        assert "3+3" in breadcrumb[1]

    def test_breadcrumb_truncation(self):
        """Test breadcrumb truncates long questions."""
        long_question = Question(
            question_text="A" * 100,  # Long question
            correct_answer="B",
            incorrect_answers=["C"],
        )
        stack = LearningStack()
        stack.push(long_question)

        breadcrumb = stack.breadcrumb()
        assert len(breadcrumb[0]) <= 53  # 50 chars + "..."

    def test_clear(self, sample_question, sample_question_2):
        """Test clearing the stack."""
        stack = LearningStack()
        stack.push(sample_question)
        stack.push(sample_question_2)

        stack.clear()
        assert stack.is_empty
        assert stack.depth == 0

    def test_to_dict(self, sample_question):
        """Test serialization to dict."""
        stack = LearningStack()
        stack.push(sample_question)
        stack.mark_incorrect("3")

        data = stack.to_dict()
        assert len(data) == 1
        assert data[0]["question"]["question_text"] == "What is 2+2?"
        assert "3" in data[0]["marked_incorrect"]

    def test_from_dict(self, sample_question):
        """Test deserialization from dict."""
        data = [
            {
                "question": {
                    "question_text": "What is 2+2?",
                    "correct_answer": "4",
                    "incorrect_answers": ["3", "5", "6"],
                },
                "marked_incorrect": ["3"],
            }
        ]

        stack = LearningStack.from_dict(data)
        assert stack.depth == 1
        assert stack.peek().question_text == "What is 2+2?"
        assert "3" in stack.current_entry().marked_incorrect

    def test_round_trip_serialization(self, sample_question, sample_question_2):
        """Test serialization round trip."""
        original = LearningStack()
        original.push(sample_question)
        original.mark_incorrect("3")
        original.push(sample_question_2)

        data = original.to_dict()
        restored = LearningStack.from_dict(data)

        assert restored.depth == original.depth
        assert restored.peek().question_text == original.peek().question_text


class TestStackEntry:
    """Tests for StackEntry dataclass."""

    def test_create_entry(self, sample_question):
        """Test creating a StackEntry."""
        entry = StackEntry(question=sample_question)
        assert entry.question == sample_question
        assert entry.marked_incorrect == []
        assert entry.prefetched == {}

    def test_entry_with_prefetched(self, sample_question, sample_question_2):
        """Test StackEntry with prefetched questions."""
        entry = StackEntry(
            question=sample_question,
            prefetched={"3": sample_question_2},
        )
        assert entry.prefetched["3"] == sample_question_2
