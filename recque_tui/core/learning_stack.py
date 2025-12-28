"""Recursive learning stack management."""

import logging
from dataclasses import dataclass, field

from recque_tui.core.models import Question

logger = logging.getLogger(__name__)


@dataclass
class StackEntry:
    """An entry in the learning stack."""
    question: Question
    marked_incorrect: list[str] = field(default_factory=list)
    prefetched: dict[str, Question] = field(default_factory=dict)


class LearningStack:
    """Manages the recursive questioning stack.

    When a learner answers incorrectly, a simpler question is pushed onto the stack.
    When they answer correctly, we pop and return to the previous question.
    This creates a recursive learning pattern that addresses knowledge gaps.
    """

    def __init__(self):
        """Initialize an empty learning stack."""
        self._stack: list[StackEntry] = []

    def push(self, question: Question, prefetched: dict[str, Question] | None = None) -> None:
        """Push a new question onto the stack.

        Args:
            question: The question to push.
            prefetched: Pre-fetched simpler questions for incorrect answers.
        """
        entry = StackEntry(
            question=question,
            prefetched=prefetched or {},
        )
        self._stack.append(entry)
        logger.info(f"Pushed question. Stack depth: {self.depth}")

    def pop(self) -> Question | None:
        """Pop the current question from the stack.

        Returns:
            The popped question, or None if stack is empty.
        """
        if not self._stack:
            return None

        entry = self._stack.pop()
        logger.info(f"Popped question. Stack depth: {self.depth}")
        return entry.question

    def peek(self) -> Question | None:
        """Get the current question without removing it.

        Returns:
            The current question, or None if stack is empty.
        """
        if not self._stack:
            return None
        return self._stack[-1].question

    def current_entry(self) -> StackEntry | None:
        """Get the current stack entry with all metadata.

        Returns:
            The current StackEntry, or None if stack is empty.
        """
        if not self._stack:
            return None
        return self._stack[-1]

    def mark_incorrect(self, answer: str) -> None:
        """Mark an answer as incorrect for the current question.

        Args:
            answer: The answer to mark as incorrect.
        """
        if self._stack:
            if answer not in self._stack[-1].marked_incorrect:
                self._stack[-1].marked_incorrect.append(answer)

    def get_prefetched(self, answer: str) -> Question | None:
        """Get a prefetched simpler question for an incorrect answer.

        Args:
            answer: The incorrect answer.

        Returns:
            The prefetched simpler question, or None if not available.
        """
        if self._stack:
            return self._stack[-1].prefetched.get(answer)
        return None

    def set_prefetched(self, prefetched: dict[str, Question]) -> None:
        """Set prefetched questions for the current entry.

        Args:
            prefetched: Dict mapping incorrect answers to simpler questions.
        """
        if self._stack:
            self._stack[-1].prefetched = prefetched

    @property
    def depth(self) -> int:
        """Get the current stack depth."""
        return len(self._stack)

    @property
    def is_empty(self) -> bool:
        """Check if the stack is empty."""
        return len(self._stack) == 0

    def breadcrumb(self) -> list[str]:
        """Get a breadcrumb trail of question topics.

        Returns:
            List of question texts (truncated) from bottom to top of stack.
        """
        return [
            entry.question.question_text[:50] + "..."
            if len(entry.question.question_text) > 50
            else entry.question.question_text
            for entry in self._stack
        ]

    def clear(self) -> None:
        """Clear the entire stack."""
        self._stack.clear()
        logger.info("Stack cleared")

    def to_dict(self) -> list[dict]:
        """Serialize the stack for persistence.

        Returns:
            List of serialized stack entries.
        """
        return [
            {
                "question": entry.question.model_dump(),
                "marked_incorrect": entry.marked_incorrect,
            }
            for entry in self._stack
        ]

    @classmethod
    def from_dict(cls, data: list[dict]) -> "LearningStack":
        """Deserialize a stack from persistence.

        Args:
            data: Serialized stack data.

        Returns:
            A restored LearningStack.
        """
        stack = cls()
        for entry_data in data:
            question = Question(**entry_data["question"])
            entry = StackEntry(
                question=question,
                marked_incorrect=entry_data.get("marked_incorrect", []),
            )
            stack._stack.append(entry)
        return stack
