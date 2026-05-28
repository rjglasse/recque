"""FastAPI web application for RecQue."""

import hashlib
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from recque_tui.application.session_service import SessionService
from recque_tui.config import configure_logging
from recque_tui.core.learning_stack import LearningStack
from recque_tui.core.models import Question
from recque_tui.core.question_engine import LearningContext, QuestionEngine
from recque_tui.database.repositories import (
    ProgressRepository,
    QuestionRepository,
    initialize_database,
)
from recque_tui.database.schema import (
    LearningSession,
    Topic,
    get_or_create_default_user,
    get_session_factory,
)
from recque_tui.domain.analytics import Analytics

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent

# Track session-level stats in memory (reset on restart, which is fine)
_session_stats: dict[int, dict] = {}


def _render(request, name, ctx=None):
    ctx = ctx or {}
    ctx["ai_mode"] = engine.ai_client.backend != "mock"
    ctx["ai_model"] = f"{engine.ai_client.backend}: {engine.ai_client.model}"
    ctx["ai_fell_back"] = engine.ai_client.fell_back_to_mock
    return templates.TemplateResponse(request, name, ctx)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    initialize_database()
    yield


app = FastAPI(title="RecQue", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

engine = QuestionEngine()


def _get_stats(session_id: int) -> dict:
    if session_id not in _session_stats:
        _session_stats[session_id] = {"answered": 0, "correct": 0}
    return _session_stats[session_id]


def _build_context(session_id: int, stack: LearningStack) -> LearningContext:
    stats = _get_stats(session_id)
    return LearningContext(
        stack_breadcrumbs=stack.breadcrumb() if stack.depth > 0 else None,
        questions_answered=stats["answered"],
        questions_correct=stats["correct"],
        stack_depth=stack.depth,
    )


def _rebuild_stack(db_session_id: int) -> tuple[LearningStack, dict]:
    with SessionService() as mgr:
        factory = get_session_factory()
        with factory() as db:
            session = db.query(LearningSession).get(db_session_id)
            if not session:
                return LearningStack(), {}
            state = mgr.get_session_state(session)
            if not state:
                return LearningStack(), {}
            stack = LearningStack()
            if state["stack_data"]:
                stack = LearningStack.from_dict(state["stack_data"])
            return stack, state


def _save_stack(db_session_id: int, stack: LearningStack, skill_index: int, skills: list[str]):
    with SessionService() as mgr:
        factory = get_session_factory()
        with factory() as db:
            session = db.query(LearningSession).get(db_session_id)
            if session:
                mgr.save_progress(session, skill_index, stack, skills)


def _record_attempt(
    db_session_id: int,
    question: Question,
    selected_answer: str,
    is_correct: bool,
    stack_depth: int,
    skill_name: str,
):
    stats = _get_stats(db_session_id)
    stats["answered"] += 1
    if is_correct:
        stats["correct"] += 1

    factory = get_session_factory()
    with factory() as db:
        session = db.query(LearningSession).get(db_session_id)
        if not session:
            return

        question_hash = hashlib.sha256(
            f"{skill_name}|{question.question_text}".encode()
        ).hexdigest()[:16]

        with QuestionRepository(db) as qrepo:
            cached = qrepo.get_by_hash(question_hash)
            if not cached:
                cached_row = qrepo.save(question, skill_name, question_hash)
            else:
                from recque_tui.database.schema import CachedQuestion
                cached_row = db.query(CachedQuestion).filter_by(
                    question_hash=question_hash
                ).first()

        with ProgressRepository(db) as prepo:
            prepo.record_attempt(
                session, cached_row, selected_answer, is_correct,
                stack_depth=stack_depth,
            )
            user = get_or_create_default_user(db)
            topic = db.query(Topic).get(session.topic_id)
            if topic:
                prepo.update_mastery(user, topic, is_correct)


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    with SessionService() as mgr:
        resumable = mgr.get_resumable_sessions()
        completed = mgr.get_completed_sessions(limit=5)
    return _render(request, "home.html", {
        "resumable": resumable,
        "completed": completed,
    })


@app.post("/start")
async def start_quiz(request: Request, topic: str = Form(...)):
    topic = topic.strip()
    if not topic:
        return RedirectResponse("/", status_code=303)
    skills = engine.generate_skillmap(topic)
    with SessionService() as mgr:
        db_session = mgr.create_session(topic, skills)
        session_id = db_session.id
    response = RedirectResponse(f"/quiz/{session_id}", status_code=303)
    response.set_cookie("recque_session_id", str(session_id), httponly=True)
    return response


@app.get("/quiz/{session_id}", response_class=HTMLResponse)
async def quiz_page(request: Request, session_id: int):
    stack, state = _rebuild_stack(session_id)
    if not state:
        return RedirectResponse("/", status_code=303)

    skills = state["skills"]
    skill_index = state["current_skill_index"]

    all_done = skill_index >= len(skills)
    if not all_done:
        factory = get_session_factory()
        with factory() as db:
            session = db.query(LearningSession).get(session_id)
            if session and session.status == "completed":
                all_done = True
            elif session:
                from recque_tui.database.schema import SessionProgress
                from recque_tui.database.schema import Skill as SkillModel
                topic_obj = db.query(Topic).get(session.topic_id)
                if topic_obj:
                    db_skills = db.query(SkillModel).filter_by(topic_id=topic_obj.id).all()
                    completed_count = sum(
                        1 for s in db_skills
                        if db.query(SessionProgress).filter_by(
                            session_id=session.id, skill_id=s.id, skill_completed=True
                        ).first()
                    )
                    if completed_count >= len(db_skills) and len(db_skills) > 0:
                        all_done = True

    if all_done:
        # Share one db session between the loader and the service: the lifecycle
        # write commits on the service's own session, so the loaded `session` must
        # be attached to that same session for the status change to persist.
        factory = get_session_factory()
        with factory() as db:
            session = db.get(LearningSession, session_id)
            if session and session.status != "completed":
                with SessionService(db) as mgr:
                    mgr.complete_session(session)
        return _render(request, "complete.html", {"topic": state["topic"]})

    ctx = _build_context(session_id, stack)

    if stack.is_empty:
        skill = f"{state['topic']}. {skills[skill_index]}"
        question = engine.generate_question(skill, context=ctx)
        prefetched = engine.prefetch_simpler_questions(
            state["topic"], skills[skill_index], question, context=ctx
        )
        stack.push(question, prefetched)
        _save_stack(session_id, stack, skill_index, skills)

    question = stack.peek()
    entry = stack.current_entry()
    answers = engine.shuffle_answers(question)

    return _render(request, "quiz.html", {
        "session_id": session_id,
        "topic": state["topic"],
        "skill": skills[skill_index],
        "skill_index": skill_index + 1,
        "total_skills": len(skills),
        "question": question,
        "answers": answers,
        "stack": stack,
        "breadcrumbs": stack.breadcrumb(),
        "marked_incorrect": entry.marked_incorrect if entry else [],
    })


@app.post("/quiz/{session_id}/answer", response_class=HTMLResponse)
async def answer_question(request: Request, session_id: int, answer: str = Form(...)):
    stack, state = _rebuild_stack(session_id)
    if not state or stack.is_empty:
        return RedirectResponse(f"/quiz/{session_id}", status_code=303)

    skills = state["skills"]
    skill_index = state["current_skill_index"]
    question = stack.peek()
    is_correct = engine.judge(question, answer)
    skill_name = f"{state['topic']}. {skills[skill_index]}"

    _record_attempt(session_id, question, answer, is_correct, stack.depth, skill_name)

    if is_correct:
        stack.pop()
        if stack.is_empty:
            _save_stack(session_id, stack, skill_index, skills)
            return _render(request, "partials/skill_complete.html", {
                "session_id": session_id,
                "skill": skills[skill_index],
                "skill_index": skill_index + 1,
                "total_skills": len(skills),
                "is_last_skill": skill_index + 1 >= len(skills),
                "explanation": question.explanation,
            })
        else:
            _save_stack(session_id, stack, skill_index, skills)
            parent = stack.peek()
            parent_entry = stack.current_entry()
            answers = engine.shuffle_answers(parent)
            return _render(request, "partials/question_pop.html", {
                "session_id": session_id,
                "question": parent,
                "answers": answers,
                "stack": stack,
                "breadcrumbs": stack.breadcrumb(),
                "marked_incorrect": parent_entry.marked_incorrect if parent_entry else [],
                "message": "Correct! Returning to the previous question.",
                "explanation": question.explanation,
            })
    else:
        stack.mark_incorrect(answer)
        entry = stack.current_entry()
        simpler = entry.prefetched.get(answer) if entry else None

        ctx = _build_context(session_id, stack)

        if not simpler:
            simpler = engine.generate_question(
                skill_name,
                prior_question=question.question_text,
                prior_answer=answer,
                context=ctx,
            )

        prefetched = engine.prefetch_simpler_questions(
            state["topic"], skills[skill_index], simpler, context=ctx
        )
        stack.push(simpler, prefetched)
        _save_stack(session_id, stack, skill_index, skills)

        new_entry = stack.current_entry()
        answers = engine.shuffle_answers(simpler)
        return _render(request, "partials/question_push.html", {
            "session_id": session_id,
            "question": simpler,
            "answers": answers,
            "stack": stack,
            "breadcrumbs": stack.breadcrumb(),
            "marked_incorrect": new_entry.marked_incorrect if new_entry else [],
            "message": "Incorrect. Let's try a simpler question to build your understanding.",
            "explanation": question.explanation,
        })


@app.post("/quiz/{session_id}/next-skill", response_class=HTMLResponse)
async def next_skill(request: Request, session_id: int):
    return RedirectResponse(f"/quiz/{session_id}", status_code=303)


@app.post("/quiz/{session_id}/new-question", response_class=HTMLResponse)
async def new_question(request: Request, session_id: int):
    stack, state = _rebuild_stack(session_id)
    if not state:
        return RedirectResponse("/", status_code=303)
    skills = state["skills"]
    skill_index = state["current_skill_index"]
    new_stack = LearningStack()
    ctx = _build_context(session_id, new_stack)
    skill = f"{state['topic']}. {skills[skill_index]}"
    question = engine.generate_question(skill, context=ctx)
    prefetched = engine.prefetch_simpler_questions(
        state["topic"], skills[skill_index], question, context=ctx
    )
    new_stack.push(question, prefetched)
    _save_stack(session_id, new_stack, skill_index, skills)
    return RedirectResponse(f"/quiz/{session_id}", status_code=303)


@app.get("/progress", response_class=HTMLResponse)
async def progress_page(request: Request):
    analytics = Analytics()
    try:
        metrics = analytics.get_overall_metrics()
        topics = analytics.get_topic_metrics()
        gaps = analytics.get_knowledge_gaps()
        streak = analytics.get_streak_info()
        history = analytics.get_session_history(limit=10)
    except Exception:
        metrics = None
        topics = []
        gaps = []
        streak = {"current_streak": 0, "longest_streak": 0, "total_days": 0}
        history = []
    return _render(request, "progress.html", {
        "metrics": metrics,
        "topics": topics,
        "gaps": gaps,
        "streak": streak,
        "history": history,
    })


@app.get("/resume/{session_id}")
async def resume_session(request: Request, session_id: int):
    # Share one db session so the status change commits against the object's session.
    factory = get_session_factory()
    with factory() as db:
        session = db.get(LearningSession, session_id)
        if session:
            with SessionService(db) as mgr:
                mgr.resume_session(session)
    response = RedirectResponse(f"/quiz/{session_id}", status_code=303)
    response.set_cookie("recque_session_id", str(session_id), httponly=True)
    return response
