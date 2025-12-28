"""Question screen - the core quiz interface."""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, LoadingIndicator, Static
from textual import work

from recque_tui.core.learning_stack import LearningStack
from recque_tui.core.models import Question
from recque_tui.core.question_engine import QuestionEngine
from recque_tui.database.schema import LearningSession
from recque_tui.domain.journey import SessionManager


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
        self.skills: list[str] = []
        self.current_skill_index = 0
        self.stack = LearningStack()
        self.engine = QuestionEngine()
        self.current_answers: list[str] = []
        self.prefetched: dict[str, Question] = {}
        self.answered = False
        self.questions_answered = 0
        self.questions_correct = 0
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
                yield Static("", id="stack-depth", classes="stack-depth")
                yield Static("", id="stats")

            # Loading indicator (shown while generating)
            yield LoadingIndicator(id="loading")

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

        if self.resume_session:
            self._resume_from_session()
        else:
            self.generate_skillmap()

    def _resume_from_session(self) -> None:
        """Resume from a saved session."""
        with SessionManager() as manager:
            state = manager.get_session_state(self.resume_session)
            if state:
                self.topic = state["topic"]
                self.skills = state["skills"]
                self.current_skill_index = state["current_skill_index"]
                self.db_session = self.resume_session

                # Restore stack if available
                if state["stack_data"]:
                    self.stack = LearningStack.from_dict(state["stack_data"])

                manager.resume_session(self.resume_session)

        self.query_one("#topic-label").update(f"[bold magenta]{self.topic}[/bold magenta]")

        if self.stack.is_empty:
            # Need to generate a new question
            self._start_skill()
        else:
            # Resume with existing stack
            skill = self.skills[self.current_skill_index]
            self.query_one("#skill-badge").update(f"[bold]{skill}[/bold]")
            self.query_one("#loading").display = False
            self._display_question()

    @work(thread=True)
    def generate_skillmap(self) -> None:
        """Generate the skillmap for the topic."""
        self.skills = self.engine.generate_skillmap(self.topic)
        self.call_from_thread(self._skillmap_ready)

    def _skillmap_ready(self) -> None:
        """Called when skillmap is ready."""
        if not self.skills:
            self.notify("Failed to generate skills", severity="error")
            self.app.pop_screen()
            return

        # Create database session
        with SessionManager() as manager:
            self.db_session = manager.create_session(self.topic, self.skills)

        self.query_one("#topic-label").update(f"[bold magenta]{self.topic}[/bold magenta]")
        self._start_skill()

    def _start_skill(self) -> None:
        """Start the current skill."""
        if self.current_skill_index >= len(self.skills):
            self._complete_topic()
            return

        skill = self.skills[self.current_skill_index]
        self.query_one("#skill-badge").update(f"[bold]{skill}[/bold]")
        self.stack.clear()
        self.generate_question()

    @work(thread=True)
    def generate_question(self, prior_question: str | None = None, prior_answer: str | None = None) -> None:
        """Generate a new question."""
        skill = f"{self.topic}. {self.skills[self.current_skill_index]}"
        question = self.engine.generate_question(skill, prior_question, prior_answer)

        # Prefetch simpler questions
        prefetched = self.engine.prefetch_simpler_questions(
            self.topic, self.skills[self.current_skill_index], question
        )

        self.call_from_thread(self._question_ready, question, prefetched)

    def _question_ready(self, question: Question, prefetched: dict[str, Question]) -> None:
        """Called when question is ready."""
        # Push to stack
        self.stack.push(question, prefetched)
        self.prefetched = prefetched

        # Save progress
        self._save_progress()

        # Update UI
        self._display_question()

    def _display_question(self) -> None:
        """Display the current question."""
        question = self.stack.peek()
        if not question:
            return

        # Shuffle answers
        self.current_answers = self.engine.shuffle_answers(question)
        self.answered = False

        # Update question text
        self.query_one("#question-text").update(question.question_text)

        # Update answer buttons
        entry = self.stack.current_entry()
        marked = entry.marked_incorrect if entry else []

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
        self.query_one("#question-container").display = True
        self.query_one("#feedback").display = False
        self.query_one("#actions").display = False

    def _update_stats(self) -> None:
        """Update the stats display."""
        depth = self.stack.depth
        skill_progress = f"{self.current_skill_index + 1}/{len(self.skills)}"
        self.query_one("#stack-depth").update(f"Depth: {depth} | Skill: {skill_progress}")

        accuracy = (
            f"{self.questions_correct}/{self.questions_answered}"
            if self.questions_answered > 0
            else "-"
        )
        self.query_one("#stats").update(f"Score: {accuracy}")

    def _save_progress(self) -> None:
        """Save current progress to database."""
        if self.db_session:
            with SessionManager() as manager:
                manager.save_progress(
                    self.db_session,
                    self.current_skill_index,
                    self.stack,
                    self.skills,
                )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id

        if button_id and button_id.startswith("answer-"):
            if not self.answered:
                index = int(button_id.split("-")[1])
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
        self.questions_answered += 1

        selected = self.current_answers[index]
        question = self.stack.peek()
        button = self.query_one(f"#answer-{index}", Button)

        # Disable all buttons
        for i in range(len(self.current_answers)):
            self.query_one(f"#answer-{i}", Button).disabled = True

        is_correct = self.engine.judge(question, selected)

        if is_correct:
            self.questions_correct += 1
            button.add_class("correct")
            self._show_feedback(True)
        else:
            button.add_class("incorrect")
            self.stack.mark_incorrect(selected)
            self._show_feedback(False, selected)

        self._update_stats()
        self._save_progress()

    def _show_feedback(self, correct: bool, selected_answer: str | None = None) -> None:
        """Show feedback after answering."""
        feedback = self.query_one("#feedback")

        if correct:
            feedback.update("[bold green]Correct![/bold green]")
            feedback.remove_class("incorrect")
            feedback.add_class("correct")

            # Check if we should pop or complete skill
            self.stack.pop()
            if self.stack.is_empty:
                # Skill complete
                self._show_skill_complete_actions()
            else:
                # Go back to previous question
                feedback.update(
                    "[bold green]Correct![/bold green] Let's go back to the earlier question."
                )
                self._show_continue_action()
        else:
            feedback.update(
                "[bold red]Incorrect.[/bold red] Let's try a simpler question."
            )
            feedback.remove_class("correct")
            feedback.add_class("incorrect")
            self._prepare_simpler_question(selected_answer)

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
            "[bold green]Well done! You've completed this skill.[/bold green]"
        )

    def _prepare_simpler_question(self, selected_answer: str) -> None:
        """Prepare a simpler question based on the incorrect answer."""
        # Get prefetched question
        simpler = self.prefetched.get(selected_answer)

        if simpler:
            # Use prefetched question
            self.stack.push(simpler)
            self._show_continue_action()
        else:
            # Generate new simpler question
            self.query_one("#loading").display = True
            self.query_one("#question-container").display = False
            question = self.stack.peek()
            self.generate_question(question.question_text, selected_answer)

    def _continue(self) -> None:
        """Continue to the next question in stack."""
        self._display_question()

    def _new_question(self) -> None:
        """Generate a new question for the current skill."""
        self.query_one("#loading").display = True
        self.query_one("#question-container").display = False
        self.query_one("#actions").display = False
        self.generate_question()

    def _next_skill(self) -> None:
        """Move to the next skill."""
        self.current_skill_index += 1
        self.stack.clear()
        self._save_progress()
        self._start_skill()

    def _complete_topic(self) -> None:
        """Called when all skills are complete."""
        # Mark session as completed
        if self.db_session:
            with SessionManager() as manager:
                manager.complete_session(self.db_session)

        self.notify(
            f"Congratulations! You've completed all skills for '{self.topic}'!",
            severity="information",
        )
        self.app.pop_screen()

    def action_pause_session(self) -> None:
        """Pause and exit the session."""
        self._save_progress()

        if self.db_session:
            with SessionManager() as manager:
                manager.pause_session(self.db_session)

        self.notify("Session paused - you can resume later", severity="information")
        self.app.pop_screen()
