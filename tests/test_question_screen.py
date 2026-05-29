"""Pilot tests for QuestionScreen — drives the real screen through the
Session aggregate's outcome switch in mock mode.

These exercise the hand-wired control flow (_handle_answer, _show_feedback,
_question_ready, _continue, _next_skill) that the aggregate unit tests cannot
reach, including the async generate -> _question_ready boundary.
"""

import pytest
from textual.app import App
from textual.widgets import Button

from recque_tui.application import SessionService
from recque_tui.core.learning_stack import LearningStack
from recque_tui.core.models import Question
from recque_tui.core.question_engine import QuestionEngine
from recque_tui.core.session import BoxState
from recque_tui.ui.screens.question_screen import QuestionScreen

C, W, P = BoxState.CORRECT, BoxState.WRONG, BoxState.PENDING


@pytest.fixture
def isolated_env(monkeypatch, tmp_path):
    """Force mock backend + a throwaway DB, with a fresh config singleton."""
    monkeypatch.setenv("RECQUE_BACKEND", "mock")
    monkeypatch.setenv("RECQUE_DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.delenv("RECQUE_MOCK_MODE", raising=False)
    import recque_tui.config
    monkeypatch.setattr(recque_tui.config, "_config", None)
    from recque_tui.database.repositories import initialize_database
    initialize_database()
    yield


class _Host(App):
    """Minimal host that drops straight into a QuestionScreen."""

    def on_mount(self) -> None:
        self.push_screen(QuestionScreen(topic="Python"))


async def _settle(pilot, predicate, label, tries=300):
    """Pump the event loop until `predicate()` holds (thread workers included)."""
    for _ in range(tries):
        if predicate():
            return
        await pilot.pause(0.02)
    raise AssertionError(f"timed out waiting for: {label}")


def _screen(pilot) -> QuestionScreen:
    return pilot.app.screen


def _question_visible(pilot) -> bool:
    s = _screen(pilot)
    return (
        isinstance(s, QuestionScreen)
        and s.session is not None
        and s.session.current_question is not None
        and not s.answered
        and s.query_one("#question-container").display
    )


def _answer_index(screen: QuestionScreen, *, correct: bool) -> int:
    """Index in the shuffled answer list of the correct (or a wrong) answer."""
    target = screen.session.current_question.correct_answer
    idx = screen.current_answers.index(target)
    if correct:
        return idx
    return next(i for i in range(len(screen.current_answers)) if i != idx)


def _btn_visible(pilot, btn_id: str) -> bool:
    return pilot.app.screen.query_one(btn_id, Button).display


@pytest.mark.asyncio
async def test_full_recursive_flow(isolated_env):
    """Wrong -> drill down, then climb back up to skill completion."""
    async with _Host().run_test() as pilot:
        await _settle(pilot, lambda: _question_visible(pilot), "first question")
        screen = _screen(pilot)
        assert screen.session.depth == 1

        # Wrong answer -> a prefetched simpler question is pushed (DRILL_DOWN).
        await pilot.press(str(_answer_index(screen, correct=False) + 1))
        await _settle(pilot, lambda: _btn_visible(pilot, "#continue-btn"), "drill-down continue")
        assert screen.session.depth == 2  # proves _question_ready pushed WITH prefetch

        # Continue to the simpler question, answer it right -> CLIMB_BACK.
        screen._continue()
        await _settle(pilot, lambda: _question_visible(pilot), "simpler question shown")
        await pilot.press(str(_answer_index(screen, correct=True) + 1))
        await _settle(pilot, lambda: _btn_visible(pilot, "#continue-btn"), "climb-back continue")
        assert screen.session.depth == 1

        # Back on the original question; answer right -> SKILL_COMPLETE.
        screen._continue()
        await _settle(pilot, lambda: _question_visible(pilot), "original question shown")
        await pilot.press(str(_answer_index(screen, correct=True) + 1))
        await _settle(pilot, lambda: _btn_visible(pilot, "#next-skill-btn"), "skill-complete actions")
        assert screen.session.depth == 0


@pytest.mark.asyncio
async def test_answer_click_before_question_loads_is_a_noop(isolated_env):
    """Regression (recque-gsf): pressing an answer button before the first
    question has loaded must not crash. The buttons are created in compose()
    and there is a paint window (Textual 6.11) before generation populates
    current_answers; #question-container is hidden by default so the buttons
    are not clickable, and on_button_pressed bounds-guards as a backstop."""
    async with _Host().run_test() as pilot:
        screen = _screen(pilot)
        # Frame 0: container hidden, no answers loaded yet.
        assert isinstance(screen, QuestionScreen)
        assert screen.current_answers == []
        assert screen.query_one("#question-container").display is False

        # Mouse path (no bounds check historically) must be a safe no-op.
        btn = screen.query_one("#answer-0", Button)
        screen.on_button_pressed(Button.Pressed(btn))  # would IndexError pre-fix
        assert screen.answered is False

        # Once the question loads, the container shows and clicks register.
        await _settle(pilot, lambda: _question_visible(pilot), "first question")
        assert screen.query_one("#question-container").display
        screen.on_button_pressed(Button.Pressed(screen.query_one("#answer-0", Button)))
        assert screen.answered is True


@pytest.mark.asyncio
async def test_needs_simpler_regenerates_with_prefetch(isolated_env, monkeypatch):
    """NEEDS_SIMPLER -> generate -> _question_ready must push the regenerated
    question WITH its prefetch, so the next wrong answer would drill down rather
    than fire another generation on the hot path."""
    calls = {"n": 0}
    real_generate = QuestionEngine.generate_question

    def fake_prefetch(self, topic, skill, current_question, context=None):
        calls["n"] += 1
        if calls["n"] == 1:
            return {}  # first question has no prefetch -> wrong answer needs generation
        # Regenerated question: hand back a real (non-empty) prefetch map.
        simpler = real_generate(self, f"{topic}. {skill}")
        return {a: simpler for a in current_question.incorrect_answers}

    monkeypatch.setattr(QuestionEngine, "prefetch_simpler_questions", fake_prefetch)

    async with _Host().run_test() as pilot:
        await _settle(pilot, lambda: _question_visible(pilot), "first question")
        screen = _screen(pilot)
        assert screen.session.stack.current_entry().prefetched == {}

        # Wrong answer with no prefetch -> NEEDS_SIMPLER -> async regeneration.
        await pilot.press(str(_answer_index(screen, correct=False) + 1))
        await _settle(
            pilot,
            lambda: _question_visible(pilot) and screen.session.depth == 2,
            "regenerated simpler question",
        )
        # The regenerated question arrived through _question_ready WITH prefetch.
        assert screen.session.stack.current_entry().prefetched != {}


@pytest.mark.asyncio
async def test_resume_restores_progress_skyline(isolated_env):
    """End-to-end resume (the session-detachment soft spot): a paused session
    with a completed skill and a mid-descent skill restores its full skyline."""
    skills = ["s1", "s2", "s3"]
    with SessionService() as svc:
        sess = svc.create_session("Python", skills)
        # s1 completed at height 2 (empty stack -> completed).
        svc.save_progress(sess, 0, LearningStack(), skills, descent_depth=2)
        # s2 mid-climb-back: live stack depth 1 (wrong main), column reached 2.
        stack = LearningStack()
        stack.push(Question(question_text="q2?", correct_answer="y",
                            incorrect_answers=["a", "b", "c"]))
        stack.mark_incorrect("a")
        svc.save_progress(sess, 1, stack, skills, descent_depth=2)
        sess_id = sess.id

    class _ResumeHost(App):
        def on_mount(self) -> None:
            with SessionService() as s:
                target = next(r["session"] for r in s.get_resumable_sessions()
                              if r["id"] == sess_id)
            self.push_screen(QuestionScreen(resume_session=target))

    async with _ResumeHost().run_test() as pilot:
        await _settle(
            pilot,
            lambda: isinstance(pilot.app.screen, QuestionScreen)
            and pilot.app.screen.session is not None,
            "resumed session",
        )
        session = pilot.app.screen.session
        assert session.current_skill_index == 1
        cols = session.progress_view()
        assert cols[0].boxes == [C, C]          # s1: restored 2-high green column
        assert cols[1].boxes == [W, C]          # s2: wrong main + restored green tail
        assert cols[1].active == 0
        assert cols[2].boxes == [P]             # s3: untouched
