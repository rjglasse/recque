"""Journey screen for browsing and managing learning journeys."""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Static

from recque_tui.database.repositories import JourneyRepository, TopicRepository
from recque_tui.domain.journey import SessionManager


class JourneyScreen(Screen):
    """Screen for browsing and creating learning journeys."""

    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
    ]

    def compose(self) -> ComposeResult:
        """Compose the journey screen UI."""
        yield Header()

        with Container(id="content"):
            yield Static(
                "[bold magenta]Learning Journeys[/bold magenta]",
                id="title",
            )
            yield Static(
                "Curated paths through related topics for comprehensive learning.",
                id="subtitle",
            )

            yield Static("")  # Spacer

            # Predefined journeys
            yield Static("[bold]Available Journeys[/bold]", classes="section-header")
            with Vertical(id="journey-list"):
                yield Static("Loading journeys...", id="journeys-loading")

            yield Static("")  # Spacer

            # Create custom journey
            yield Static("[bold]Create Custom Journey[/bold]", classes="section-header")
            yield Input(
                placeholder="Journey name (e.g., 'Web Development Fundamentals')",
                id="journey-name-input",
            )
            yield Button("Create Journey", id="create-journey-btn")

            yield Static("")  # Spacer

            # Recent topics (for adding to journeys)
            yield Static("[bold]Recent Topics[/bold]", classes="section-header")
            with Vertical(id="topic-list"):
                yield Static("Loading topics...", id="topics-loading")

        yield Footer()

    def on_mount(self) -> None:
        """Load journeys and topics on mount."""
        self._load_journeys()
        self._load_topics()

    def _load_journeys(self) -> None:
        """Load available journeys."""
        with JourneyRepository() as repo:
            journeys = repo.get_all()

        loading = self.query_one("#journeys-loading")
        loading.remove()

        journey_list = self.query_one("#journey-list")

        if not journeys:
            journey_list.mount(
                Static(
                    "[dim]No journeys yet. Create one below![/dim]",
                    classes="no-items",
                )
            )
            return

        for i, journey in enumerate(journeys):
            steps_count = len(journey.steps)
            label = f"{journey.name}\n[dim]{journey.description or 'No description'} | {steps_count} topics[/dim]"
            btn = Button(label, id=f"journey-{journey.id}", classes="journey-card")
            journey_list.mount(btn)

    def _load_topics(self) -> None:
        """Load recent topics."""
        with TopicRepository() as repo:
            topics = repo.get_all()

        loading = self.query_one("#topics-loading")
        loading.remove()

        topic_list = self.query_one("#topic-list")

        if not topics:
            topic_list.mount(
                Static(
                    "[dim]No topics learned yet. Start learning to see topics here.[/dim]",
                    classes="no-items",
                )
            )
            return

        # Show recent topics (limit to 5)
        for topic in topics[:5]:
            skills_count = len(topic.skills)
            label = f"{topic.name} [dim]({skills_count} skills)[/dim]"
            topic_list.mount(Static(label, classes="topic-item"))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id

        if button_id == "create-journey-btn":
            self._create_journey()
        elif button_id and button_id.startswith("journey-"):
            journey_id = int(button_id.split("-")[1])
            self._start_journey(journey_id)

    def _create_journey(self) -> None:
        """Create a new journey."""
        name_input = self.query_one("#journey-name-input", Input)
        name = name_input.value.strip()

        if not name:
            self.notify("Please enter a journey name", severity="warning")
            return

        with JourneyRepository() as repo:
            repo.create(name)

        self.notify(f"Journey '{name}' created!", severity="information")
        name_input.value = ""

        # Refresh the journey list
        journey_list = self.query_one("#journey-list")
        for child in list(journey_list.children):
            child.remove()
        journey_list.mount(Static("Loading journeys...", id="journeys-loading"))
        self._load_journeys()

    def _start_journey(self, journey_id: int) -> None:
        """Start or continue a journey."""
        # For now, just show a message - full implementation would
        # find the next uncompleted topic in the journey
        self.notify(
            "Journey mode coming soon! For now, use Quick Start.",
            severity="information",
        )
