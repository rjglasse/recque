"""AI client wrapper supporting Anthropic (Claude) and OpenAI backends."""

import logging
import os
from typing import Type, TypeVar

from pydantic import BaseModel

from recque_tui.config import get_config
from recque_tui.core.mock_generator import get_mock_generator
from recque_tui.core.models import Question, Review, SkillMap

T = TypeVar("T", bound=BaseModel)

logger = logging.getLogger(__name__)


class AIClient:
    """AI client supporting Claude (anthropic SDK), OpenAI, and mock backends.

    Backend selection:
      1. RECQUE_BACKEND env var (explicit override): anthropic|openai|mock
      2. Auto-detect: ANTHROPIC_API_KEY → anthropic, else OPENAI_API_KEY → openai, else mock
    """

    def __init__(self, model: str | None = None, mock_mode: bool | None = None):
        config = get_config()
        self.mock_mode = mock_mode if mock_mode is not None else config.mock_mode
        self._anthropic_client = None
        self._openai_client = None
        self.fell_back_to_mock = False

        self.has_anthropic = bool(os.getenv("ANTHROPIC_API_KEY"))
        self.has_openai = bool(os.getenv("OPENAI_API_KEY"))

        explicit_backend = (config.backend or "").lower()
        if explicit_backend == "anthropic":
            self.backend = "anthropic"
            self.model = model or os.getenv("RECQUE_MODEL", "claude-sonnet-4-20250514")
        elif explicit_backend == "openai":
            self.backend = "openai"
            self.model = model or os.getenv("RECQUE_MODEL", config.model)
        elif explicit_backend == "mock":
            self.backend = "mock"
            self.mock_mode = True
            self.model = "mock"
        elif self.has_anthropic:
            self.backend = "anthropic"
            self.model = model or os.getenv("RECQUE_MODEL", "claude-sonnet-4-20250514")
        elif self.has_openai:
            self.backend = "openai"
            self.model = model or os.getenv("RECQUE_MODEL", config.model)
        else:
            self.backend = "mock"
            self.mock_mode = True
            self.model = "mock"

        if self.mock_mode:
            self.backend = "mock"
            logger.info("AI Client running in mock mode")
        else:
            logger.info(f"AI Client using {self.backend} ({self.model})")

    @property
    def anthropic_client(self):
        if self._anthropic_client is None:
            import anthropic
            self._anthropic_client = anthropic.Anthropic()
        return self._anthropic_client

    @property
    def openai_client(self):
        if self._openai_client is None:
            from openai import OpenAI
            self._openai_client = OpenAI()
        return self._openai_client

    def generate(self, prompt: str, response_format: Type[T]) -> T:
        if self.mock_mode:
            return self._generate_mock(prompt, response_format)

        self.fell_back_to_mock = False

        if self.backend == "anthropic":
            try:
                return self._generate_anthropic(prompt, response_format)
            except Exception as e:
                logger.error(f"Anthropic API error: {e}")
                if self.has_openai:
                    logger.info("Falling back to OpenAI")
                    try:
                        return self._generate_openai(prompt, response_format)
                    except Exception as e2:
                        logger.error(f"OpenAI fallback also failed: {e2}")
                logger.info("Falling back to mock generator")
                self.fell_back_to_mock = True
                return self._generate_mock(prompt, response_format)
        else:
            try:
                return self._generate_openai(prompt, response_format)
            except Exception as e:
                logger.error(f"OpenAI API error: {e}")
                logger.info("Falling back to mock generator")
                self.fell_back_to_mock = True
                return self._generate_mock(prompt, response_format)

    def _generate_anthropic(self, prompt: str, response_format: Type[T]) -> T:
        schema = response_format.model_json_schema()

        tool_name = response_format.__name__.lower()
        tool = {
            "name": tool_name,
            "description": f"Return the {response_format.__name__} data",
            "input_schema": schema,
        }

        message = self.anthropic_client.messages.create(
            model=self.model,
            max_tokens=1024,
            tools=[tool],
            tool_choice={"type": "tool", "name": tool_name},
            messages=[{"role": "user", "content": prompt}],
        )

        for block in message.content:
            if block.type == "tool_use":
                result = response_format.model_validate(block.input)
                logger.info(f"Anthropic response: {result}")
                return result

        raise ValueError("No tool_use block in Anthropic response")

    def _generate_openai(self, prompt: str, response_format: Type[T]) -> T:
        completion = self.openai_client.beta.chat.completions.parse(
            model=self.model if self.backend == "openai" else "gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            response_format=response_format,
        )
        result = completion.choices[0].message.parsed
        logger.info(f"OpenAI response: {result}")
        return result

    def _generate_mock(self, prompt: str, response_format: Type[T]) -> T:
        mock = get_mock_generator()

        if response_format == SkillMap:
            topic = self._extract_topic_from_prompt(prompt)
            return mock.generate_skillmap(topic)
        elif response_format == Question:
            skill = self._extract_skill_from_prompt(prompt)
            return mock.generate_question(skill)
        elif response_format == Review:
            return Review(valid=True, correct_answer="Mock answer")
        else:
            raise ValueError(f"Unsupported response format for mock: {response_format}")

    def _extract_topic_from_prompt(self, prompt: str) -> str:
        prompt_lower = prompt.lower()
        if "topic:" in prompt_lower:
            parts = prompt.split("topic:")
            if len(parts) > 1:
                return parts[1].split("\n")[0].strip().strip('"\'')
        if "learn" in prompt_lower and "about" in prompt_lower:
            idx = prompt_lower.find("about")
            return prompt[idx + 5:].split("\n")[0].strip().strip('"\'')
        return "general knowledge"

    def _extract_skill_from_prompt(self, prompt: str) -> str:
        prompt_lower = prompt.lower()
        if "skill:" in prompt_lower:
            parts = prompt.split("skill:")
            if len(parts) > 1:
                return parts[1].split("\n")[0].strip().strip('"\'')
        # Match "question about: SKILL" pattern from new prompts
        if "question about:" in prompt_lower:
            idx = prompt_lower.find("question about:")
            return prompt[idx + 15:].split("\n")[0].strip().strip('"\'')
        # Match "studying: SKILL" pattern
        if "is studying:" in prompt_lower:
            idx = prompt_lower.find("is studying:")
            return prompt[idx + 12:].split("\n")[0].strip().strip('"\'')
        # Match "about {skill}" early in the prompt (first "about" before any newline)
        for line in prompt.split("\n"):
            line_lower = line.lower()
            if "about" in line_lower and ("generate" in line_lower or "question" in line_lower or "skill" in line_lower):
                idx = line_lower.find("about")
                extracted = line[idx + 5:].strip().strip('"\'').rstrip(".")
                if extracted and len(extracted) > 3:
                    return extracted
        return "general"
