"""Knowledge graph for topic prerequisites and adaptive learning paths."""

from dataclasses import dataclass

from recque_tui.database.schema import (
    Topic,
    TopicMastery,
    TopicPrerequisite,
    get_or_create_default_user,
    get_session_factory,
)


@dataclass
class TopicNode:
    """A node in the knowledge graph."""
    id: int
    name: str
    mastery_level: float
    prerequisites: list["TopicNode"]
    is_ready: bool  # True if all prerequisites met


class KnowledgeGraph:
    """Manages topic prerequisites and adaptive learning recommendations."""

    def __init__(self):
        """Initialize the knowledge graph."""
        self._factory = get_session_factory()

    def add_prerequisite(
        self,
        topic_name: str,
        prerequisite_name: str,
        strength: float = 1.0,
    ) -> None:
        """Add a prerequisite relationship between topics.

        Args:
            topic_name: The topic that has a prerequisite.
            prerequisite_name: The prerequisite topic.
            strength: Importance of this prerequisite (0-1).
        """
        with self._factory() as db:
            # Get or create topics
            topic = db.query(Topic).filter_by(name=topic_name).first()
            if not topic:
                topic = Topic(name=topic_name)
                db.add(topic)
                db.flush()

            prereq = db.query(Topic).filter_by(name=prerequisite_name).first()
            if not prereq:
                prereq = Topic(name=prerequisite_name)
                db.add(prereq)
                db.flush()

            # Add prerequisite relationship
            existing = (
                db.query(TopicPrerequisite)
                .filter_by(topic_id=topic.id, prerequisite_topic_id=prereq.id)
                .first()
            )

            if not existing:
                rel = TopicPrerequisite(
                    topic_id=topic.id,
                    prerequisite_topic_id=prereq.id,
                    strength=strength,
                )
                db.add(rel)

            db.commit()

    def get_prerequisites(self, topic_name: str) -> list[str]:
        """Get prerequisites for a topic.

        Args:
            topic_name: The topic name.

        Returns:
            List of prerequisite topic names.
        """
        with self._factory() as db:
            topic = db.query(Topic).filter_by(name=topic_name).first()
            if not topic:
                return []

            prereqs = (
                db.query(TopicPrerequisite)
                .filter_by(topic_id=topic.id)
                .all()
            )

            result = []
            for p in prereqs:
                prereq_topic = db.query(Topic).get(p.prerequisite_topic_id)
                if prereq_topic:
                    result.append(prereq_topic.name)

            return result

    def check_readiness(self, topic_name: str, min_mastery: float = 0.6) -> dict:
        """Check if user is ready to learn a topic.

        Args:
            topic_name: The topic to check.
            min_mastery: Minimum mastery level required for prerequisites.

        Returns:
            Dict with readiness info.
        """
        with self._factory() as db:
            user = get_or_create_default_user(db)
            topic = db.query(Topic).filter_by(name=topic_name).first()

            if not topic:
                return {"ready": True, "missing": [], "weak": []}

            prereqs = (
                db.query(TopicPrerequisite)
                .filter_by(topic_id=topic.id)
                .all()
            )

            missing = []
            weak = []

            for p in prereqs:
                prereq_topic = db.query(Topic).get(p.prerequisite_topic_id)
                if not prereq_topic:
                    continue

                mastery = (
                    db.query(TopicMastery)
                    .filter_by(user_id=user.id, topic_id=prereq_topic.id)
                    .first()
                )

                if not mastery or mastery.questions_answered == 0:
                    missing.append(prereq_topic.name)
                elif mastery.mastery_level < min_mastery * p.strength:
                    weak.append({
                        "topic": prereq_topic.name,
                        "current": mastery.mastery_level,
                        "required": min_mastery * p.strength,
                    })

            return {
                "ready": len(missing) == 0 and len(weak) == 0,
                "missing": missing,
                "weak": weak,
            }

    def recommend_next_topics(self, limit: int = 5) -> list[dict]:
        """Recommend topics to learn next based on mastery and prerequisites.

        Args:
            limit: Maximum recommendations to return.

        Returns:
            List of recommended topic dicts.
        """
        with self._factory() as db:
            user = get_or_create_default_user(db)

            # Get all topics
            all_topics = db.query(Topic).all()

            recommendations = []

            for topic in all_topics:
                mastery = (
                    db.query(TopicMastery)
                    .filter_by(user_id=user.id, topic_id=topic.id)
                    .first()
                )

                current_level = mastery.mastery_level if mastery else 0

                # Skip topics with high mastery
                if current_level >= 0.9:
                    continue

                # Check readiness
                readiness = self.check_readiness(topic.name)

                # Calculate priority score
                # Higher priority for: ready topics, lower mastery, fewer missing prereqs
                if readiness["ready"]:
                    priority = 1.0 - current_level
                else:
                    # Penalize for missing/weak prerequisites
                    penalty = len(readiness["missing"]) * 0.3 + len(readiness["weak"]) * 0.1
                    priority = max(0, (1.0 - current_level) - penalty)

                recommendations.append({
                    "topic": topic.name,
                    "current_mastery": current_level,
                    "ready": readiness["ready"],
                    "missing_prereqs": readiness["missing"],
                    "priority": priority,
                })

            # Sort by priority
            recommendations.sort(key=lambda x: x["priority"], reverse=True)

            return recommendations[:limit]

    def get_learning_path(self, target_topic: str) -> list[str]:
        """Get an ordered learning path to reach a target topic.

        Args:
            target_topic: The topic to learn.

        Returns:
            Ordered list of topics to learn.
        """
        with self._factory() as db:
            user = get_or_create_default_user(db)
            topic = db.query(Topic).filter_by(name=target_topic).first()

            if not topic:
                return [target_topic]

            path = []
            visited = set()

            def visit(t: Topic) -> None:
                if t.id in visited:
                    return
                visited.add(t.id)

                # Get prerequisites
                prereqs = (
                    db.query(TopicPrerequisite)
                    .filter_by(topic_id=t.id)
                    .order_by(TopicPrerequisite.strength.desc())
                    .all()
                )

                for p in prereqs:
                    prereq_topic = db.query(Topic).get(p.prerequisite_topic_id)
                    if prereq_topic:
                        # Check if already mastered
                        mastery = (
                            db.query(TopicMastery)
                            .filter_by(user_id=user.id, topic_id=prereq_topic.id)
                            .first()
                        )

                        if not mastery or mastery.mastery_level < 0.6:
                            visit(prereq_topic)

                path.append(t.name)

            visit(topic)
            return path
