"""Configuration management for recque_tui."""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables
load_dotenv()


@dataclass
class Config:
    """Application configuration."""

    # AI Settings
    default_model: str = "gpt-4o-mini"
    model: str = field(default_factory=lambda: os.getenv("RECQUE_MODEL", "gpt-4o-mini"))
    valid_models: list[str] = field(
        default_factory=lambda: ["gpt-4o", "gpt-4o-mini", "o3-mini"]
    )

    # Database Settings
    db_path: Path = field(
        default_factory=lambda: Path(os.getenv("RECQUE_DB_PATH", "data/recque.db"))
    )

    # Logging Settings
    log_file: Path = field(
        default_factory=lambda: Path(os.getenv("RECQUE_LOG_FILE", "recque.log"))
    )
    log_level: int = logging.INFO

    # UI Settings
    text_wrap_width: int = 80

    # Mock Mode (for testing/offline use)
    mock_mode: bool = field(
        default_factory=lambda: os.getenv("RECQUE_MOCK_MODE", "").lower() in ("1", "true", "yes")
    )

    # Prompt Rules (for question generation)
    prompt_rules: str = """Keep the question under 50 words.
Provide at least two incorrect but plausible and realistic alternative answers.
The alternative answers ideally should target common misconceptions.
Each answer should be no more than 20 words.
Ensure there is exactly one correct answer, verify that it is correct.
Ensure it is not obvious which answer is correct; in terms of being longer or containing more information.
Do not provide a prefix for the index of each alternative answer, such as a number, letter, dash or other characters."""


_config: Config | None = None


def get_config() -> Config:
    """Get the application configuration singleton."""
    global _config
    if _config is None:
        _config = Config()
    return _config


def configure_logging() -> None:
    """Configure application logging."""
    config = get_config()
    logging.basicConfig(
        level=config.log_level,
        format="{asctime} - {levelname} - {message}",
        style="{",
        datefmt="%Y-%m-%d %H:%M",
        filename=str(config.log_file),
        encoding="utf-8",
        filemode="a",
    )
