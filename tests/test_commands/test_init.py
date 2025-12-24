"""Tests for the init command and CLI wiring.

This module verifies that `init` creates/validates `.github/rhiza/template.yml` and
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
        template_file = tmp_path / ".github" / "rhiza" / "template.yml"
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
        rhiza_dir = tmp_path / ".github" / "rhiza"
        rhiza_dir.mkdir(parents=True)
        template_file = rhiza_dir / "template.yml"

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
        rhiza_dir = tmp_path / ".github" / "rhiza"
        rhiza_dir.mkdir(parents=True)
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump({"template-branch": "main", "include": [".github"]}, f)

        # Run init - should validate but warn
        init(tmp_path)
        # If we reach here, the function completed without raising an exception

    def test_init_warns_on_missing_include(self, tmp_path):
        """Test that init warns when include field is missing or empty."""
        # Create template.yml without include
        rhiza_dir = tmp_path / ".github" / "rhiza"
        rhiza_dir.mkdir(parents=True)
        template_file = rhiza_dir / "template.yml"

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

    def test_init_migrates_old_template_location(self, tmp_path):
        """Test that init migrates template.yml from old location to new location."""
        # Create old location template.yml
        github_dir = tmp_path / ".github"
        github_dir.mkdir(parents=True)
        old_template_file = github_dir / "template.yml"

        with open(old_template_file, "w") as f:
            yaml.dump(
                {
                    "template-repository": "old/repo",
                    "template-branch": "legacy",
                    "include": [".github", "old-file"],
                },
                f,
            )

        # Run init - should migrate to new location
        init(tmp_path)

        # Verify template was copied to new location
        new_template_file = tmp_path / ".github" / "rhiza" / "template.yml"
        assert new_template_file.exists()

        # Verify content was preserved
        with open(new_template_file) as f:
            config = yaml.safe_load(f)

        assert config["template-repository"] == "old/repo"
        assert config["template-branch"] == "legacy"
        assert "old-file" in config["include"]

    def test_init_cli_command(self):
        """Test the CLI init command via Typer runner."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(cli.app, ["init"])
            assert result.exit_code == 0
            assert Path(".github/rhiza/template.yml").exists()

    def test_init_creates_correctly_formatted_files(self, tmp_path):
        """Test that init creates files with correct formatting (no indentation)."""
        init(tmp_path)

        # Check pyproject.toml content
        pyproject_file = tmp_path / "pyproject.toml"
        assert pyproject_file.exists()

        expected_pyproject = f"""\
[project]
name = "{tmp_path.name}"
version = "0.1.0"
description = "Add your description here"
readme = "README.md"
requires-python = ">=3.11"
dependencies = []
"""
        assert pyproject_file.read_text() == expected_pyproject

        # Check main.py content
        main_file = tmp_path / "src" / tmp_path.name / "main.py"
        assert main_file.exists()

        expected_main = """\
def say_hello(name: str) -> str:
    return f"Hello, {name}!"

def main():
    print(say_hello("World"))

if __name__ == "__main__":
    main()
"""
        assert main_file.read_text() == expected_main
