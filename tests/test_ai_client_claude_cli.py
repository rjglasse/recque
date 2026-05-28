"""Tests for the claude_cli backend of AIClient."""

import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from recque_tui.core.ai_client import AIClient
from recque_tui.core.models import Question


def _claude_envelope(result_text: str, is_error: bool = False) -> str:
    """Construct a fake `claude -p --output-format json` envelope."""
    return json.dumps({
        "type": "result",
        "subtype": "success" if not is_error else "error",
        "is_error": is_error,
        "api_error_status": None if not is_error else 400,
        "result": result_text,
        "duration_ms": 1000,
        "total_cost_usd": 0.001,
        "usage": {},
        "session_id": "fake",
    })


def _question_json() -> str:
    return json.dumps({
        "question_text": "What is 2+2?",
        "correct_answer": "4",
        "incorrect_answers": ["3", "5", "22"],
        "explanation": "Arithmetic.",
    })


@pytest.fixture
def claude_cli_client(monkeypatch, tmp_path):
    """An AIClient forced into claude_cli mode, isolated from real env."""
    monkeypatch.setenv("RECQUE_BACKEND", "claude_cli")
    monkeypatch.delenv("RECQUE_MOCK_MODE", raising=False)
    monkeypatch.setattr("recque_tui.core.ai_client.shutil.which", lambda _: "/usr/bin/claude")
    # Reset the config singleton so the new env var takes effect
    import recque_tui.config
    monkeypatch.setattr(recque_tui.config, "_config", None)
    return AIClient()


class TestClaudeCliBackendSelection:
    def test_explicit_backend_selected(self, claude_cli_client):
        assert claude_cli_client.backend == "claude_cli"
        assert claude_cli_client.model == "sonnet"

    def test_raises_when_claude_not_on_path(self, monkeypatch):
        monkeypatch.setenv("RECQUE_BACKEND", "claude_cli")
        monkeypatch.setattr("recque_tui.core.ai_client.shutil.which", lambda _: None)
        import recque_tui.config
        monkeypatch.setattr(recque_tui.config, "_config", None)
        with pytest.raises(RuntimeError, match="not on PATH"):
            AIClient()


class TestClaudeCliGenerate:
    def test_happy_path_returns_validated_object(self, claude_cli_client):
        fake_proc = MagicMock(stdout=_claude_envelope(_question_json()), stderr="", returncode=0)
        with patch("subprocess.run", return_value=fake_proc) as mock_run:
            result = claude_cli_client.generate("Make a question.", Question)

        assert isinstance(result, Question)
        assert result.correct_answer == "4"
        # Verify ANTHROPIC_API_KEY stripped from subprocess env
        kwargs = mock_run.call_args.kwargs
        assert "ANTHROPIC_API_KEY" not in kwargs["env"]
        # Verify the schema is included in the prompt
        cmd = mock_run.call_args.args[0]
        assert cmd[0] == "claude"
        assert "--model" in cmd
        assert "sonnet" in cmd
        prompt_arg = cmd[cmd.index("-p") + 1]
        assert "question_text" in prompt_arg  # schema field appears

    def test_strips_markdown_fences(self, claude_cli_client):
        fenced = f"```json\n{_question_json()}\n```"
        fake_proc = MagicMock(stdout=_claude_envelope(fenced), stderr="", returncode=0)
        with patch("subprocess.run", return_value=fake_proc):
            result = claude_cli_client.generate("Make a question.", Question)
        assert result.correct_answer == "4"

    def test_retries_once_on_malformed_json(self, claude_cli_client):
        bad = MagicMock(stdout=_claude_envelope("this is not json"), stderr="", returncode=0)
        good = MagicMock(stdout=_claude_envelope(_question_json()), stderr="", returncode=0)
        with patch("subprocess.run", side_effect=[bad, good]) as mock_run:
            result = claude_cli_client.generate("Make a question.", Question)
        assert mock_run.call_count == 2
        assert result.correct_answer == "4"

    def test_envelope_error_falls_back_to_mock(self, claude_cli_client):
        err_env = _claude_envelope("Credit balance is too low", is_error=True)
        fake_proc = MagicMock(stdout=err_env, stderr="", returncode=0)
        with patch("subprocess.run", return_value=fake_proc):
            result = claude_cli_client.generate("Generate a question about: arithmetic", Question)
        # Did not raise — fell back to mock
        assert claude_cli_client.fell_back_to_mock is True
        assert isinstance(result, Question)

    def test_subprocess_failure_falls_back_to_mock(self, claude_cli_client):
        with patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(1, ["claude"], stderr="auth failed"),
        ):
            result = claude_cli_client.generate("Generate a question about: arithmetic", Question)
        assert claude_cli_client.fell_back_to_mock is True
        assert isinstance(result, Question)

    def test_timeout_falls_back_to_mock(self, claude_cli_client):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="claude", timeout=90)):
            result = claude_cli_client.generate("Generate a question about: arithmetic", Question)
        assert claude_cli_client.fell_back_to_mock is True
        assert isinstance(result, Question)

    def test_does_not_fallback_to_anthropic_or_openai(self, claude_cli_client, monkeypatch):
        """Even with API keys set, claude_cli should fall back only to mock."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")
        monkeypatch.setenv("OPENAI_API_KEY", "fake")
        with patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(1, ["claude"], stderr="fail"),
        ):
            # Patch the anthropic/openai paths to detect if they're called (they shouldn't be)
            with patch.object(claude_cli_client, "_generate_anthropic") as anth, \
                 patch.object(claude_cli_client, "_generate_openai") as openai:
                claude_cli_client.generate("Generate a question about: arithmetic", Question)
        anth.assert_not_called()
        openai.assert_not_called()
