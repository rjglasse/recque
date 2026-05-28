"""Tests for the Session aggregate — recursive-questioning invariants."""

from recque_tui.core.learning_stack import LearningStack
from recque_tui.core.models import Question
from recque_tui.core.session import AnswerResult, Outcome, Session


def _q(text: str, correct: str = "right", wrong: list[str] | None = None) -> Question:
    return Question(
        question_text=text,
        correct_answer=correct,
        incorrect_answers=wrong or ["w1", "w2", "w3"],
    )


def _session(skills: list[str] | None = None) -> Session:
    return Session("Topic", skills or ["s1", "s2"])


class TestAnswerOutcomes:
    def test_correct_on_lone_question_completes_skill(self):
        s = _session()
        s.push_question(_q("top"))
        result = s.answer("right")
        assert result == AnswerResult(True, Outcome.SKILL_COMPLETE)
        assert s.depth == 0

    def test_correct_with_deeper_stack_climbs_back(self):
        s = _session()
        s.push_question(_q("top"))
        s.push_question(_q("simpler", correct="r2"))  # drilled down
        result = s.answer("r2")
        assert result.is_correct
        assert result.outcome == Outcome.CLIMB_BACK
        assert result.next_question.question_text == "top"
        assert s.depth == 1

    def test_wrong_with_prefetch_drills_down(self):
        s = _session()
        simpler = _q("simpler", correct="r2")
        s.push_question(_q("top", wrong=["bad", "w2", "w3"]), prefetched={"bad": simpler})
        result = s.answer("bad")
        assert not result.is_correct
        assert result.outcome == Outcome.DRILL_DOWN
        assert result.next_question is simpler
        assert s.depth == 2
        assert s.current_question is simpler

    def test_wrong_without_prefetch_needs_simpler(self):
        s = _session()
        s.push_question(_q("top", wrong=["bad", "w2", "w3"]))
        result = s.answer("bad")
        assert not result.is_correct
        assert result.outcome == Outcome.NEEDS_SIMPLER
        assert result.prior_question_text == "top"
        assert result.selected_answer == "bad"
        # The wrong answer is marked on the still-current entry.
        assert "bad" in s.marked_incorrect

    def test_regenerated_simpler_question_keeps_its_prefetch(self):
        """Integration guard: the NEEDS_SIMPLER follow-up arrives via push_question
        WITH prefetch, so the next wrong answer drills down instead of regenerating."""
        s = _session()
        s.push_question(_q("top", wrong=["bad", "w2", "w3"]))
        assert s.answer("bad").outcome == Outcome.NEEDS_SIMPLER

        # Caller generates a simpler question with its own prefetch and pushes it.
        deeper = _q("deeper", correct="r3")
        s.push_question(
            _q("simpler", correct="r2", wrong=["badx", "y", "z"]),
            prefetched={"badx": deeper},
        )
        result = s.answer("badx")
        assert result.outcome == Outcome.DRILL_DOWN
        assert result.next_question is deeper


class TestSkillProgression:
    def test_advance_skill_returns_true_until_last(self):
        s = _session(["s1", "s2"])
        assert s.current_skill == "s1"
        assert s.advance_skill() is True
        assert s.current_skill == "s2"
        assert not s.is_complete

    def test_advance_past_last_skill_completes(self):
        s = _session(["only"])
        assert s.advance_skill() is False
        assert s.is_complete
        assert s.current_skill is None

    def test_advance_clears_stack(self):
        s = _session(["s1", "s2"])
        s.push_question(_q("top"))
        assert s.depth == 1
        s.advance_skill()
        assert s.depth == 0


class TestCounters:
    def test_accuracy_tracks_correct_over_answered(self):
        s = _session()
        assert s.accuracy == "-"
        s.push_question(_q("a"))
        s.answer("right")               # correct
        s.push_question(_q("b", wrong=["bad", "x", "y"]))
        s.answer("bad")                 # wrong
        assert s.questions_answered == 2
        assert s.questions_correct == 1
        assert s.accuracy == "1/2"


class TestSerialization:
    def test_restore_round_trips_through_learning_stack_shape(self):
        s = _session(["s1", "s2"])
        s.current_skill_index = 1
        s.push_question(_q("top"))
        s.answer("right")               # pop to empty, then re-push to have content
        s.push_question(_q("kept", wrong=["bad", "x", "y"]))
        s.answer("bad")                 # marks "bad" incorrect on the entry

        data = s.stack.to_dict()
        restored = Session.restore("Topic", ["s1", "s2"], 1, data)

        # Same on-disk shape as a bare LearningStack round-trip.
        assert restored.stack.to_dict() == LearningStack.from_dict(data).to_dict()
        assert restored.current_skill_index == 1
        assert restored.current_question.question_text == "kept"
        assert "bad" in restored.marked_incorrect
