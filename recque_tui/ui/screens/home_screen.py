"""Home screen for recque TUI."""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, Static


class HomeScreen(Screen):
    """The home/landing screen."""

    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
    ]

    def compose(self) -> ComposeResult:
        """Compose the home screen UI."""
        yield Header()

        with Container(id="content"):
            yield Static(
                "[bold magenta]RecQue[/bold magenta] - Recursive Questioning",
                id="title",
            )
            yield Static(
                "Learn any topic through adaptive questioning. "
                "When you answer incorrectly, we dig deeper to find your knowledge gaps.",
                id="subtitle",
            )

            yield Static("")  # Spacer

            # Quick start section
            yield Static("[bold]Quick Start[/bold]", classes="section-header")
            yield Input(
                placeholder="Enter a topic to learn (e.g., 'Python basics', 'Quantum physics')",
                id="topic-input",
                classes="topic-input",
            )
            yield Button("Start Learning", id="start-btn", variant="primary")

            yield Static("")  # Spacer

            # Menu options
            yield Static("[bold]Menu[/bold]", classes="section-header")
            with Vertical(id="menu"):
                yield Button(
                    "Resume Session",
                    id="resume-btn",
                    classes="menu-item",
                )
                yield Button(
                    "Learning Journeys",
                    id="journeys-btn",
                    classes="menu-item",
                )
                yield Button(
                    "View Progress",
                    id="progress-btn",
                    classes="menu-item",
                )
                yield Button(
                    "Analytics",
                    id="analytics-btn",
                    classes="menu-item",
                )

        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id

        if button_id == "start-btn":
            self._start_learning()
        elif button_id == "resume-btn":
            self._show_resume_sessions()
        elif button_id == "journeys-btn":
            self._show_journeys()
        elif button_id == "progress-btn":
            self._show_progress()
        elif button_id == "analytics-btn":
            self._show_analytics()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter key in input field."""
        if event.input.id == "topic-input":
            self._start_learning()

    def _start_learning(self) -> None:
        """Start a new learning session."""
        topic_input = self.query_one("#topic-input", Input)
        topic = topic_input.value.strip()

        if not topic:
            self.notify("Please enter a topic", severity="warning")
            return

        # Import here to avoid circular imports
        from recque_tui.ui.screens.question_screen import QuestionScreen

        self.app.push_screen(QuestionScreen(topic=topic))

    def _show_resume_sessions(self) -> None:
        """Show resumable sessions."""
        from recque_tui.ui.screens.session_picker import SessionPickerScreen

        def on_session_selected(session) -> None:
            """Handle session selection."""
            if session:
                from recque_tui.ui.screens.question_screen import QuestionScreen
                self.app.push_screen(QuestionScreen(resume_session=session))

        self.app.push_screen(SessionPickerScreen(), on_session_selected)

    def _show_journeys(self) -> None:
        """Show learning journeys."""
        from recque_tui.ui.screens.journey_screen import JourneyScreen
        self.app.push_screen(JourneyScreen())

    def _show_progress(self) -> None:
        """Show progress screen."""
        from recque_tui.ui.screens.progress_screen import ProgressScreen
        self.app.push_screen(ProgressScreen())

    def _show_analytics(self) -> None:
        """Show analytics screen."""
        # Analytics will reuse progress screen for now, with more detail later
        from recque_tui.ui.screens.progress_screen import ProgressScreen
        self.app.push_screen(ProgressScreen())
