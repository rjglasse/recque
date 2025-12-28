"""Entry point for recque_tui application."""

import argparse
import sys

from recque_tui.config import configure_logging, get_config


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog="recque",
        description="RecQue - Recursive Questioning for adaptive learning",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run in mock mode (no API calls, uses sample questions)",
    )
    parser.add_argument(
        "--model",
        choices=["gpt-4o", "gpt-4o-mini", "o3-mini"],
        help="AI model to use (default: gpt-4o-mini)",
    )
    return parser.parse_args()


def main() -> int:
    """Main entry point for the application."""
    args = parse_args()

    # Apply CLI args to config
    config = get_config()
    if args.mock:
        config.mock_mode = True
    if args.model:
        config.model = args.model

    configure_logging()

    # Import here to ensure logging is configured first
    from recque_tui.ui.app import RecqueApp

    app = RecqueApp()
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
