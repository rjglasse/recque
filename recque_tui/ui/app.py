"""Main Textual application for recque."""

from textual.app import App, ComposeResult
from textual.binding import Binding

from recque_tui.database.repositories import initialize_database
from recque_tui.ui.screens.home_screen import HomeScreen


class RecqueApp(App):
    """The main recque TUI application."""

    TITLE = "RecQue - Recursive Questioning"
    CSS_PATH = "styles/theme.tcss"

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("h", "go_home", "Home", show=True),
        Binding("?", "show_help", "Help", show=True),
    ]

    SCREENS = {
        "home": HomeScreen,
    }

    def __init__(self):
        """Initialize the application."""
        super().__init__()
        # Initialize database on startup
        initialize_database()

    def on_mount(self) -> None:
        """Handle mount event."""
        self.push_screen("home")

    def action_go_home(self) -> None:
        """Navigate to home screen."""
        # Pop all screens and go back to home
        while len(self.screen_stack) > 1:
            self.pop_screen()
        if self.screen.id != "home":
            self.push_screen("home")

    def action_show_help(self) -> None:
        """Show help screen."""
        self.notify("Help: Use arrow keys to navigate, Enter to select, q to quit")
