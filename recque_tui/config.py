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
    default_model: str = "gpt-4o"
    model: str = field(default_factory=lambda: os.getenv("RECQUE_MODEL", "gpt-4o"))
    valid_models: list[str] = field(
        default_factory=lambda: ["gpt-4o", "gpt-4o-mini", "o3-mini", "gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano"]
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

    # Backend override (claude_cli|anthropic|openai|mock). Empty = auto-detect.
    # claude_cli is never auto-selected — must be explicit, since having `claude` on PATH
    # doesn't imply the user wants to route question generation through it.
    backend: str = field(
        default_factory=lambda: os.getenv("RECQUE_BACKEND", "").lower()
    )

    # Legacy prompt rules (kept for backward compatibility with TUI)
    prompt_rules: str = """Provide exactly 3 incorrect but plausible answers, each targeting a distinct misconception.
Ensure there is exactly one correct answer, verify that it is correct.
Ensure it is not obvious which answer is correct; in terms of being longer or containing more information.
Do not provide a prefix for the index of each alternative answer, such as a number, letter, dash or other characters.
Provide a brief explanation of why the correct answer is right."""


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
