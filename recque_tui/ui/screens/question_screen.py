"""Question screen - the core quiz interface."""

from textual import work
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, LoadingIndicator, Static

from recque_tui.application import SessionService
from recque_tui.core.models import Question
from recque_tui.core.question_engine import QuestionEngine
from recque_tui.core.session import AnswerResult, Outcome, Session
from recque_tui.database.schema import LearningSession
from recque_tui.ui.widgets.progress_map import ProgressMap


class QuestionScreen(Screen):
    """The main question/quiz screen."""

    BINDINGS = [
        ("escape", "pause_session", "Pause"),
        ("1", "select_answer(0)", "Answer 1"),
        ("2", "select_answer(1)", "Answer 2"),
        ("3", "select_answer(2)", "Answer 3"),
        ("4", "select_answer(3)", "Answer 4"),
    ]

    def __init__(
        self,
        topic: str | None = None,
        resume_session: LearningSession | None = None,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ):
        """Initialize the question screen.

        Args:
            topic: The topic to learn (for new sessions).
            resume_session: Session to resume (for resuming).
            name: Screen name.
            id: Screen ID.
            classes: CSS classes.
        """
        super().__init__(name=name, id=id, classes=classes)
        self.topic = topic or ""
        self.resume_session = resume_session
        self.engine = QuestionEngine()
        self.session: Session | None = None
        self.current_answers: list[str] = []
        self.answered = False
        self.db_session: LearningSession | None = None

    def compose(self) -> ComposeResult:
        """Compose the question screen UI."""
        yield Header()

        with Container(id="content"):
            # Topic and skill info
            yield Static("", id="topic-label")

            # Skill badge and stats
            with Horizontal(id="top-bar"):
                yield Static("", id="skill-badge", classes="skill-badge")
                yield Static("", id="stats")

            # Recursive-descent progress skyline
            yield ProgressMap(id="progress-map", classes="progress-map")

            # Loading indicator (shown while generating)
            yield LoadingIndicator(id="loading")
            yield Static("Generating your question…", id="loading-label")

            # Question card (hidden while loading)
            with Container(id="question-container", classes="question-card"):
                yield Static("", id="question-text", classes="question-text")

                # Answer buttons
                with Vertical(id="answers"):
                    for i in range(4):
                        yield Button(
                            f"Answer {i+1}",
                            id=f"answer-{i}",
                            classes="answer-button",
                        )

            # Feedback area
            yield Static("", id="feedback", classes="feedback")

            # Action buttons (shown after answering)
            with Horizontal(id="actions"):
                yield Button("Continue", id="continue-btn", variant="primary")
                yield Button("New Question", id="new-question-btn")
                yield Button("Next Skill", id="next-skill-btn")

        yield Footer()

    def on_mount(self) -> None:
        """Handle mount - start generating skillmap or resume."""
        # Hide elements initially
        self.query_one("#question-container").display = False
        self.query_one("#feedback").display = False
        self.query_one("#actions").display = False
        self.query_one("#loading").display = True
        self.query_one("#loading-label").display = True

        if self.resume_session:
            self._resume_from_session()
        else:
            self.generate_skillmap()

    def _resume_from_session(self) -> None:
        """Resume from a saved session."""
        with SessionService() as service:
            state = service.get_session_state(self.resume_session)
            if state:
                self.topic = state["topic"]
                self.session = Session.restore(
                    state["topic"],
                    state["skills"],
                    state["current_skill_index"],
                    state["stack_data"],
                    state.get("descent_depths"),
                )
                self.db_session = self.resume_session
                service.resume_session(self.resume_session)

        if self.session is None:
            # No saved state — nothing to resume.
            self.session = Session(self.topic, [])

        self.query_one("#topic-label").update(f"[bold]{self.topic}[/bold]")

        if self.session.depth == 0:
            # Need to generate a new question
            self._start_skill()
        else:
            # Resume with existing stack
            self.query_one("#skill-badge").update(f"{self.session.current_skill}")
            self.query_one("#loading").display = False
            self.query_one("#loading-label").display = False
            self._display_question()

    @work(thread=True)
    def generate_skillmap(self) -> None:
        """Generate the skillmap for the topic."""
        skills = self.engine.generate_skillmap(self.topic)
        self.app.call_from_thread(self._skillmap_ready, skills)

    def _skillmap_ready(self, skills: list[str]) -> None:
        """Called when skillmap is ready."""
        if not skills:
            self.notify("Failed to generate skills", severity="error")
            self.app.pop_screen()
            return

        self.session = Session(self.topic, skills)

        # Create database session
        with SessionService() as service:
            self.db_session = service.create_session(self.topic, skills)

        self.query_one("#topic-label").update(f"[bold]{self.topic}[/bold]")
        self._start_skill()

    def _start_skill(self) -> None:
        """Start the current skill."""
        if self.session.is_complete:
            self._complete_topic()
            return

        self.query_one("#skill-badge").update(f"{self.session.current_skill}")
        self.session.start_skill()
        self.generate_question()

    @work(thread=True)
    def generate_question(self, prior_question: str | None = None, prior_answer: str | None = None) -> None:
        """Generate a new question."""
        skill_name = self.session.current_skill
        skill = f"{self.topic}. {skill_name}"
        question = self.engine.generate_question(skill, prior_question, prior_answer)

        # Prefetch simpler questions
        prefetched = self.engine.prefetch_simpler_questions(self.topic, skill_name, question)

        self.app.call_from_thread(self._question_ready, question, prefetched)

    def _question_ready(self, question: Question, prefetched: dict[str, Question]) -> None:
        """Called when question is ready."""
        self.session.push_question(question, prefetched)
        self._save_progress()
        self._display_question()

    def _display_question(self) -> None:
        """Display the current question."""
        question = self.session.current_question
        if not question:
            return

        # Shuffle answers
        self.current_answers = self.engine.shuffle_answers(question)
        self.answered = False

        # Update question text
        self.query_one("#question-text").update(question.question_text)

        # Update answer buttons
        marked = self.session.marked_incorrect

        for i, answer in enumerate(self.current_answers):
            button = self.query_one(f"#answer-{i}", Button)
            button.label = f"({i+1}) {answer}"
            button.disabled = False
            button.display = True
            button.remove_class("correct", "incorrect", "marked-wrong")

            if answer in marked:
                button.add_class("marked-wrong")

        # Hide unused buttons
        for i in range(len(self.current_answers), 4):
            button = self.query_one(f"#answer-{i}", Button)
            button.display = False

        # Update stats
        self._update_stats()

        # Show question, hide loading
        self.query_one("#loading").display = False
        self.query_one("#loading-label").display = False
        self.query_one("#question-container").display = True
        self.query_one("#feedback").display = False
        self.query_one("#actions").display = False

    def _update_stats(self) -> None:
        """Update the stats display and the progress skyline."""
        skill_progress = f"{self.session.current_skill_index + 1}/{len(self.session.skills)}"
        self.query_one("#stats").update(f"Skill {skill_progress} | Score: {self.session.accuracy}")
        self._update_progress_map()

    def _update_progress_map(self) -> None:
        """Refresh the recursive-descent skyline from the session."""
        if self.session:
            self.query_one("#progress-map", ProgressMap).update_view(self.session.progress_view())

    def _save_progress(self) -> None:
        """Save current progress to database."""
        if self.db_session and self.session:
            with SessionService() as service:
                service.save_progress(
                    self.db_session,
                    self.session.current_skill_index,
                    self.session.stack,
                    self.session.skills,
                    self.session.current_descent_depth,
                )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id

        if button_id and button_id.startswith("answer-"):
            index = int(button_id.split("-")[1])
            if not self.answered and index < len(self.current_answers):
                self._handle_answer(index)
        elif button_id == "continue-btn":
            self._continue()
        elif button_id == "new-question-btn":
            self._new_question()
        elif button_id == "next-skill-btn":
            self._next_skill()

    def action_select_answer(self, index: int) -> None:
        """Handle keyboard answer selection."""
        if not self.answered and index < len(self.current_answers):
            self._handle_answer(index)

    def _handle_answer(self, index: int) -> None:
        """Handle an answer selection."""
        self.answered = True

        selected = self.current_answers[index]
        button = self.query_one(f"#answer-{index}", Button)

        # Disable all buttons
        for i in range(len(self.current_answers)):
            self.query_one(f"#answer-{i}", Button).disabled = True

        result = self.session.answer(selected)
        button.add_class("correct" if result.is_correct else "incorrect")

        self._show_feedback(result)
        self._update_stats()
        self._save_progress()

    def _show_feedback(self, result: AnswerResult) -> None:
        """Show feedback and set up the next action based on the answer outcome."""
        feedback = self.query_one("#feedback")

        if result.is_correct:
            feedback.remove_class("incorrect")
            feedback.add_class("correct")
            if result.outcome == Outcome.SKILL_COMPLETE:
                feedback.update("Correct.")
                self._show_skill_complete_actions()
            else:  # CLIMB_BACK
                feedback.update(
                    "Correct. Let's go back to the earlier question."
                )
                self._show_continue_action()
        else:
            feedback.update("Incorrect. Let's try a simpler question.")
            feedback.remove_class("correct")
            feedback.add_class("incorrect")
            if result.outcome == Outcome.DRILL_DOWN:
                # A prefetched simpler question is already on the stack.
                self._show_continue_action()
            else:  # NEEDS_SIMPLER — generate one targeting the misconception.
                self.query_one("#loading").display = True
                self.query_one("#loading-label").display = True
                self.query_one("#question-container").display = False
                self.generate_question(result.prior_question_text, result.selected_answer)

        feedback.display = True

    def _show_continue_action(self) -> None:
        """Show continue button."""
        actions = self.query_one("#actions")
        self.query_one("#continue-btn").display = True
        self.query_one("#new-question-btn").display = False
        self.query_one("#next-skill-btn").display = False
        actions.display = True

    def _show_skill_complete_actions(self) -> None:
        """Show actions after completing a skill."""
        actions = self.query_one("#actions")
        self.query_one("#continue-btn").display = False
        self.query_one("#new-question-btn").display = True
        self.query_one("#next-skill-btn").display = True
        actions.display = True

        feedback = self.query_one("#feedback")
        feedback.update(
            "Well done — you've completed this skill."
        )

    def _continue(self) -> None:
        """Continue to the next question in stack."""
        self._display_question()

    def _new_question(self) -> None:
        """Generate a new question for the current skill."""
        self.query_one("#loading").display = True
        self.query_one("#loading-label").display = True
        self.query_one("#question-container").display = False
        self.query_one("#actions").display = False
        self.generate_question()

    def _next_skill(self) -> None:
        """Move to the next skill."""
        self.session.advance_skill()
        self._save_progress()
        self._start_skill()

    def _complete_topic(self) -> None:
        """Called when all skills are complete."""
        # Mark session as completed
        if self.db_session:
            with SessionService() as service:
                service.complete_session(self.db_session)

        self.notify(
            f"Congratulations! You've completed all skills for '{self.topic}'!",
            severity="information",
        )
        self.app.pop_screen()

    def action_pause_session(self) -> None:
        """Pause and exit the session."""
        self._save_progress()

        if self.db_session:
            with SessionService() as service:
                service.pause_session(self.db_session)

        self.notify("Session paused - you can resume later", severity="information")
        self.app.pop_screen()
