"""Database initialization and migration script."""

from recque_tui.database.repositories import initialize_database
from recque_tui.database.schema import init_database


def main():
    """Initialize the database."""
    print("Initializing recque database...")
    init_database()
    initialize_database()
    print("Database initialized successfully!")


if __name__ == "__main__":
    main()
