"""Tests for the init command and CLI wiring.

This module verifies that `init` creates/validates `.rhiza/template.yml` and
that the Typer CLI entry `rhiza init` works as expected.
"""

from pathlib import Path

import pytest
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

    def test_init_with_github_explicit(self, tmp_path):
        """Test init with explicitly specified GitHub target platform."""
        init(tmp_path, git_host="github")

        # Verify template.yml was created
        template_file = tmp_path / ".rhiza" / "template.yml"
        assert template_file.exists()

        with open(template_file) as f:
            config = yaml.safe_load(f)

        # template-host should not appear (defaults to github for template repo)
        assert "template-host" not in config
        # Should include .github for GitHub target
        assert ".github" in config["include"]
        assert ".gitlab-ci.yml" not in config["include"]

    def test_init_with_gitlab_explicit(self, tmp_path):
        """Test init with explicitly specified GitLab target platform."""
        init(tmp_path, git_host="gitlab")

        # Verify template.yml was created
        template_file = tmp_path / ".rhiza" / "template.yml"
        assert template_file.exists()

        with open(template_file) as f:
            config = yaml.safe_load(f)

        # template-host should not appear because template repo is still on GitHub
        # We only change the include list based on target platform
        assert "template-host" not in config
        # Should include .gitlab-ci.yml for GitLab target
        assert ".gitlab-ci.yml" in config["include"]
        # Should NOT include .github for GitLab target
        assert ".github" not in config["include"]

    def test_init_with_invalid_git_host(self, tmp_path):
        """Test init with invalid git-host raises error."""
        with pytest.raises(ValueError, match="Invalid git-host"):
            init(tmp_path, git_host="bitbucket")

    def test_init_with_git_host_case_insensitive(self, tmp_path):
        """Test init with git-host is case insensitive."""
        init(tmp_path, git_host="GitLab")

        # Verify template.yml was created
        template_file = tmp_path / ".rhiza" / "template.yml"
        assert template_file.exists()

        with open(template_file) as f:
            config = yaml.safe_load(f)

        # Should include .gitlab-ci.yml for GitLab target
        assert ".gitlab-ci.yml" in config["include"]
        # Should NOT include .github for GitLab target
        assert ".github" not in config["include"]

    def test_init_skips_src_folder_creation_when_exists(self, tmp_path):
        """Test that init skips creating src folder when it already exists."""
        # Create existing src folder structure
        src_folder = tmp_path / "src" / "mypackage"
        src_folder.mkdir(parents=True)
        init_file = src_folder / "__init__.py"
        init_file.write_text("# Existing package")

        # Run init with explicit git_host to avoid prompting
        init(tmp_path, git_host="github")

        # Verify existing src structure is preserved
        assert init_file.exists()
        assert init_file.read_text() == "# Existing package"

        # Verify template.yml was still created
        template_file = tmp_path / ".rhiza" / "template.yml"
        assert template_file.exists()

    def test_init_skips_pyproject_creation_when_exists(self, tmp_path):
        """Test that init skips creating pyproject.toml when it already exists."""
        # Create existing pyproject.toml
        pyproject_file = tmp_path / "pyproject.toml"
        existing_content = "[project]\nname = 'existing-project'\n"
        pyproject_file.write_text(existing_content)

        # Run init with explicit git_host to avoid prompting
        init(tmp_path, git_host="github")

        # Verify existing pyproject.toml is preserved
        assert pyproject_file.exists()
        assert pyproject_file.read_text() == existing_content

        # Verify template.yml was still created
        template_file = tmp_path / ".rhiza" / "template.yml"
        assert template_file.exists()

    def test_init_skips_readme_creation_when_exists(self, tmp_path):
        """Test that init skips creating README.md when it already exists."""
        # Create existing README.md
        readme_file = tmp_path / "README.md"
        existing_content = "# My Existing Project\n\nExisting content.\n"
        readme_file.write_text(existing_content)

        # Run init with explicit git_host to avoid prompting
        init(tmp_path, git_host="github")

        # Verify existing README.md is preserved
        assert readme_file.exists()
        assert readme_file.read_text() == existing_content

        # Verify template.yml was still created
        template_file = tmp_path / ".rhiza" / "template.yml"
        assert template_file.exists()

    def test_prompt_git_host_validation_loop(self, monkeypatch):
        """Test that _prompt_git_host validates input in a loop."""
        from unittest.mock import MagicMock

        from rhiza.commands.init import _prompt_git_host

        # Mock sys.stdin.isatty to return True (interactive mode)
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)

        # Mock typer.prompt to return invalid input first, then valid input
        prompt_responses = ["bitbucket", "gitlab"]
        prompt_mock = MagicMock(side_effect=prompt_responses)
        monkeypatch.setattr("typer.prompt", prompt_mock)

        # Call the function
        result = _prompt_git_host()

        # Verify it returned the valid input
        assert result == "gitlab"

        # Verify prompt was called twice (once for invalid, once for valid)
        assert prompt_mock.call_count == 2

    def test_init_with_custom_template_repository(self, tmp_path):
        """Test init with custom template repository."""
        init(tmp_path, git_host="github", template_repository="myorg/my-templates")

        # Verify template.yml was created
        template_file = tmp_path / ".rhiza" / "template.yml"
        assert template_file.exists()

        with open(template_file) as f:
            config = yaml.safe_load(f)

        # Should use the custom repository
        assert config["template-repository"] == "myorg/my-templates"
        # Branch should default to main
        assert config["template-branch"] == "main"

    def test_init_with_custom_template_repository_and_branch(self, tmp_path):
        """Test init with custom template repository and branch."""
        init(
            tmp_path,
            git_host="github",
            template_repository="myorg/my-templates",
            template_branch="develop",
        )

        # Verify template.yml was created
        template_file = tmp_path / ".rhiza" / "template.yml"
        assert template_file.exists()

        with open(template_file) as f:
            config = yaml.safe_load(f)

        # Should use the custom repository and branch
        assert config["template-repository"] == "myorg/my-templates"
        assert config["template-branch"] == "develop"

    def test_init_with_custom_template_branch_only(self, tmp_path):
        """Test init with custom template branch but default repository."""
        init(tmp_path, git_host="github", template_branch="v2.0")

        # Verify template.yml was created
        template_file = tmp_path / ".rhiza" / "template.yml"
        assert template_file.exists()

        with open(template_file) as f:
            config = yaml.safe_load(f)

        # Should use default repository but custom branch
        assert config["template-repository"] == "jebel-quant/rhiza"
        assert config["template-branch"] == "v2.0"
