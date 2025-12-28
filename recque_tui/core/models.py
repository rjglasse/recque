"""Pydantic models for structured AI outputs."""

from pydantic import BaseModel


class SkillMap(BaseModel):
    """A list of skills for a given topic."""
    skills: list[str]


class Question(BaseModel):
    """A multiple-choice question with one correct answer."""
    question_text: str
    correct_answer: str
    incorrect_answers: list[str]

    def all_answers(self) -> list[str]:
        """Return all answers (correct + incorrect)."""
        return [self.correct_answer] + self.incorrect_answers


class Review(BaseModel):
    """Validation response for question verification."""
    valid: bool
    correct_answer: str


class QuestionAttempt(BaseModel):
    """Record of a user's answer attempt."""
    question_id: int | None = None
    selected_answer: str
    is_correct: bool
    time_taken_seconds: int | None = None
    stack_depth: int = 0


class SessionState(BaseModel):
    """Current state of a learning session."""
    topic: str
    current_skill_index: int = 0
    skills: list[str] = []
    question_stack: list[Question] = []
    marked_incorrect: dict[int, list[str]] = {}  # question index -> list of marked wrong answers
