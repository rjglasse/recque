"""Session aggregate — owns the recursive-questioning state and its invariants.

A `Session` wraps a `LearningStack` and the surrounding journey state (skills,
current skill index, per-attempt counters). It is the single home for the
push-on-wrong / pop-on-right logic that previously lived in the UI screens.

The aggregate is pure: no AI generation, no database, no UI. Callers generate
questions and render outcomes; the aggregate decides what happens to the stack
and reports it via `AnswerResult`.
"""

import logging
from dataclasses import dataclass, field
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


class BoxState(Enum):
    """State of one box (level) in a skill's progress column."""

    PENDING = "pending"  # not yet answered
    WRONG = "wrong"      # answered incorrectly (and drilled deeper)
    CORRECT = "correct"  # answered correctly / resolved


@dataclass
class SkillColumn:
    """One skill's column in the progress skyline.

    `boxes` runs top (the main question) to bottom (the deepest level reached).
    `active` is the index of the box the learner is currently on, or None when
    the skill isn't the active one.
    """

    label: str
    boxes: list[BoxState] = field(default_factory=list)
    active: int | None = None


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
        descent_depths: list[int] | None = None,
    ):
        self.topic = topic
        self.skills = skills
        self.current_skill_index = current_skill_index
        self._stack = stack if stack is not None else LearningStack()
        self.questions_answered = 0
        self.questions_correct = 0
        # Per-skill max stack depth ever reached — the height of each skill's
        # progress column. The whole skyline derives from this plus the live
        # stack (see progress_view).
        self._max_depth = list(descent_depths) if descent_depths else [0] * len(skills)
        if len(self._max_depth) < len(skills):
            self._max_depth += [0] * (len(skills) - len(self._max_depth))

    @classmethod
    def restore(
        cls,
        topic: str,
        skills: list[str],
        current_skill_index: int,
        stack_data: list[dict] | None,
        descent_depths: list[int] | None = None,
    ) -> "Session":
        """Rebuild a Session from persisted state (see SessionService.get_session_state).

        Counters are not persisted, so they reset on resume — matching prior behavior.
        `descent_depths` restores each skill's column height for the skyline.
        """
        stack = LearningStack.from_dict(stack_data) if stack_data else LearningStack()
        return cls(topic, skills, current_skill_index, stack, descent_depths)

    # --- Stack-feeding -----------------------------------------------------

    def push_question(self, question: Question, prefetched: dict[str, Question] | None = None) -> None:
        """Push a caller-generated question onto the stack.

        This is the only public push: it is used for every generated question —
        a fresh skill question, a "new question", or a regenerated simpler one.
        The DRILL_DOWN promotion of an already-prefetched child is handled inside
        `answer()`, which is why there is no separate `push_simpler`.
        """
        self._stack.push(question, prefetched)
        self._record_depth()

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
            self._record_depth()
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

    # --- Progress skyline --------------------------------------------------

    def _record_depth(self) -> None:
        """Update the current skill's column height after a push.

        Called only on pushes. A push that lands at depth 1 is a fresh main
        question, so the column resets to a single box; deeper pushes only
        ever extend the recorded maximum (climb-backs never call this).
        """
        i = self.current_skill_index
        if not 0 <= i < len(self._max_depth):
            return
        self._max_depth[i] = 1 if self.depth == 1 else max(self._max_depth[i], self.depth)

    @property
    def descent_depths(self) -> list[int]:
        """Per-skill column heights — for persistence/restore of the skyline."""
        return list(self._max_depth)

    @property
    def current_descent_depth(self) -> int:
        """Recorded column height for the active skill (persisted per save)."""
        i = self.current_skill_index
        return self._max_depth[i] if 0 <= i < len(self._max_depth) else 0

    def progress_view(self) -> list[SkillColumn]:
        """The skyline: one column per skill, derived from the live stack and
        each skill's recorded max depth.

        - Skills before the current one are complete → an all-green column.
        - The current skill renders its live descent: the first `depth` boxes
          come from the stack (wrong where a wrong answer is recorded, else the
          pending current box), and the remaining `max_depth − depth` boxes are
          resolved greens sitting below.
        - Later skills are a single pending box.
        """
        wrong = self._stack.wrong_flags()
        depth = self._stack.depth
        columns: list[SkillColumn] = []

        for i, _name in enumerate(self.skills):
            label = f"Q{i + 1}"
            if i < self.current_skill_index:
                height = max(self._max_depth[i], 1)
                columns.append(SkillColumn(label, [BoxState.CORRECT] * height))
            elif i == self.current_skill_index:
                if depth > 0:
                    height = max(self._max_depth[i], depth)
                    boxes = [
                        BoxState.WRONG if wrong[level] else BoxState.PENDING
                        for level in range(depth)
                    ]
                    boxes += [BoxState.CORRECT] * (height - depth)
                    columns.append(SkillColumn(label, boxes, active=depth - 1))
                elif self._max_depth[i] > 0:
                    # Just completed, awaiting advance — show the resolved column.
                    columns.append(SkillColumn(label, [BoxState.CORRECT] * self._max_depth[i]))
                else:
                    # Fresh skill, question still generating.
                    columns.append(SkillColumn(label, [BoxState.PENDING]))
            else:
                columns.append(SkillColumn(label, [BoxState.PENDING]))

        return columns

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
