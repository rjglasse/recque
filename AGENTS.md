# AGENTS.md

Guidance for AI assistants working in this repo. Canonical agent-guidance file — `CLAUDE.md` is kept in sync with this one (the project-specific sections are identical; the auto-managed Beads Integration block at the bottom is managed by `bd init`).

## What this project is

RecQue is an adaptive learning TUI built with Textual. The hook is **recursive questioning**: when the learner answers incorrectly, a simpler question targeting the misconception is pushed onto a stack; when they answer correctly, the stack pops and they "climb back up." AI (OpenAI by default, Anthropic optional) generates questions and skill maps; SQLite persists sessions, progress, and a question cache.

Single-user, single-process desktop app. There's also a small FastAPI web variant in `recque_web/` and original prototypes in `legacy/` — both secondary; the TUI is the active product.

## Run / test

```bash
uv sync                     # install
uv run recque               # launch TUI
uv run pytest -q            # full test suite
uv run pytest tests/test_learning_stack.py   # one file
uv run ruff check .         # lint
```

Requires `OPENAI_API_KEY` for live AI calls. Tests don't hit the API — `tests/test_mock_generator.py` exercises a deterministic mock generator.

## Layout

```
recque_tui/
  core/            # Stack mechanics, AI client, question engine, Pydantic DTOs
  application/     # Application services (session lifecycle, etc.) — orchestrates domain + persistence
  domain/          # Cross-aggregate read models and analyses: knowledge graph, analytics
  database/        # SQLAlchemy ORM + repositories
  ui/              # Textual app, screens, widgets, styles
recque_web/        # FastAPI variant (secondary)
legacy/            # Pre-TUI prototypes — do not modify unless asked
tests/             # pytest, no API calls
data/              # SQLite DB, auto-created (gitignored)
```

## Architecture notes (read before refactoring)

The directory names suggest DDD layering, but **the boundaries are weaker than they look**. Specifics worth knowing:

- **`application/session_service.py:SessionService` is the single path for session lifecycle.** UI screens use it for create/pause/resume/complete/save_progress/get_resumable_sessions/get_session_state. It uses `SessionRepository` and `TopicRepository` under the hood. The old `domain/journey.py:SessionManager` was deleted — don't reintroduce it.
- **`domain/` code calls SQLAlchemy directly.** `Analytics` and `KnowledgeGraph` build `self._db.query(...)` chains. They aren't pure domain logic — closer to read models. Map to domain objects at the boundary if you touch them ([recque-5v9](#) tracks this).
- **`QuestionRepository.save` creates topics/skills as a side effect** (look for `"_uncategorized"`). A repository making domain decisions — be careful changing it; the mock generator and live engine both rely on it. [recque-tx0](#) tracks removal.
- **`core/learning_stack.py` is the cleanest domain object.** Pure logic, no DB, has invariants (push/pop/breadcrumb/depth). The plan is to promote it into a full `Session` aggregate ([recque-9d1](#)).
- **`ui/screens/question_screen.py` still orchestrates the engine, the stack, and session persistence** (~430 lines). When extending question flow, resist adding more orchestration there; route through services. [recque-nm1](#) tracks expanding the application layer to thin this screen.
- **Two model styles coexist**: Pydantic (`core/models.py`, used for AI-structured output) and dataclasses (`StackEntry`, `LearningContext`). Repositories sometimes return Pydantic `Question`, sometimes ORM `CachedQuestion` — be explicit about which you expect.

## Conventions

- Python 3.11+, type hints throughout, `from __future__ import annotations` is **not** in use — keep current style (PEP 604 `X | None` unions, no future import).
- Ruff is configured (line length 100, E501 ignored). Run `ruff check` before declaring done.
- Tests use plain pytest + `MagicMock`. No fixtures library beyond what's in `tests/conftest.py`.
- Logging via the stdlib `logging` module; modules use `logger = logging.getLogger(__name__)`.
- DB sessions: repositories and `SessionService` accept an optional `Session` for composition; if omitted they own one and close it on `__exit__`. Don't break that contract.
- The `LearningStack` serializes via `to_dict` / `from_dict` to `SessionProgress.stack_state_json`. Changing its shape is a migration concern.

## Issue tracking

This project uses **beads** (`bd`) for issue tracking — see the Beads Issue Tracker section at the end of this file for the full workflow. Do not use markdown TODO lists, MEMORY.md, or harness Task tools for project-level work tracking.

Quick start: `bd ready` to see available work, `bd show <id>` for details, `bd update <id> --claim` to start, `bd close <id>` when done.

## Refactor direction (in progress)

A light DDD refactor is underway. **Done:**

- ✅ Collapsed `SessionManager`/`SessionRepository` duplication into one path. `recque_tui/application/SessionService` is the new orchestrator; `domain/journey.py` is gone.

**Remaining** (filed as beads issues — run `bd show <id>` for full detail):

- `recque-9d1` — Promote `LearningStack` into a real `Session` aggregate owning skills, current index, stack, and exposing `answer(...)` / `advance_skill()` with invariants.
- `recque-nm1` — Expand the application service layer (AnswerQuestionService, StartSessionService, etc.) so `question_screen.py` becomes mostly presentation. *Blocked by recque-9d1.*
- `recque-5v9` — Repositories return domain objects, not ORM rows. *Blocked by recque-9d1.*
- `recque-tx0` — Stop `QuestionRepository.save` from inventing `_uncategorized` topics.

Don't do full tactical DDD (private setters everywhere, value objects per primitive, domain events) — overkill for a ~4.5k LoC single-user TUI.

## Things to avoid

- Don't add features to `legacy/` — it's preserved as-is for historical reference.
- Don't change the `LearningStack` serialization format without a migration story for existing `session_progress.stack_state_json` rows.
- Don't introduce a new ORM session pattern; follow the owns-session-or-borrows-one pattern already in `BaseRepository` and `SessionService`.
- Don't put AI prompts in UI code — prompts live in `core/question_engine.py`.
- Don't bypass the question cache (`QuestionRepository.get_by_hash`) when adding new generation paths; it materially affects cost and latency.
- Don't track work in markdown files, MEMORY.md, or TaskCreate — use `bd` (see Beads Issue Tracker section below).

## When you need more context

- `README.md` — user-facing overview, usage, keyboard shortcuts.
- `recque_tui/core/question_engine.py` — prompt templates, generation rules, prefetch strategy.
- `recque_tui/database/schema.py` — full data model with relationships.
- `tests/` — best source of "what's the expected behavior" for repositories and the stack.

## Non-Interactive Shell Commands

Some shells alias `cp`, `mv`, and `rm` to interactive mode (`-i`), which can hang an automated agent waiting for input. Use the non-interactive forms:

```bash
cp -f source dest           # NOT: cp source dest
mv -f source dest           # NOT: mv source dest
rm -f file                  # NOT: rm file
rm -rf directory            # NOT: rm -r directory
cp -rf source dest          # NOT: cp -r source dest
```

Other commands that may prompt: `scp`/`ssh` (use `-o BatchMode=yes`), `apt-get` (use `-y`), `brew` (use `HOMEBREW_NO_AUTO_UPDATE=1`).

<!-- BEGIN BEADS INTEGRATION v:1 profile:minimal hash:ca08a54f -->
## Beads Issue Tracker

This project uses **bd (beads)** for issue tracking. Run `bd prime` to see full workflow context and commands.

### Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work
bd close <id>         # Complete work
```

### Rules

- Use `bd` for ALL task tracking — do NOT use TodoWrite, TaskCreate, or markdown TODO lists
- Run `bd prime` for detailed command reference and session close protocol
- Use `bd remember` for persistent knowledge — do NOT use MEMORY.md files

## Session Completion

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   bd dolt push
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds
<!-- END BEADS INTEGRATION -->
