# RecQue - Recursive Questioning

An adaptive learning system that uses AI-generated questions to help learners master topics through recursive questioning. When you answer incorrectly, the system generates simpler questions targeting your misconception. Once you answer correctly, you "unwind" back to previous questions - creating a personalized learning path.

![Recursive Questioning Concept](https://github.com/user-attachments/assets/8b60dc82-c913-4553-9f1a-84e96efb4e9f)

## Features

- **Textual TUI**: Modern terminal interface with keyboard navigation
- **Recursive Learning**: Drill down into simpler questions when stuck, then work back up
- **Learning Journeys**: Multi-session progress tracking with curriculum paths
- **SQLite Database**: Persistent storage for sessions, progress, and question caching
- **Analytics**: Performance metrics, knowledge gaps, and learning curves
- **Knowledge Graph**: Topic prerequisites and adaptive recommendations

## Installation

Requires Python 3.11+ and an OpenAI API key.

```bash
# Clone the repository
git clone https://github.com/rjglasse/recque.git
cd recque

# Install with uv (recommended)
uv sync

# Or with pip
pip install -e .
```

Set your OpenAI API key:
```bash
export OPENAI_API_KEY="your-api-key"
```

## Usage

```bash
# Run with uv
uv run recque

# Or directly
python -m recque_tui.main
```

### Keyboard Shortcuts

- `1-4`: Select answer
- `Enter`: Confirm / Continue
- `Escape`: Pause session
- `h`: Go to home
- `q`: Quit

## Project Structure

```
recque/
├── recque_tui/           # Main application
│   ├── core/             # Business logic
│   │   ├── models.py     # Pydantic models
│   │   ├── ai_client.py  # OpenAI wrapper
│   │   ├── question_engine.py
│   │   └── learning_stack.py
│   ├── database/         # SQLite persistence
│   │   ├── schema.py     # SQLAlchemy models
│   │   └── repositories.py
│   ├── domain/           # Domain logic
│   │   ├── journey.py    # Session management
│   │   ├── knowledge_graph.py
│   │   └── analytics.py
│   └── ui/               # Textual TUI
│       ├── app.py
│       └── screens/
├── legacy/               # Original CLI/web implementations
├── data/                 # SQLite database (auto-created)
└── pyproject.toml
```

## How It Works

1. **Enter a topic** to learn (e.g., "Python basics")
2. **AI generates skills** - 3 progressive concepts for the topic
3. **Answer questions** - Multiple choice with AI-generated options
4. **Wrong answer?** Get a simpler question about your misconception
5. **Right answer?** Work back up to the previous question
6. **Complete skills** to progress through the topic

## Legacy Versions

The original CLI and web versions are preserved in `legacy/`:
- `legacy/recque.py` - Original terminal version
- `legacy/recque_web.py` - Flask web application

## License

MIT License - Copyright 2024 Ric Glassey
