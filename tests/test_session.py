"""Tests for the Session aggregate — recursive-questioning invariants."""

from recque_tui.core.learning_stack import LearningStack
from recque_tui.core.models import Question
from recque_tui.core.session import AnswerResult, BoxState, Outcome, Session

P, W, C = BoxState.PENDING, BoxState.WRONG, BoxState.CORRECT


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


class TestProgressView:
    """The recursive-descent skyline (progress_view) across all transitions."""

    def _cols(self, s):
        return [(c.label, c.boxes, c.active) for c in s.progress_view()]

    def test_initial_columns_are_pending(self):
        s = _session(["s1", "s2", "s3"])
        s.push_question(_q("q1"))
        cols = s.progress_view()
        assert [c.label for c in cols] == ["Q1", "Q2", "Q3"]
        assert cols[0].boxes == [P] and cols[0].active == 0   # current main question
        assert cols[1].boxes == [P] and cols[1].active is None
        assert cols[2].boxes == [P] and cols[2].active is None

    def test_correct_first_try_then_advance_is_all_green(self):
        s = _session(["s1", "s2"])
        s.push_question(_q("q1"))
        assert s.answer("right").outcome == Outcome.SKILL_COMPLETE
        # Immediately after completion (before advance) the column shows green.
        assert s.progress_view()[0].boxes == [C]
        s.advance_skill()
        cols = s.progress_view()
        assert cols[0].boxes == [C] and cols[0].active is None
        assert cols[1].boxes == [P]               # next skill, not started

    def test_wrong_drills_and_climb_back_builds_green_tail(self):
        s = _session(["s1", "s2"])
        simpler = _q("simpler", correct="r2")
        s.push_question(_q("top", wrong=["bad", "x", "y"]), prefetched={"bad": simpler})

        # Wrong on the main question -> drill down. Top red, new pending below.
        s.answer("bad")
        col = s.progress_view()[0]
        assert col.boxes == [W, P] and col.active == 1

        # Correct on the simpler one -> climb back. The deeper box is now green,
        # and we're back on the (still-wrong) main question.
        assert s.answer("r2").outcome == Outcome.CLIMB_BACK
        col = s.progress_view()[0]
        assert col.boxes == [W, C] and col.active == 0

        # Re-answer the main question correctly -> skill complete, all green.
        assert s.answer("right").outcome == Outcome.SKILL_COMPLETE
        assert s.progress_view()[0].boxes == [C, C]

    def test_multi_level_descent_height_is_max_reached(self):
        s = _session(["s1"])
        l1 = _q("l1", correct="r1", wrong=["b1", "x", "y"])
        l2 = _q("l2", correct="r2")
        s.push_question(_q("top", wrong=["b0", "x", "y"]), prefetched={"b0": l1})
        s.answer("b0")                       # depth 2
        s.stack.set_prefetched({"b1": l2})
        s.answer("b1")                       # depth 3
        col = s.progress_view()[0]
        assert col.boxes == [W, W, P] and col.active == 2

        s.answer("r2")                       # climb to depth 2
        assert s.progress_view()[0].boxes == [W, W, C]
        s.answer("r1")                       # climb to depth 1
        assert s.progress_view()[0].boxes == [W, C, C] and s.progress_view()[0].active == 0

    def test_redescent_does_not_keep_phantom_green(self):
        """Wrong again at a level after a resolved drill: the old green tail is
        gone and the column height stays the max depth (no flicker, no phantom)."""
        s = _session(["s1"])
        first = _q("first", correct="r1")
        second = _q("second", correct="r2")
        s.push_question(_q("top", wrong=["a", "b", "y"]), prefetched={"a": first, "b": second})
        s.answer("a")                        # drill via "a"
        s.answer("r1")                        # climb back -> [W, C]
        assert s.progress_view()[0].boxes == [W, C]
        s.answer("b")                        # wrong AGAIN, drill via "b" -> re-descent
        col = s.progress_view()[0]
        assert col.boxes == [W, P] and col.active == 1   # no phantom green at level 1

    def test_completed_skills_keep_their_skyline_height(self):
        s = _session(["s1", "s2"])
        # s1 takes one drill before completing -> height 2.
        simpler = _q("simpler", correct="r2")
        s.push_question(_q("top", wrong=["bad", "x", "y"]), prefetched={"bad": simpler})
        s.answer("bad")
        s.answer("r2")
        s.answer("right")
        s.advance_skill()
        s.push_question(_q("q2"))
        cols = s.progress_view()
        assert cols[0].boxes == [C, C]        # retained 2-high skyline
        assert cols[1].boxes == [P] and cols[1].active == 0

    def test_descent_depths_restore_round_trips_the_skyline(self):
        # Realistic resume: s1 completed at height 3; on s2 the learner had
        # drilled then climbed back to the (still-wrong) main question — so the
        # live stack is depth 1 but the column reached height 2.
        live = LearningStack()
        live.push(_q("q2-main", wrong=["bad", "x", "y"]))
        live.mark_incorrect("bad")
        restored = Session.restore(
            "Topic", ["s1", "s2", "s3"], 1, live.to_dict(), descent_depths=[3, 2, 0]
        )
        cols = restored.progress_view()
        assert cols[0].boxes == [C, C, C]     # s1 restored as a 3-high green column
        # s2: wrong main from the stack + one green tail recovered from descent_depth.
        assert cols[1].boxes == [W, C] and cols[1].active == 0
        assert cols[2].boxes == [P]           # s3 untouched


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
