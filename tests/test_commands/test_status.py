"""Tests for the status command and CLI wiring.

This module verifies that `status` reads `.rhiza/template.lock` and that
the Typer CLI entry `rhiza status` behaves as expected across scenarios.
"""

import pytest
import yaml
from loguru import logger
from typer.testing import CliRunner

from rhiza.cli import app
from rhiza.commands.status import status


@pytest.fixture
def log_sink():
    """Capture loguru output into a list for assertions."""
    messages: list[str] = []
    handler_id = logger.add(lambda msg: messages.append(msg), format="{message}", colorize=False)
    yield messages
    logger.remove(handler_id)


class TestStatusCommand:
    """Tests for the status command."""

    def test_status_warns_when_no_lock_file(self, tmp_path, log_sink):
        """Test that status warns when template.lock is absent."""
        status(tmp_path)

        output = "\n".join(log_sink)
        assert "template.lock" in output

    def test_status_displays_lock_info(self, tmp_path, log_sink):
        """Test that status prints all fields from a structured lock file."""
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        lock_file = rhiza_dir / "template.lock"
        lock_data = {
            "sha": "abcdef1234567890",
            "repo": "owner/repo",
            "host": "github",
            "ref": "main",
            "include": ["ci/", "docs/"],
            "exclude": [],
            "templates": [],
            "synced_at": "2025-01-01T00:00:00Z",
            "strategy": "merge",
            "files": ["ci/test.yml", "docs/index.md"],
        }
        lock_file.write_text(yaml.dump(lock_data))

        status(tmp_path)

        output = "\n".join(log_sink)
        assert "owner/repo" in output
        assert "main" in output
        assert "abcdef123456" in output
        assert "2025-01-01T00:00:00Z" in output
        assert "merge" in output
        assert "ci/" in output
        assert "2" in output  # file count

    def test_status_shows_templates_when_present(self, tmp_path, log_sink):
        """Test that status shows templates list when templates field is populated."""
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        lock_file = rhiza_dir / "template.lock"
        lock_data = {
            "sha": "abc123",
            "repo": "owner/repo",
            "host": "github",
            "ref": "main",
            "include": [],
            "exclude": [],
            "templates": ["python", "ci"],
            "synced_at": "",
            "strategy": "",
        }
        lock_file.write_text(yaml.dump(lock_data))

        status(tmp_path)

        output = "\n".join(log_sink)
        assert "python" in output
        assert "ci" in output


class TestStatusCli:
    """Tests for the `rhiza status` CLI entry point."""

    def test_cli_status_exits_zero_with_lock(self, tmp_path):
        """Test that the CLI returns exit code 0 when template.lock exists."""
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        lock_file = rhiza_dir / "template.lock"
        lock_data = {
            "sha": "abc123def456",
            "repo": "owner/repo",
            "host": "github",
            "ref": "main",
            "include": [],
            "exclude": [],
            "templates": [],
        }
        lock_file.write_text(yaml.dump(lock_data))

        runner = CliRunner()
        result = runner.invoke(app, ["status", str(tmp_path)])
        assert result.exit_code == 0

    def test_cli_status_exits_zero_without_lock(self, tmp_path):
        """Test that the CLI returns exit code 0 even when template.lock is absent (warning only)."""
        runner = CliRunner()
        result = runner.invoke(app, ["status", str(tmp_path)])
        assert result.exit_code == 0
