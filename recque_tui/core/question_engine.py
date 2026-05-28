"""Question generation and management."""

import hashlib
import logging
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import TYPE_CHECKING

from recque_tui.config import get_config
from recque_tui.core.ai_client import AIClient
from recque_tui.core.models import Question, Review, SkillMap

if TYPE_CHECKING:
    from recque_tui.database.repositories import QuestionRepository

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert educator creating adaptive multiple-choice questions.
Your questions should test genuine understanding, not surface-level recall.
Use concrete scenarios, code snippets, real-world analogies, or thought experiments where appropriate.
Every incorrect answer should represent a specific, named misconception — not just a plausible-sounding wrong option.
After the question, provide a concise explanation of why the correct answer is right and what each wrong answer reveals about the learner's misunderstanding."""

PROMPT_RULES = """Rules for the question:
- The question can use a scenario, code snippet, diagram description, or thought experiment to set context.
- Provide exactly 3 incorrect answers, each targeting a distinct misconception.
- The correct answer must be unambiguously right.
- Do not make the correct answer longer or more detailed than the distractors.
- Do not prefix answers with letters, numbers, or dashes.
- Provide a brief explanation (2-3 sentences) that says why the correct answer is right and what each wrong answer reveals about the learner's thinking."""


@dataclass
class LearningContext:
    """Context about the learner's current state, fed into prompts for adaptation."""
    stack_breadcrumbs: list[str] | None = None
    questions_answered: int = 0
    questions_correct: int = 0
    stack_depth: int = 0


class QuestionEngine:
    """Handles question generation with caching and prefetching."""

    def __init__(
        self,
        ai_client: AIClient | None = None,
        question_repo: "QuestionRepository | None" = None,
    ):
        self.ai_client = ai_client or AIClient()
        self.question_repo = question_repo
        self.config = get_config()

    def generate_skillmap(self, topic: str) -> list[str]:
        prompt = f"""Generate a learning path for the topic: {topic}.

Provide exactly 3 skills that form a natural progression from foundational to advanced.
Each skill should be specific and assessable — not vague categories.
For example, for "Python decorators": not "Basics, Intermediate, Advanced" but "First-class functions and closures", "Writing simple decorators", "Decorators with arguments and stacking".
Return only the skill names."""

        skillmap = self.ai_client.generate(prompt, SkillMap)
        return skillmap.skills

    def generate_question(
        self,
        skill: str,
        prior_question: str | None = None,
        prior_answer: str | None = None,
        variation: bool = False,
        context: LearningContext | None = None,
    ) -> Question:
        if self.question_repo and not prior_question:
            question_hash = self._compute_hash(skill, prior_question, prior_answer, variation)
            cached = self.question_repo.get_by_hash(question_hash)
            if cached:
                logger.info(f"Cache hit for question hash: {question_hash}")
                return cached

        context_section = self._build_context_section(context)

        if variation:
            prompt = f"""{SYSTEM_PROMPT}

The learner correctly answered this question about {skill}:
"{prior_question}"

{context_section}

Generate a harder follow-up question that builds on the same concept but requires deeper understanding.
Raise the difficulty: introduce edge cases, combine concepts, or require applying the idea in an unfamiliar context.

{PROMPT_RULES}"""
        elif prior_question:
            prompt = f"""{SYSTEM_PROMPT}

The learner is studying: {skill}

They were asked: "{prior_question}"
They answered: "{prior_answer}" — this was INCORRECT.

{context_section}

Diagnose the misconception behind their answer. Then generate a simpler question that directly addresses that specific misunderstanding.
The new question should help the learner discover *why* their answer was wrong, not just test a simpler version of the same fact.
Think about what prerequisite knowledge they might be missing and target that.

{PROMPT_RULES}"""
        else:
            prompt = f"""{SYSTEM_PROMPT}

Generate a question about: {skill}

{context_section}

Create a question that tests genuine understanding of this skill.
Use a concrete scenario, code example, or real-world situation where possible.
The question should require thinking, not just recall.

{PROMPT_RULES}"""

        question = self.ai_client.generate(prompt, Question)

        if self.question_repo and not prior_question:
            question_hash = self._compute_hash(skill, prior_question, prior_answer, variation)
            self.question_repo.save(question, skill, question_hash)

        return question

    def _build_context_section(self, context: LearningContext | None) -> str:
        if not context:
            return ""

        parts = []

        if context.questions_answered > 0:
            accuracy = context.questions_correct / context.questions_answered * 100
            parts.append(
                f"Session performance: {context.questions_correct}/{context.questions_answered} "
                f"correct ({accuracy:.0f}% accuracy)."
            )

            if accuracy >= 80:
                parts.append("The learner is doing well — challenge them.")
            elif accuracy >= 50:
                parts.append("The learner is struggling somewhat — aim for clarity over difficulty.")
            else:
                parts.append("The learner is finding this hard — use simple, concrete language and build confidence.")

        if context.stack_depth > 1 and context.stack_breadcrumbs:
            chain = " → ".join(f'"{b}"' for b in context.stack_breadcrumbs)
            parts.append(
                f"The learner has drilled down {context.stack_depth - 1} level(s) "
                f"through these questions: {chain}. "
                f"Each level was triggered by a wrong answer. Keep simplifying."
            )

        if not parts:
            return ""
        return "Learner context:\n" + "\n".join(parts)

    def prefetch_simpler_questions(
        self, topic: str, skill: str, current_question: Question,
        context: LearningContext | None = None,
    ) -> dict[str, Question]:
        prefetched: dict[str, Question] = {}
        full_skill = f"{topic}. {skill}"

        def generate_for_answer(answer: str) -> tuple[str, Question]:
            simpler = self.generate_question(
                full_skill,
                prior_question=current_question.question_text,
                prior_answer=answer,
                context=context,
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
        prompt = f"""You are given a multiple-choice question, along with possible answers.
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
        answers = question.all_answers()
        random.shuffle(answers)
        return answers

    @staticmethod
    def judge(question: Question, selected_answer: str) -> bool:
        return question.correct_answer == selected_answer

    @staticmethod
    def _compute_hash(
        skill: str,
        prior_question: str | None,
        prior_answer: str | None,
        variation: bool,
    ) -> str:
        content = f"{skill}|{prior_question}|{prior_answer}|{variation}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
