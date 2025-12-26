"""Tests for the init command and CLI wiring.

This module verifies that `init` creates/validates `.rhiza/template.yml` and
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
        template_file = tmp_path / ".rhiza" / "template.yml"
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
        rhiza_dir = tmp_path / ".rhiza"
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
        rhiza_dir = tmp_path / ".rhiza"
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
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump({"template-repository": "jebel-quant/rhiza", "template-branch": "main"}, f)

        # Run init - should validate but warn
        init(tmp_path)

    def test_init_creates_rhiza_directory(self, tmp_path):
        """Test that init creates .rhiza directory if it doesn't exist."""
        init(tmp_path)

        rhiza_dir = tmp_path / ".rhiza"
        assert rhiza_dir.exists()
        assert rhiza_dir.is_dir()

    def test_init_with_old_template_location(self, tmp_path):
        """Test that init works when template.yml exists in old location."""
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

        # Run init - should create new template in new location
        init(tmp_path)

        # Verify new template was created in new location
        new_template_file = tmp_path / ".rhiza" / "template.yml"
        assert new_template_file.exists()

        # Verify it has default content (not copied from old location)
        with open(new_template_file) as f:
            config = yaml.safe_load(f)

        assert config["template-repository"] == "jebel-quant/rhiza"

        # Old file should still exist (not moved)
        assert old_template_file.exists()

    def test_init_cli_command(self):
        """Test the CLI init command via Typer runner."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(cli.app, ["init"])
            assert result.exit_code == 0
            assert Path(".rhiza/template.yml").exists()

    def test_init_creates_correctly_formatted_files(self, tmp_path):
        """Test that init creates files with correct formatting (no indentation)."""
        init(tmp_path)

        # Check pyproject.toml content
        pyproject_file = tmp_path / "pyproject.toml"
        assert pyproject_file.exists()

        # We expect the default template output
        content = pyproject_file.read_text()
        assert f'name = "{tmp_path.name}"' in content
        assert 'packages = ["src/' in content

        # Check main.py content
        main_file = tmp_path / "src" / tmp_path.name / "main.py"
        assert main_file.exists()

        content = main_file.read_text()
        assert f'"""Main module for {tmp_path.name}."""' in content
        assert "def say_hello(name: str) -> str:" in content

    def test_init_with_custom_names(self, tmp_path):
        """Test init with custom project and package names."""
        init(tmp_path, project_name="My Project", package_name="my_pkg")

        # Check pyproject.toml
        pyproject_file = tmp_path / "pyproject.toml"
        content = pyproject_file.read_text()
        assert 'name = "My Project"' in content
        assert 'packages = ["src/my_pkg"]' in content

        # Check directory structure
        assert (tmp_path / "src" / "my_pkg").exists()
        assert (tmp_path / "src" / "my_pkg" / "__init__.py").exists()
        assert (tmp_path / "src" / "my_pkg" / "main.py").exists()

        # Check __init__.py docstring
        init_file = tmp_path / "src" / "my_pkg" / "__init__.py"
        assert '"""My Project."""' in init_file.read_text()

    def test_init_with_dev_dependencies(self, tmp_path):
        """Test init with dev dependencies enabled."""
        init(tmp_path, with_dev_dependencies=True)

        pyproject_file = tmp_path / "pyproject.toml"
        content = pyproject_file.read_text()

        assert "[project.optional-dependencies]" in content
        assert "dev = [" in content
        assert '"pytest==9.0.2",' in content
        assert "[tool.deptry]" in content

    def test_init_generates_valid_toml(self, tmp_path):
        """Test that the generated pyproject.toml is valid TOML."""
        import tomllib

        init(tmp_path)

        pyproject_file = tmp_path / "pyproject.toml"
        assert pyproject_file.exists()

        with open(pyproject_file, "rb") as f:
            data = tomllib.load(f)

        assert "project" in data
        assert "name" in data["project"]
        assert data["project"]["name"] == tmp_path.name

    def test_init_with_project_name_starting_with_digit(self, tmp_path):
        """Test init with project name starting with a digit (auto-normalized package name)."""
        # Don't pass package_name, so it will be auto-normalized from project_name
        init(tmp_path, project_name="123project")

        # Check that package name was normalized to _123project
        assert (tmp_path / "src" / "_123project").exists()
        assert (tmp_path / "src" / "_123project" / "__init__.py").exists()

        # Check pyproject.toml references the normalized package
        pyproject_file = tmp_path / "pyproject.toml"
        content = pyproject_file.read_text()
        assert 'packages = ["src/_123project"]' in content

    def test_init_with_project_name_as_keyword(self, tmp_path):
        """Test init with project name that is a Python keyword (auto-normalized package name)."""
        # Don't pass package_name, so it will be auto-normalized from project_name
        init(tmp_path, project_name="class")

        # Check that package name was normalized to class_
        assert (tmp_path / "src" / "class_").exists()
        assert (tmp_path / "src" / "class_" / "__init__.py").exists()

        # Check pyproject.toml references the normalized package
        pyproject_file = tmp_path / "pyproject.toml"
        content = pyproject_file.read_text()
        assert 'packages = ["src/class_"]' in content
