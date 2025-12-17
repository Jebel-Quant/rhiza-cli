"""Tests for the init command and CLI wiring.

This module verifies that `init` creates/validates `.github/template.yml` and
that the Typer CLI entry `rhiza init` works as expected.
"""

from pathlib import Path

import yaml
from typer.testing import CliRunner

from rhiza import cli
from rhiza.commands.init import init


class TestInitCommand:
    """Tests for the init command."""

    def test_init_creates_default_template_yml(self, tmp_path):
        """Test that init creates a default template.yml when it doesn't exist."""
        init(tmp_path)

        # Verify template.yml was created
        template_file = tmp_path / ".github" / "template.yml"
        assert template_file.exists()

        # Verify it contains expected content
        with open(template_file) as f:
            config = yaml.safe_load(f)

        assert config["template-repository"] == "jebel-quant/rhiza"
        assert config["template-branch"] == "main"
        assert ".github" in config["include"]
        assert ".editorconfig" in config["include"]
        assert "Makefile" in config["include"]

    def test_init_validates_existing_template_yml(self, tmp_path):
        """Test that init validates an existing template.yml."""
        # Create existing template.yml
        github_dir = tmp_path / ".github"
        github_dir.mkdir()
        template_file = github_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump(
                {
                    "template-repository": "custom/repo",
                    "template-branch": "dev",
                    "include": [".github", "Makefile"],
                },
                f,
            )

        # Run init - should validate without error
        init(tmp_path)

        # Verify original content is preserved
        with open(template_file) as f:
            config = yaml.safe_load(f)

        assert config["template-repository"] == "custom/repo"
        assert config["template-branch"] == "dev"

    def test_init_warns_on_missing_template_repository(self, tmp_path):
        """Test that init warns when template-repository is missing."""
        # Create template.yml without template-repository
        github_dir = tmp_path / ".github"
        github_dir.mkdir()
        template_file = github_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump({"template-branch": "main", "include": [".github"]}, f)

        # Run init - should validate but warn
        init(tmp_path)
        # If we reach here, the function completed without raising an exception

    def test_init_warns_on_missing_include(self, tmp_path):
        """Test that init warns when include field is missing or empty."""
        # Create template.yml without include
        github_dir = tmp_path / ".github"
        github_dir.mkdir()
        template_file = github_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump({"template-repository": "jebel-quant/rhiza", "template-branch": "main"}, f)

        # Run init - should validate but warn
        init(tmp_path)

    def test_init_creates_github_directory(self, tmp_path):
        """Test that init creates .github directory if it doesn't exist."""
        init(tmp_path)

        github_dir = tmp_path / ".github"
        assert github_dir.exists()
        assert github_dir.is_dir()

    def test_init_cli_command(self):
        """Test the CLI init command via Typer runner."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(cli.app, ["init"])
            assert result.exit_code == 0
            assert Path(".github/template.yml").exists()
