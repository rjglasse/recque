"""Progress screen showing learning progress and mastery."""

from textual.app import ComposeResult
from textual.containers import Container, Grid, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, ProgressBar, Static

from recque_tui.database.schema import (
    Topic,
    TopicMastery,
    get_or_create_default_user,
    get_session_factory,
)
from recque_tui.domain.journey import SessionManager


class ProgressScreen(Screen):
    """Screen showing learning progress and mastery levels."""

    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
    ]

    def compose(self) -> ComposeResult:
        """Compose the progress screen UI."""
        yield Header()

        with Container(id="content"):
            yield Static(
                "[bold magenta]Learning Progress[/bold magenta]",
                id="title",
            )

            yield Static("")  # Spacer

            # Summary stats
            yield Static("[bold]Summary[/bold]", classes="section-header")
            with Horizontal(id="summary-stats"):
                yield Static("", id="total-sessions")
                yield Static("", id="total-topics")
                yield Static("", id="total-questions")

            yield Static("")  # Spacer

            # Topic mastery
            yield Static("[bold]Topic Mastery[/bold]", classes="section-header")
            with Vertical(id="mastery-list"):
                yield Static("Loading mastery data...", id="mastery-loading")

            yield Static("")  # Spacer

            # Recent sessions
            yield Static("[bold]Recent Sessions[/bold]", classes="section-header")
            with Vertical(id="session-history"):
                yield Static("Loading session history...", id="history-loading")

        yield Footer()

    def on_mount(self) -> None:
        """Load progress data on mount."""
        self._load_summary()
        self._load_mastery()
        self._load_history()

    def _load_summary(self) -> None:
        """Load summary statistics."""
        factory = get_session_factory()
        with factory() as db:
            user = get_or_create_default_user(db)

            # Count sessions
            from recque_tui.database.schema import LearningSession, QuestionAttempt

            total_sessions = (
                db.query(LearningSession)
                .filter_by(user_id=user.id)
                .count()
            )

            completed_sessions = (
                db.query(LearningSession)
                .filter_by(user_id=user.id, status="completed")
                .count()
            )

            # Count topics with mastery
            total_topics = (
                db.query(TopicMastery)
                .filter_by(user_id=user.id)
                .count()
            )

            # Count questions answered
            total_questions = (
                db.query(QuestionAttempt)
                .join(LearningSession)
                .filter(LearningSession.user_id == user.id)
                .count()
            )

        self.query_one("#total-sessions").update(
            f"[bold]{completed_sessions}[/bold]/{total_sessions} sessions"
        )
        self.query_one("#total-topics").update(
            f"[bold]{total_topics}[/bold] topics studied"
        )
        self.query_one("#total-questions").update(
            f"[bold]{total_questions}[/bold] questions answered"
        )

    def _load_mastery(self) -> None:
        """Load topic mastery levels."""
        factory = get_session_factory()
        with factory() as db:
            user = get_or_create_default_user(db)

            masteries = (
                db.query(TopicMastery)
                .filter_by(user_id=user.id)
                .order_by(TopicMastery.mastery_level.desc())
                .all()
            )

            mastery_data = []
            for m in masteries:
                topic = db.query(Topic).get(m.topic_id)
                if topic:
                    mastery_data.append({
                        "topic": topic.name,
                        "level": m.mastery_level,
                        "questions": m.questions_answered,
                        "correct": m.questions_correct,
                    })

        # Remove loading
        loading = self.query_one("#mastery-loading")
        loading.remove()

        mastery_list = self.query_one("#mastery-list")

        if not mastery_data:
            mastery_list.mount(
                Static(
                    "[dim]No mastery data yet. Complete some learning sessions![/dim]",
                    classes="no-items",
                )
            )
            return

        for data in mastery_data:
            level_pct = int(data["level"] * 100)
            accuracy = (
                f"{data['correct']}/{data['questions']}"
                if data["questions"] > 0
                else "-"
            )

            # Create mastery bar visualization
            bar_width = 20
            filled = int(bar_width * data["level"])
            bar = "█" * filled + "░" * (bar_width - filled)

            color = "green" if level_pct >= 70 else "yellow" if level_pct >= 40 else "red"

            label = (
                f"{data['topic']}\n"
                f"[{color}]{bar}[/{color}] {level_pct}% | {accuracy} correct"
            )
            mastery_list.mount(Static(label, classes="mastery-item"))

    def _load_history(self) -> None:
        """Load recent session history."""
        with SessionManager() as manager:
            completed = manager.get_completed_sessions(limit=5)

        # Remove loading
        loading = self.query_one("#history-loading")
        loading.remove()

        history_list = self.query_one("#session-history")

        if not completed:
            history_list.mount(
                Static(
                    "[dim]No completed sessions yet.[/dim]",
                    classes="no-items",
                )
            )
            return

        for session in completed:
            started = session["started_at"].strftime("%Y-%m-%d %H:%M")
            ended = (
                session["ended_at"].strftime("%H:%M")
                if session["ended_at"]
                else "?"
            )

            label = f"{session['topic']}\n[dim]{started} - {ended}[/dim]"
            history_list.mount(Static(label, classes="history-item"))
