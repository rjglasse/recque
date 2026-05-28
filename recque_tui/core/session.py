"""Session aggregate — owns the recursive-questioning state and its invariants.

A `Session` wraps a `LearningStack` and the surrounding journey state (skills,
current skill index, per-attempt counters). It is the single home for the
push-on-wrong / pop-on-right logic that previously lived in the UI screens.

The aggregate is pure: no AI generation, no database, no UI. Callers generate
questions and render outcomes; the aggregate decides what happens to the stack
and reports it via `AnswerResult`.
"""

import logging
from dataclasses import dataclass
from enum import Enum, auto

from recque_tui.core.learning_stack import LearningStack
from recque_tui.core.models import Question

logger = logging.getLogger(__name__)


class Outcome(Enum):
    """What the caller should do after an answer."""

    CLIMB_BACK = auto()      # Correct: popped, the previous question is back on top.
    SKILL_COMPLETE = auto()  # Correct: the stack emptied, the skill is done.
    DRILL_DOWN = auto()      # Wrong: a prefetched simpler question is now on top.
    NEEDS_SIMPLER = auto()   # Wrong: no prefetch — caller must generate a simpler question.


@dataclass
class AnswerResult:
    """The decision the aggregate reached for an answer.

    `next_question` is set for CLIMB_BACK and DRILL_DOWN (the question to show).
    `prior_question_text` / `selected_answer` are set for NEEDS_SIMPLER so the
    caller can generate a simpler question targeting the misconception.
    """

    is_correct: bool
    outcome: Outcome
    next_question: Question | None = None
    prior_question_text: str | None = None
    selected_answer: str | None = None


class Session:
    """The recursive-questioning aggregate for one learning session."""

    def __init__(
        self,
        topic: str,
        skills: list[str],
        current_skill_index: int = 0,
        stack: LearningStack | None = None,
    ):
        self.topic = topic
        self.skills = skills
        self.current_skill_index = current_skill_index
        self._stack = stack if stack is not None else LearningStack()
        self.questions_answered = 0
        self.questions_correct = 0

    @classmethod
    def restore(
        cls,
        topic: str,
        skills: list[str],
        current_skill_index: int,
        stack_data: list[dict] | None,
    ) -> "Session":
        """Rebuild a Session from persisted state (see SessionService.get_session_state).

        Counters are not persisted, so they reset on resume — matching prior behavior.
        """
        stack = LearningStack.from_dict(stack_data) if stack_data else LearningStack()
        return cls(topic, skills, current_skill_index, stack)

    # --- Stack-feeding -----------------------------------------------------

    def push_question(self, question: Question, prefetched: dict[str, Question] | None = None) -> None:
        """Push a caller-generated question onto the stack.

        This is the only public push: it is used for every generated question —
        a fresh skill question, a "new question", or a regenerated simpler one.
        The DRILL_DOWN promotion of an already-prefetched child is handled inside
        `answer()`, which is why there is no separate `push_simpler`.
        """
        self._stack.push(question, prefetched)

    # --- The core mechanic -------------------------------------------------

    def answer(self, selected: str) -> AnswerResult:
        """Record an answer to the current question and decide what happens next.

        Not idempotent: each call counts as an attempt. Callers guard against
        double-submission at the UI layer.
        """
        question = self._stack.peek()
        if question is None:
            raise ValueError("answer() called with an empty stack")

        self.questions_answered += 1

        if question.correct_answer == selected:
            self.questions_correct += 1
            self._stack.pop()
            if self._stack.is_empty:
                logger.info("Answer correct — skill complete")
                return AnswerResult(True, Outcome.SKILL_COMPLETE)
            logger.info("Answer correct — climbing back")
            return AnswerResult(True, Outcome.CLIMB_BACK, next_question=self._stack.peek())

        self._stack.mark_incorrect(selected)
        simpler = self._stack.get_prefetched(selected)
        if simpler is not None:
            self._stack.push(simpler)
            logger.info("Answer wrong — drilling down to prefetched question")
            return AnswerResult(False, Outcome.DRILL_DOWN, next_question=simpler)

        logger.info("Answer wrong — need to generate a simpler question")
        return AnswerResult(
            False,
            Outcome.NEEDS_SIMPLER,
            prior_question_text=question.question_text,
            selected_answer=selected,
        )

    # --- Skill progression -------------------------------------------------

    def start_skill(self) -> None:
        """Begin the current skill with a clean stack."""
        self._stack.clear()

    def advance_skill(self) -> bool:
        """Move to the next skill, clearing the stack.

        Returns True if there is another skill to start, False if the topic is
        complete.
        """
        self.current_skill_index += 1
        self._stack.clear()
        return not self.is_complete

    # --- Queries -----------------------------------------------------------

    @property
    def stack(self) -> LearningStack:
        """The underlying stack — for persistence via SessionService.save_progress."""
        return self._stack

    @property
    def current_question(self) -> Question | None:
        return self._stack.peek()

    @property
    def current_skill(self) -> str | None:
        if 0 <= self.current_skill_index < len(self.skills):
            return self.skills[self.current_skill_index]
        return None

    @property
    def is_complete(self) -> bool:
        return self.current_skill_index >= len(self.skills)

    @property
    def depth(self) -> int:
        return self._stack.depth

    @property
    def marked_incorrect(self) -> list[str]:
        entry = self._stack.current_entry()
        return entry.marked_incorrect if entry else []

    @property
    def accuracy(self) -> str:
        """Human-readable correct/answered, or '-' before any answer."""
        if self.questions_answered == 0:
            return "-"
        return f"{self.questions_correct}/{self.questions_answered}"
