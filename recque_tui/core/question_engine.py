"""Question generation and management."""

import hashlib
import logging
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING

from recque_tui.config import get_config
from recque_tui.core.ai_client import AIClient
from recque_tui.core.models import Question, Review, SkillMap

if TYPE_CHECKING:
    from recque_tui.database.repositories import QuestionRepository

logger = logging.getLogger(__name__)


class QuestionEngine:
    """Handles question generation with caching and prefetching."""

    def __init__(
        self,
        ai_client: AIClient | None = None,
        question_repo: "QuestionRepository | None" = None,
    ):
        """Initialize the question engine.

        Args:
            ai_client: The AI client to use. If None, creates a new one.
            question_repo: The question repository for caching. If None, no caching.
        """
        self.ai_client = ai_client or AIClient()
        self.question_repo = question_repo
        self.config = get_config()

    def generate_skillmap(self, topic: str) -> list[str]:
        """Generate a list of skills for a topic.

        Args:
            topic: The topic to generate skills for.

        Returns:
            A list of skill names.
        """
        prompt = f"""Task:
Generate a list of skills for the topic: {topic}.

Instructions:
The list of skills should contain 3 concepts in a natural progression that are important to understand the topic.
The response should only be the skills and no other additional information.
There is no need to provide an index of skill, such as a number, dash or other characters."""

        skillmap = self.ai_client.generate(prompt, SkillMap)
        return skillmap.skills

    def generate_question(
        self,
        skill: str,
        prior_question: str | None = None,
        prior_answer: str | None = None,
        variation: bool = False,
    ) -> Question:
        """Generate a question for a skill.

        Args:
            skill: The skill to generate a question for.
            prior_question: The previous question (for simpler/variation questions).
            prior_answer: The user's incorrect answer (for simpler questions).
            variation: If True, generate a harder variation instead of simpler.

        Returns:
            A Question object.
        """
        # Check cache first
        if self.question_repo and not prior_question:
            question_hash = self._compute_hash(skill, prior_question, prior_answer, variation)
            cached = self.question_repo.get_by_hash(question_hash)
            if cached:
                logger.info(f"Cache hit for question hash: {question_hash}")
                return cached

        # Build prompt
        if variation:
            prompt = f"""Task:
Generate a new question about {skill} that is a more challenging variation of the previous question.
They answered this correctly: {prior_question}.

Make sure you follow these rules: {self.config.prompt_rules}"""
        elif prior_question:
            prompt = f"""Task:
Generate a simpler question about {skill} based on the question that was incorrectly answered: {prior_question}.
The learner answered: {prior_answer}. This was incorrect and shows they do not understand all the concepts.
Try use their misconception and formulate a new related question to help explain the misconception.
Perhaps try to break down the original question into smaller parts that help simplify it.

Make sure you follow these rules: {self.config.prompt_rules}"""
        else:
            prompt = f"""Task:
Create an engaging, insightful and challenging multiple choice question that focuses on this skill: {skill}.

Make sure you follow these rules: {self.config.prompt_rules}"""

        question = self.ai_client.generate(prompt, Question)

        # Cache the question
        if self.question_repo and not prior_question:
            question_hash = self._compute_hash(skill, prior_question, prior_answer, variation)
            self.question_repo.save(question, skill, question_hash)

        return question

    def prefetch_simpler_questions(
        self, topic: str, skill: str, current_question: Question
    ) -> dict[str, Question]:
        """Prefetch simpler questions for all incorrect answers in parallel.

        Args:
            topic: The current topic.
            skill: The current skill.
            current_question: The question being displayed.

        Returns:
            A dict mapping incorrect answers to their simpler questions.
        """
        prefetched: dict[str, Question] = {}
        full_skill = f"{topic}. {skill}"

        def generate_for_answer(answer: str) -> tuple[str, Question]:
            """Generate a simpler question for an incorrect answer."""
            simpler = self.generate_question(
                full_skill,
                prior_question=current_question.question_text,
                prior_answer=answer,
            )
            return answer, simpler

        with ThreadPoolExecutor(max_workers=len(current_question.incorrect_answers)) as executor:
            futures = [
                executor.submit(generate_for_answer, answer)
                for answer in current_question.incorrect_answers
            ]

            for future in as_completed(futures):
                answer, question = future.result()
                prefetched[answer] = question

        return prefetched

    def verify_question(self, question: Question) -> Question:
        """Verify a question has a correct answer and repair if needed.

        Args:
            question: The question to verify.

        Returns:
            The verified (possibly repaired) question.
        """
        prompt = f"""Task:
You are given a multiple-choice question, along with possible answers.
Your goal is to determine if at least one of the provided answers is correct.

Question:
{question.question_text}

Possible Answers:
{question.incorrect_answers} and {question.correct_answer}

Instructions:
- Solve the given question step by step, showing the intermediate steps if necessary.
- Determine the correct answer.
- Check if the correct answer matches one of the possible answers.
- If the correct answer is not among the possible answers, provide the correct answer."""

        review = self.ai_client.generate(prompt, Review)

        if not review.valid:
            logger.warning("Question had no correct answer; repairing question.")
            question.correct_answer = review.correct_answer

        return question

    @staticmethod
    def shuffle_answers(question: Question) -> list[str]:
        """Shuffle the answers for display.

        Args:
            question: The question to shuffle answers for.

        Returns:
            A shuffled list of all answers.
        """
        answers = question.all_answers()
        random.shuffle(answers)
        return answers

    @staticmethod
    def judge(question: Question, selected_answer: str) -> bool:
        """Judge if the selected answer is correct.

        Args:
            question: The question being answered.
            selected_answer: The user's selected answer.

        Returns:
            True if correct, False otherwise.
        """
        return question.correct_answer == selected_answer

    @staticmethod
    def _compute_hash(
        skill: str,
        prior_question: str | None,
        prior_answer: str | None,
        variation: bool,
    ) -> str:
        """Compute a hash for caching questions."""
        content = f"{skill}|{prior_question}|{prior_answer}|{variation}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
