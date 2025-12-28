"""Analytics and metrics for learning progress."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta

from recque_tui.database.schema import (
    LearningSession,
    QuestionAttempt,
    Skill,
    Topic,
    TopicMastery,
    get_or_create_default_user,
    get_session_factory,
)


@dataclass
class PerformanceMetrics:
    """Overall performance metrics."""
    total_questions: int
    correct_answers: int
    accuracy: float
    avg_time_seconds: float
    avg_stack_depth: float
    total_sessions: int
    completed_sessions: int
    topics_studied: int


@dataclass
class TopicMetrics:
    """Metrics for a specific topic."""
    topic_name: str
    questions_answered: int
    correct_answers: int
    accuracy: float
    mastery_level: float
    avg_stack_depth: float
    time_spent_seconds: int
    last_practiced: datetime | None


@dataclass
class LearningCurve:
    """Learning curve data point."""
    date: datetime
    accuracy: float
    questions_count: int
    cumulative_accuracy: float


class Analytics:
    """Analytics engine for learning metrics."""

    def __init__(self):
        """Initialize analytics."""
        self._factory = get_session_factory()

    def get_overall_metrics(self) -> PerformanceMetrics:
        """Get overall performance metrics.

        Returns:
            PerformanceMetrics object.
        """
        with self._factory() as db:
            user = get_or_create_default_user(db)

            # Session stats
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

            # Question stats
            attempts = (
                db.query(QuestionAttempt)
                .join(LearningSession)
                .filter(LearningSession.user_id == user.id)
                .all()
            )

            total_questions = len(attempts)
            correct_answers = sum(1 for a in attempts if a.is_correct)
            accuracy = correct_answers / total_questions if total_questions > 0 else 0

            times = [a.time_taken_seconds for a in attempts if a.time_taken_seconds]
            avg_time = sum(times) / len(times) if times else 0

            depths = [a.stack_depth for a in attempts]
            avg_depth = sum(depths) / len(depths) if depths else 0

            # Topics studied
            topics_studied = (
                db.query(TopicMastery)
                .filter_by(user_id=user.id)
                .count()
            )

            return PerformanceMetrics(
                total_questions=total_questions,
                correct_answers=correct_answers,
                accuracy=accuracy,
                avg_time_seconds=avg_time,
                avg_stack_depth=avg_depth,
                total_sessions=total_sessions,
                completed_sessions=completed_sessions,
                topics_studied=topics_studied,
            )

    def get_topic_metrics(self) -> list[TopicMetrics]:
        """Get metrics for each topic.

        Returns:
            List of TopicMetrics objects.
        """
        with self._factory() as db:
            user = get_or_create_default_user(db)

            masteries = (
                db.query(TopicMastery)
                .filter_by(user_id=user.id)
                .all()
            )

            results = []
            for m in masteries:
                topic = db.query(Topic).get(m.topic_id)
                if not topic:
                    continue

                # Get attempts for this topic's skills
                skill_ids = [s.id for s in topic.skills]
                attempts = (
                    db.query(QuestionAttempt)
                    .join(LearningSession)
                    .filter(
                        LearningSession.user_id == user.id,
                        QuestionAttempt.question.has(
                            skill_id=db.query(Skill.id).filter(Skill.topic_id == topic.id).scalar_subquery()
                        ),
                    )
                    .all()
                )

                depths = [a.stack_depth for a in attempts]
                avg_depth = sum(depths) / len(depths) if depths else 0

                times = [a.time_taken_seconds for a in attempts if a.time_taken_seconds]
                total_time = sum(times)

                results.append(TopicMetrics(
                    topic_name=topic.name,
                    questions_answered=m.questions_answered,
                    correct_answers=m.questions_correct,
                    accuracy=m.mastery_level,
                    mastery_level=m.mastery_level,
                    avg_stack_depth=avg_depth,
                    time_spent_seconds=total_time,
                    last_practiced=m.last_practiced_at,
                ))

            return sorted(results, key=lambda x: x.mastery_level, reverse=True)

    def get_knowledge_gaps(self, threshold: float = 0.5) -> list[dict]:
        """Identify topics where user has knowledge gaps.

        Args:
            threshold: Mastery threshold below which is considered a gap.

        Returns:
            List of knowledge gap info dicts.
        """
        with self._factory() as db:
            user = get_or_create_default_user(db)

            gaps = []

            # Get topics with low mastery
            masteries = (
                db.query(TopicMastery)
                .filter(
                    TopicMastery.user_id == user.id,
                    TopicMastery.mastery_level < threshold,
                    TopicMastery.questions_answered >= 3,  # Need some data
                )
                .all()
            )

            for m in masteries:
                topic = db.query(Topic).get(m.topic_id)
                if not topic:
                    continue

                # Analyze wrong answers to find patterns
                # This is a simplified version - could be more sophisticated
                gaps.append({
                    "topic": topic.name,
                    "mastery": m.mastery_level,
                    "questions_answered": m.questions_answered,
                    "correct": m.questions_correct,
                    "gap_size": threshold - m.mastery_level,
                })

            return sorted(gaps, key=lambda x: x["gap_size"], reverse=True)

    def get_learning_curve(self, days: int = 30) -> list[LearningCurve]:
        """Get learning curve data over time.

        Args:
            days: Number of days to include.

        Returns:
            List of LearningCurve data points.
        """
        with self._factory() as db:
            user = get_or_create_default_user(db)

            start_date = datetime.utcnow() - timedelta(days=days)

            attempts = (
                db.query(QuestionAttempt)
                .join(LearningSession)
                .filter(
                    LearningSession.user_id == user.id,
                    QuestionAttempt.attempted_at >= start_date,
                )
                .order_by(QuestionAttempt.attempted_at)
                .all()
            )

            # Group by date
            by_date = defaultdict(list)
            for a in attempts:
                date_key = a.attempted_at.date()
                by_date[date_key].append(a)

            results = []
            cumulative_correct = 0
            cumulative_total = 0

            for date in sorted(by_date.keys()):
                day_attempts = by_date[date]
                correct = sum(1 for a in day_attempts if a.is_correct)
                total = len(day_attempts)
                accuracy = correct / total if total > 0 else 0

                cumulative_correct += correct
                cumulative_total += total
                cumulative_accuracy = (
                    cumulative_correct / cumulative_total
                    if cumulative_total > 0
                    else 0
                )

                results.append(LearningCurve(
                    date=datetime.combine(date, datetime.min.time()),
                    accuracy=accuracy,
                    questions_count=total,
                    cumulative_accuracy=cumulative_accuracy,
                ))

            return results

    def get_session_history(self, limit: int = 20) -> list[dict]:
        """Get detailed session history.

        Args:
            limit: Maximum sessions to return.

        Returns:
            List of session info dicts.
        """
        with self._factory() as db:
            user = get_or_create_default_user(db)

            sessions = (
                db.query(LearningSession)
                .filter_by(user_id=user.id)
                .order_by(LearningSession.started_at.desc())
                .limit(limit)
                .all()
            )

            results = []
            for session in sessions:
                topic = db.query(Topic).get(session.topic_id)

                # Get attempt stats for this session
                attempts = session.attempts
                total = len(attempts)
                correct = sum(1 for a in attempts if a.is_correct)
                accuracy = correct / total if total > 0 else 0

                depths = [a.stack_depth for a in attempts]
                max_depth = max(depths) if depths else 0

                duration = None
                if session.ended_at and session.started_at:
                    duration = (session.ended_at - session.started_at).total_seconds()

                results.append({
                    "id": session.id,
                    "topic": topic.name if topic else "Unknown",
                    "status": session.status,
                    "started_at": session.started_at,
                    "ended_at": session.ended_at,
                    "duration_seconds": duration,
                    "questions_answered": total,
                    "correct_answers": correct,
                    "accuracy": accuracy,
                    "max_stack_depth": max_depth,
                })

            return results

    def get_streak_info(self) -> dict:
        """Get learning streak information.

        Returns:
            Dict with streak info.
        """
        with self._factory() as db:
            user = get_or_create_default_user(db)

            # Get all session dates
            sessions = (
                db.query(LearningSession)
                .filter_by(user_id=user.id)
                .order_by(LearningSession.started_at.desc())
                .all()
            )

            if not sessions:
                return {"current_streak": 0, "longest_streak": 0, "total_days": 0}

            # Get unique dates
            dates = set()
            for s in sessions:
                dates.add(s.started_at.date())

            dates = sorted(dates, reverse=True)

            # Calculate current streak
            today = datetime.utcnow().date()
            current_streak = 0

            for i, date in enumerate(dates):
                expected = today - timedelta(days=i)
                if date == expected:
                    current_streak += 1
                else:
                    break

            # Calculate longest streak
            longest_streak = 0
            current_run = 1

            for i in range(1, len(dates)):
                if dates[i - 1] - dates[i] == timedelta(days=1):
                    current_run += 1
                else:
                    longest_streak = max(longest_streak, current_run)
                    current_run = 1

            longest_streak = max(longest_streak, current_run)

            return {
                "current_streak": current_streak,
                "longest_streak": longest_streak,
                "total_days": len(dates),
            }
