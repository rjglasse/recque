"""Session picker screen for resuming paused sessions."""

from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static

from recque_tui.domain.journey import SessionManager


class SessionPickerScreen(ModalScreen):
    """Modal screen for picking a session to resume."""

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(
        self,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ):
        """Initialize the session picker."""
        super().__init__(name=name, id=id, classes=classes)
        self.sessions: list[dict] = []

    def compose(self) -> ComposeResult:
        """Compose the session picker UI."""
        with Container(id="session-picker-container"):
            yield Static("[bold]Resume a Session[/bold]", id="picker-title")
            yield Static(
                "Select a session to continue learning:",
                id="picker-subtitle",
            )

            with Vertical(id="session-list"):
                yield Static("Loading sessions...", id="sessions-loading")

            yield Button("Cancel", id="cancel-btn", variant="default")

    def on_mount(self) -> None:
        """Load sessions on mount."""
        self._load_sessions()

    def _load_sessions(self) -> None:
        """Load resumable sessions from database."""
        with SessionManager() as manager:
            self.sessions = manager.get_resumable_sessions()

        # Remove loading message
        loading = self.query_one("#sessions-loading")
        loading.remove()

        session_list = self.query_one("#session-list")

        if not self.sessions:
            session_list.mount(Static("No sessions to resume.", classes="no-sessions"))
            return

        # Add session buttons
        for i, session_info in enumerate(self.sessions):
            topic = session_info["topic"]
            status = session_info["status"]
            started = session_info["started_at"].strftime("%Y-%m-%d %H:%M")
            skills_completed = session_info["skills_completed"]
            total_skills = session_info["total_skills"]

            progress = (
                f"{skills_completed}/{total_skills} skills"
                if total_skills > 0
                else "In progress"
            )

            label = f"{topic}\n[dim]{status} | {started} | {progress}[/dim]"

            btn = Button(label, id=f"session-{i}", classes="session-item")
            session_list.mount(btn)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id

        if button_id == "cancel-btn":
            self.dismiss(None)
        elif button_id and button_id.startswith("session-"):
            index = int(button_id.split("-")[1])
            session_info = self.sessions[index]
            self.dismiss(session_info["session"])

    def action_cancel(self) -> None:
        """Cancel and close the picker."""
        self.dismiss(None)
