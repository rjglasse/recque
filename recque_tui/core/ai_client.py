"""OpenAI API client wrapper for structured outputs."""

import logging
from typing import Type, TypeVar

from openai import OpenAI
from pydantic import BaseModel

from recque_tui.config import get_config
from recque_tui.core.mock_generator import get_mock_generator
from recque_tui.core.models import Question, Review, SkillMap

T = TypeVar("T", bound=BaseModel)

logger = logging.getLogger(__name__)


class AIClient:
    """Wrapper for OpenAI API with structured output support."""

    def __init__(self, model: str | None = None, mock_mode: bool | None = None):
        """Initialize the AI client.

        Args:
            model: The model to use. If None, uses config default.
            mock_mode: If True, use mock generator instead of API.
                      If None, uses config setting.
        """
        config = get_config()
        self.mock_mode = mock_mode if mock_mode is not None else config.mock_mode
        self.model = model or config.model
        self.valid_models = config.valid_models
        self._client: OpenAI | None = None

        if self.model not in self.valid_models:
            logger.warning(f"Invalid model: {self.model}. Using default: {config.default_model}")
            self.model = config.default_model

        if self.mock_mode:
            logger.info("AI Client running in mock mode")

    @property
    def client(self) -> OpenAI:
        """Lazy initialization of OpenAI client."""
        if self._client is None:
            self._client = OpenAI()
        return self._client

    def generate(self, prompt: str, response_format: Type[T]) -> T:
        """Generate a structured response from the AI.

        Args:
            prompt: The prompt to send to the AI.
            response_format: The Pydantic model to parse the response into.

        Returns:
            The parsed response as the specified Pydantic model.

        Raises:
            Exception: If the API call fails and mock fallback is disabled.
        """
        if self.mock_mode:
            return self._generate_mock(prompt, response_format)

        try:
            completion = self.client.beta.chat.completions.parse(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format=response_format,
            )

            result = completion.choices[0].message.parsed
            logger.info(f"AI response: {result}")
            return result

        except Exception as e:
            logger.error(f"AI API error: {e}")
            logger.info("Falling back to mock generator")
            return self._generate_mock(prompt, response_format)

    def _generate_mock(self, prompt: str, response_format: Type[T]) -> T:
        """Generate a mock response using the mock generator.

        Args:
            prompt: The prompt (used to extract context).
            response_format: The expected response type.

        Returns:
            A mock response of the expected type.
        """
        mock = get_mock_generator()
        prompt_lower = prompt.lower()

        if response_format == SkillMap:
            # Extract topic from prompt
            topic = self._extract_topic_from_prompt(prompt)
            result = mock.generate_skillmap(topic)
            logger.info(f"Mock skillmap generated for: {topic}")
            return result

        elif response_format == Question:
            # Extract skill from prompt
            skill = self._extract_skill_from_prompt(prompt)
            result = mock.generate_question(skill)
            logger.info(f"Mock question generated for: {skill}")
            return result

        elif response_format == Review:
            # Mock verification always returns valid
            result = Review(valid=True, correct_answer="Mock answer")
            logger.info("Mock review generated")
            return result

        else:
            raise ValueError(f"Unsupported response format for mock: {response_format}")

    def _extract_topic_from_prompt(self, prompt: str) -> str:
        """Extract topic name from a skillmap generation prompt."""
        # Look for patterns like "topic: X" or "about X"
        prompt_lower = prompt.lower()
        if "topic:" in prompt_lower:
            parts = prompt.split("topic:")
            if len(parts) > 1:
                return parts[1].split("\n")[0].strip().strip('"\'')
        # Fall back to extracting from "I want to learn about X"
        if "learn" in prompt_lower and "about" in prompt_lower:
            idx = prompt_lower.find("about")
            return prompt[idx + 5:].split("\n")[0].strip().strip('"\'')
        # Default
        return "general knowledge"

    def _extract_skill_from_prompt(self, prompt: str) -> str:
        """Extract skill name from a question generation prompt."""
        prompt_lower = prompt.lower()
        if "skill:" in prompt_lower:
            parts = prompt.split("skill:")
            if len(parts) > 1:
                return parts[1].split("\n")[0].strip().strip('"\'')
        if "about" in prompt_lower:
            idx = prompt_lower.find("about")
            return prompt[idx + 5:].split("\n")[0].strip().strip('"\'')
        return "general"
