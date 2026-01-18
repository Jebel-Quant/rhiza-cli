"""Tests for the summarise command.

This module verifies that `summarise` generates correct PR descriptions based on
staged changes and `.rhiza/template.yml` configuration.
"""

import shutil
import subprocess

import pytest
from typer.testing import CliRunner

from rhiza.cli import app
from rhiza.commands.summarise import summarise


class TestSummariseCommand:
    """Tests for the summarise command."""

    @pytest.fixture
    def git_repo(self, tmp_path):
        """Create a temporary git repository."""
        repo = tmp_path / "test_repo"
        repo.mkdir()

        git_cmd = shutil.which("git") or "git"
        subprocess.run([git_cmd, "init"], cwd=repo, check=True)
        subprocess.run([git_cmd, "config", "user.email", "test@test.com"], cwd=repo, check=True)
        subprocess.run([git_cmd, "config", "user.name", "Test"], cwd=repo, check=True)

        return repo

    def test_summarise_default_config(self, git_repo, capsys):
        """Test summarise with default configuration (missing template.yml)."""
        git_cmd = shutil.which("git") or "git"

        # Create and stage a file
        test_file = git_repo / "test.txt"
        test_file.write_text("test content")
        subprocess.run([git_cmd, "add", "."], cwd=git_repo, check=True)

        # Run summarise directly
        summarise(git_repo)

        captured = capsys.readouterr()
        output = captured.out

        # Verify default template info is used
        assert "jebel-quant/rhiza" in output
        assert "main" in output
        assert "files added" in output
        assert "Change Summary" in output

    def test_summarise_custom_config(self, git_repo, capsys):
        """Test summarise with custom template.yml configuration."""
        git_cmd = shutil.which("git") or "git"

        # Create custom template.yml
        rhiza_dir = git_repo / ".rhiza"
        rhiza_dir.mkdir()
        template_file = rhiza_dir / "template.yml"
        template_file.write_text('template-repository: "my-org/my-template"\ntemplate-branch: "v2"\n')

        # Create and stage a file
        test_file = git_repo / "feature.py"
        test_file.write_text("def feature(): pass")
        subprocess.run([git_cmd, "add", "."], cwd=git_repo, check=True)

        # Run summarise directly
        summarise(git_repo)

        captured = capsys.readouterr()
        output = captured.out

        # Verify custom template info is used
        assert "my-org/my-template" in output
        assert "v2" in output
        assert "files added" in output

    def test_summarise_cli_integration(self, git_repo):
        """Test summarise command via CLI invoke."""
        git_cmd = shutil.which("git") or "git"

        # Create custom template.yml
        rhiza_dir = git_repo / ".rhiza"
        rhiza_dir.mkdir()
        template_file = rhiza_dir / "template.yml"
        template_file.write_text('template-repository: "cli-test/repo"\ntemplate-branch: "dev"\n')

        # Create and stage a file
        test_file = git_repo / "cli_test.txt"
        test_file.write_text("cli test")
        subprocess.run([git_cmd, "add", "."], cwd=git_repo, check=True)

        runner = CliRunner()
        result = runner.invoke(app, ["summarise", str(git_repo)])

        assert result.exit_code == 0
        assert "cli-test/repo" in result.stdout
        assert "dev" in result.stdout
        assert "Template Synchronization" in result.stdout
