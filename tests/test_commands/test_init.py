"""Tests for the init command and CLI wiring.

This module verifies that `init` creates/validates `.rhiza/template.yml` and
that the Typer CLI entry `rhiza init` works as expected.
"""

import subprocess  # nosec B404
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml
from typer.testing import CliRunner

from rhiza import cli
from rhiza.commands.init import _check_template_repository_reachable, init


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

        assert config["repository"] == "jebel-quant/rhiza"
        assert config["ref"] == "main"
        # Should use templates by default
        assert "templates" in config
        assert "core" in config["templates"]
        assert "tests" in config["templates"]
        assert "github" in config["templates"]

    def test_init_validates_existing_template_yml(self, tmp_path):
        """Test that init validates an existing template.yml."""
        # Create existing template.yml
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump(
                {
                    "repository": "custom/repo",
                    "ref": "dev",
                    "include": [".github", "Makefile"],
                },
                f,
            )

        # Run init - should validate without error
        init(tmp_path)

        # Verify original content is preserved
        with open(template_file) as f:
            config = yaml.safe_load(f)

        assert config["repository"] == "custom/repo"
        assert config["ref"] == "dev"

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

        assert config["repository"] == "jebel-quant/rhiza"

        # Old file should still exist (not moved)
        assert old_template_file.exists()

    def test_init_cli_command(self):
        """Test the CLI init command via Typer runner."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            subprocess.run(["git", "init"], capture_output=True)  # nosec B603 B607
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
        """Test init creates a pyproject.toml with a [dependency-groups] dev block."""
        init(tmp_path, with_dev_dependencies=True)

        pyproject_file = tmp_path / "pyproject.toml"
        content = pyproject_file.read_text()

        assert "[dependency-groups]" in content
        assert "dev = [" in content
        assert "marimo" in content
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

        # Should use templates for GitHub target
        assert "templates" in config
        assert "github" in config["templates"]
        assert "gitlab" not in config["templates"]

    def test_init_with_gitlab_explicit(self, tmp_path):
        """Test init with explicitly specified GitLab target platform."""
        init(tmp_path, git_host="gitlab")

        # Verify template.yml was created
        template_file = tmp_path / ".rhiza" / "template.yml"
        assert template_file.exists()

        with open(template_file) as f:
            config = yaml.safe_load(f)

        # Should use templates for GitLab target
        assert "templates" in config
        assert "gitlab" in config["templates"]
        assert "github" not in config["templates"]

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

        # Should use gitlab template for GitLab target
        assert "templates" in config
        assert "gitlab" in config["templates"]
        # Should NOT include github template for GitLab target
        assert "github" not in config["templates"]

    def test_init_with_go_language(self, tmp_path):
        """Test that init with go language creates Go-specific structure."""
        init(tmp_path, git_host="github", language="go")

        # Verify template.yml was created with go language
        template_file = tmp_path / ".rhiza" / "template.yml"
        assert template_file.exists()

        with open(template_file) as f:
            config = yaml.safe_load(f)

        assert config["repository"] == "jebel-quant/rhiza-go"
        assert config["language"] == "go"

        # Verify Go-specific structure was NOT created (user should run go mod init)
        assert not (tmp_path / "go.mod").exists()
        assert not (tmp_path / "src").exists()
        assert not (tmp_path / "pyproject.toml").exists()

        # Only README should be created
        assert (tmp_path / "README.md").exists()

    def test_init_with_python_language_explicit(self, tmp_path):
        """Test that init with explicit python language creates Python structure."""
        init(tmp_path, git_host="github", language="python")

        # Verify template.yml was created WITHOUT language field (it's default)
        template_file = tmp_path / ".rhiza" / "template.yml"
        with open(template_file) as f:
            config = yaml.safe_load(f)

        assert config["repository"] == "jebel-quant/rhiza"
        assert config["language"] == "python"

        # Verify Python-specific structure
        assert (tmp_path / "pyproject.toml").exists()
        assert (tmp_path / "src" / tmp_path.name).is_dir()
        assert (tmp_path / "README.md").exists()

    def test_init_defaults_to_python_language(self, tmp_path):
        """Test that init defaults to python when no language specified."""
        init(tmp_path, git_host="github")

        # Verify Python structure was created
        assert (tmp_path / "pyproject.toml").exists()
        assert (tmp_path / "src").is_dir()

    @patch("rhiza.commands.init._check_template_repository_reachable", return_value=True)
    def test_init_go_with_custom_template_repository(self, mock_check, tmp_path):
        """Test that custom template repository works with Go language."""
        init(
            tmp_path,
            git_host="github",
            language="go",
            template_repository="custom/go-templates",
        )

        template_file = tmp_path / ".rhiza" / "template.yml"
        with open(template_file) as f:
            config = yaml.safe_load(f)

        # Custom repository should override default
        assert config["repository"] == "custom/go-templates"
        assert config["language"] == "go"

    def test_init_unknown_language(self, tmp_path):
        """Test that init handles unknown languages gracefully."""
        init(tmp_path, git_host="github", language="rust")

        # Should create minimal structure
        assert (tmp_path / ".rhiza" / "template.yml").exists()
        assert (tmp_path / "README.md").exists()

        # Should not create language-specific files
        assert not (tmp_path / "pyproject.toml").exists()
        assert not (tmp_path / "go.mod").exists()

        # Verify template.yml
        template_file = tmp_path / ".rhiza" / "template.yml"
        with open(template_file) as f:
            config = yaml.safe_load(f)

        assert config["language"] == "rust"
        # Should use default Python repository since no mapping exists
        assert config["repository"] == "jebel-quant/rhiza"

    def test_init_go_language_with_gitlab(self, tmp_path):
        """Test Go init with GitLab hosting."""
        init(tmp_path, git_host="gitlab", language="go")

        template_file = tmp_path / ".rhiza" / "template.yml"
        with open(template_file) as f:
            config = yaml.safe_load(f)

        assert config["repository"] == "jebel-quant/rhiza-go"
        assert config["language"] == "go"
        # Should include gitlab in templates
        assert "gitlab" in config["templates"]
        assert "github" not in config["templates"]

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

    @patch("rhiza.commands.init._check_template_repository_reachable", return_value=True)
    def test_init_with_custom_template_repository(self, mock_check, tmp_path):
        """Test init with custom template repository."""
        init(tmp_path, git_host="github", template_repository="myorg/my-templates")

        # Verify template.yml was created
        template_file = tmp_path / ".rhiza" / "template.yml"
        assert template_file.exists()

        with open(template_file) as f:
            config = yaml.safe_load(f)

        # Should use the custom repository
        assert config["repository"] == "myorg/my-templates"
        # Branch should default to main
        assert config["ref"] == "main"

    @patch("rhiza.commands.init._check_template_repository_reachable", return_value=True)
    def test_init_with_custom_template_repository_and_branch(self, mock_check, tmp_path):
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
        assert config["repository"] == "myorg/my-templates"
        assert config["ref"] == "develop"

    def test_init_with_custom_template_branch_only(self, tmp_path):
        """Test init with custom template branch but default repository."""
        init(tmp_path, git_host="github", template_branch="v2.0")

        # Verify template.yml was created
        template_file = tmp_path / ".rhiza" / "template.yml"
        assert template_file.exists()

        with open(template_file) as f:
            config = yaml.safe_load(f)

        # Should use default repository but custom branch
        assert config["repository"] == "jebel-quant/rhiza"
        assert config["ref"] == "v2.0"

    def test_create_template_file_with_gitlab_path_based(self, tmp_path):
        """Test that path-based config with gitlab creates .gitlab paths."""
        from rhiza.commands.init import _create_template_file

        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)

        _create_template_file(tmp_path, git_host="gitlab")

        template_file = tmp_path / ".rhiza" / "template.yml"
        assert template_file.exists()

        with open(template_file) as f:
            config = yaml.safe_load(f)

        assert "templates" in config

    def test_create_template_file_with_github_path_based(self, tmp_path):
        """Test that path-based config with github creates .github paths."""
        from rhiza.commands.init import _create_template_file

        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)

        _create_template_file(tmp_path, git_host="github")

        template_file = tmp_path / ".rhiza" / "template.yml"
        assert template_file.exists()

        with open(template_file) as f:
            config = yaml.safe_load(f)

        assert "templates" in config


class TestCheckTemplateRepositoryReachable:
    """Tests for the _check_template_repository_reachable function."""

    @patch("rhiza.commands.init.subprocess.run")
    def test_reachable_repository_returns_true(self, mock_run):
        """Test that a reachable repository returns True."""
        mock_run.return_value = MagicMock(returncode=0)
        result = _check_template_repository_reachable("myorg/my-templates", "github")
        assert result is True
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "https://github.com/myorg/my-templates" in args

    @patch("rhiza.commands.init.subprocess.run")
    def test_unreachable_repository_returns_false(self, mock_run):
        """Test that an unreachable repository returns False."""
        mock_run.return_value = MagicMock(returncode=128)
        result = _check_template_repository_reachable("typo/nonexistent", "github")
        assert result is False

    @patch("rhiza.commands.init.subprocess.run")
    def test_gitlab_host_uses_gitlab_url(self, mock_run):
        """Test that gitlab host uses gitlab.com URL."""
        mock_run.return_value = MagicMock(returncode=0)
        _check_template_repository_reachable("myorg/my-templates", "gitlab")
        args = mock_run.call_args[0][0]
        assert "https://gitlab.com/myorg/my-templates" in args

    @patch("rhiza.commands.init.subprocess.run")
    def test_timeout_returns_false(self, mock_run):
        """Test that a timeout returns False."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="git", timeout=30)
        result = _check_template_repository_reachable("myorg/my-templates", "github")
        assert result is False

    @patch("rhiza.commands.init.GitContext")
    def test_git_not_found_returns_true(self, mock_git_ctx_cls):
        """Test that missing git executable returns True (don't block init)."""
        mock_git_ctx_cls.default.side_effect = RuntimeError("git not found")
        result = _check_template_repository_reachable("myorg/my-templates", "github")
        assert result is True

    @patch("rhiza.commands.init._check_template_repository_reachable", return_value=False)
    def test_init_returns_false_when_repository_unreachable(self, mock_check, tmp_path):
        """Test that init returns False when template repository is unreachable."""
        result = init(tmp_path, git_host="github", template_repository="typo/nonexistent")
        assert result is False
        # Template file should not be created
        template_file = tmp_path / ".rhiza" / "template.yml"
        assert not template_file.exists()

    @patch("rhiza.commands.init._check_template_repository_reachable", return_value=False)
    def test_cli_init_exits_with_error_when_repository_unreachable(self, mock_check, tmp_path):
        """Test that CLI exits with non-zero code when template repository is unreachable."""
        runner = CliRunner()
        result = runner.invoke(
            cli.app, ["init", str(tmp_path), "--git-host", "github", "--template-repository", "typo/nonexistent"]
        )
        assert result.exit_code != 0


class TestPromptTemplateRepository:
    """Tests for the _prompt_template_repository function."""

    def test_returns_none_when_not_tty(self, monkeypatch):
        """Return None immediately in non-interactive (non-TTY) mode."""
        from rhiza.commands.init import _prompt_template_repository

        monkeypatch.setattr("sys.stdin.isatty", lambda: False)
        assert _prompt_template_repository() is None

    def test_returns_none_on_network_error(self, monkeypatch):
        """Return None gracefully when the GitHub API is unreachable."""
        import urllib.error

        from rhiza.commands.init import _prompt_template_repository

        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        with patch(
            "rhiza.commands.init._fetch_repos",
            side_effect=urllib.error.URLError("network error"),
        ):
            assert _prompt_template_repository() is None

    def test_returns_none_when_no_repos(self, monkeypatch):
        """Return None when the API returns an empty list."""
        from rhiza.commands.init import _prompt_template_repository

        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        with patch("rhiza.commands.init._fetch_repos", return_value=[]):
            assert _prompt_template_repository() is None

    def test_returns_none_on_empty_input(self, monkeypatch):
        """Return None when the user presses Enter without entering a number."""
        from rhiza.commands.init import _prompt_template_repository
        from rhiza.commands.list_repos import _RepoInfo

        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        monkeypatch.setattr("typer.prompt", lambda *a, **kw: "")
        with patch(
            "rhiza.commands.init._fetch_repos",
            return_value=[_RepoInfo("org/repo", "desc", "2026-01-01")],
        ):
            assert _prompt_template_repository() is None

    def test_returns_selected_repo_on_valid_number(self, monkeypatch):
        """Return the full_name of the repo at the selected index."""
        from rhiza.commands.init import _prompt_template_repository
        from rhiza.commands.list_repos import _RepoInfo

        repos = [
            _RepoInfo("org/repo-a", "desc A", "2026-01-01"),
            _RepoInfo("org/repo-b", "desc B", "2026-02-01"),
        ]
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        monkeypatch.setattr("typer.prompt", lambda *a, **kw: "2")
        with patch("rhiza.commands.init._fetch_repos", return_value=repos):
            assert _prompt_template_repository() == "org/repo-b"

    def test_returns_none_on_out_of_range_number(self, monkeypatch):
        """Return None when the number is out of range."""
        from rhiza.commands.init import _prompt_template_repository
        from rhiza.commands.list_repos import _RepoInfo

        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        monkeypatch.setattr("typer.prompt", lambda *a, **kw: "99")
        with patch(
            "rhiza.commands.init._fetch_repos",
            return_value=[_RepoInfo("org/repo", "desc", "2026-01-01")],
        ):
            assert _prompt_template_repository() is None

    def test_returns_none_on_non_numeric_input(self, monkeypatch):
        """Return None when the user enters a non-numeric value."""
        from rhiza.commands.init import _prompt_template_repository
        from rhiza.commands.list_repos import _RepoInfo

        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        monkeypatch.setattr("typer.prompt", lambda *a, **kw: "abc")
        with patch(
            "rhiza.commands.init._fetch_repos",
            return_value=[_RepoInfo("org/repo", "desc", "2026-01-01")],
        ):
            assert _prompt_template_repository() is None

    def test_init_calls_prompt_when_no_template_repo_specified(self, tmp_path):
        """init() should call _prompt_template_repository() when no repo is provided and no yml exists."""
        prompt_mock = MagicMock(return_value=None)
        with patch("rhiza.commands.init._prompt_template_repository", prompt_mock):
            init(tmp_path, git_host="github")
        prompt_mock.assert_called_once()

    def test_init_skips_prompt_when_template_repo_specified(self, tmp_path):
        """init() should skip the prompt when --template-repository is provided."""
        prompt_mock = MagicMock(return_value=None)
        with (
            patch("rhiza.commands.init._prompt_template_repository", prompt_mock),
            patch("rhiza.commands.init._check_template_repository_reachable", return_value=True),
        ):
            init(tmp_path, git_host="github", template_repository="org/custom")
        prompt_mock.assert_not_called()

    def test_init_skips_prompt_when_template_yml_exists(self, tmp_path):
        """init() should skip the prompt when .rhiza/template.yml already exists."""
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        template_file = rhiza_dir / "template.yml"
        template_file.write_text("repository: org/existing\nref: main\ninclude:\n  - .github\n")
        prompt_mock = MagicMock(return_value=None)
        with patch("rhiza.commands.init._prompt_template_repository", prompt_mock):
            init(tmp_path, git_host="github")
        prompt_mock.assert_not_called()

    def test_init_uses_selected_repo_from_prompt(self, tmp_path):
        """init() should use the repository returned by _prompt_template_repository()."""
        with (
            patch("rhiza.commands.init._prompt_template_repository", return_value="org/selected-repo"),
            patch("rhiza.commands.init._check_template_repository_reachable", return_value=True),
        ):
            init(tmp_path, git_host="github")

        template_file = tmp_path / ".rhiza" / "template.yml"
        assert template_file.exists()
        with open(template_file) as f:
            config = yaml.safe_load(f)
        assert config["repository"] == "org/selected-repo"


class TestInitCustomTemplatePath:
    """Tests for the --path-to-template option on init."""

    def test_init_creates_template_in_custom_directory(self, tmp_path):
        """init() writes template.yml to the custom directory when template_file is given."""
        (tmp_path / ".git").mkdir()
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
        custom_dir = tmp_path / "my-rhiza"
        custom_dir.mkdir()
        custom_file = custom_dir / "template.yml"

        result = init(tmp_path, git_host="github", template_file=custom_file)
        assert result is True
        assert custom_file.exists()
        # Default .rhiza/template.yml must NOT have been created.
        assert not (tmp_path / ".rhiza" / "template.yml").exists()

    def test_init_creates_parent_directory_for_custom_file(self, tmp_path):
        """init() creates parent directories for the custom template_file path."""
        (tmp_path / ".git").mkdir()
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
        custom_file = tmp_path / "deep" / "nested" / "template.yml"

        result = init(tmp_path, git_host="github", template_file=custom_file)
        assert result is True
        assert custom_file.exists()

    def test_init_skips_prompt_when_custom_template_yml_exists(self, tmp_path):
        """init() skips the interactive prompt when the custom template file already exists."""
        custom_dir = tmp_path / "my-rhiza"
        custom_dir.mkdir()
        custom_file = custom_dir / "template.yml"
        custom_file.write_text("repository: org/existing\nref: main\ninclude:\n  - .github\n")

        prompt_mock = MagicMock(return_value=None)
        with patch("rhiza.commands.init._prompt_template_repository", prompt_mock):
            init(tmp_path, git_host="github", template_file=custom_file)
        prompt_mock.assert_not_called()

    def test_cli_path_to_template_creates_template_in_custom_directory(self, tmp_path):
        """CLI --path-to-template writes template.yml to the given directory."""
        import subprocess as sp  # nosec B404

        sp.run(["git", "init", str(tmp_path)], capture_output=True)  # nosec B603 B607
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
        custom_dir = tmp_path / "custom-rhiza"
        custom_dir.mkdir()

        runner = CliRunner()
        result = runner.invoke(
            cli.app,
            ["init", str(tmp_path), "--git-host", "github", "--path-to-template", str(custom_dir)],
        )
        assert result.exit_code == 0
        assert (custom_dir / "template.yml").exists()
        assert not (tmp_path / ".rhiza" / "template.yml").exists()


# ---------------------------------------------------------------------------
# _fetch_profiles_from_upstream
# ---------------------------------------------------------------------------


class TestFetchProfilesFromUpstream:
    """Tests for _fetch_profiles_from_upstream().

    All tests mock the git clone so they run offline and never touch the network.
    """

    def _make_bundles_file(self, tmp_path, profiles: dict | None = None) -> Path:
        """Write a minimal template-bundles.yml to tmp_path and return its path."""
        import yaml as _yaml

        content: dict = {"bundles": {"core": {"description": "Core", "files": ["Makefile"]}}}
        if profiles is not None:
            content["profiles"] = profiles
        bundles_file = tmp_path / ".rhiza" / "template-bundles.yml"
        bundles_file.parent.mkdir(parents=True, exist_ok=True)
        bundles_file.write_text(_yaml.dump(content))
        return bundles_file

    def test_returns_profile_map_when_fetch_succeeds(self, tmp_path):
        """Returns a name→description dict when the upstream file has profiles."""
        from rhiza.commands.init import _fetch_profiles_from_upstream

        bundles_root = tmp_path / "upstream"
        bundles_root.mkdir()
        self._make_bundles_file(
            bundles_root,
            profiles={
                "local": {"description": "Local-first", "bundles": ["core"]},
                "github-project": {"description": "GitHub project", "bundles": ["core"]},
            },
        )

        def fake_clone(repo_url, dest, branch, paths):
            # Copy the bundles file into dest so the real parsing code finds it
            import shutil

            src = bundles_root / ".rhiza" / "template-bundles.yml"
            target = dest / ".rhiza" / "template-bundles.yml"
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(src, target)

        with patch("rhiza.commands.init.GitContext.default") as mock_ctx:
            mock_ctx.return_value.clone_repository.side_effect = fake_clone
            result = _fetch_profiles_from_upstream("owner/repo", branch="main")

        assert result is not None
        profiles_map, rb = result
        assert "local" in profiles_map
        assert "github-project" in profiles_map
        assert "Local-first" in profiles_map["local"]
        assert rb is not None
        assert "core" in rb.bundles

    def test_returns_none_when_clone_raises(self):
        """Returns None (does not raise) when the git clone fails."""
        from rhiza.commands.init import _fetch_profiles_from_upstream

        with patch("rhiza.commands.init.GitContext.default") as mock_ctx:
            mock_ctx.return_value.clone_repository.side_effect = RuntimeError("network down")
            result = _fetch_profiles_from_upstream("owner/repo")

        assert result is None

    def test_returns_none_when_bundles_file_absent(self, tmp_path):
        """Returns None when the cloned directory has no template-bundles.yml."""
        from rhiza.commands.init import _fetch_profiles_from_upstream

        def fake_clone(repo_url, dest, branch, paths):
            pass  # Don't write anything — file will be absent

        with patch("rhiza.commands.init.GitContext.default") as mock_ctx:
            mock_ctx.return_value.clone_repository.side_effect = fake_clone
            result = _fetch_profiles_from_upstream("owner/repo")

        assert result is None

    def test_returns_none_when_no_profiles_section(self, tmp_path):
        """Returns None when the bundles file exists but has no profiles: key."""
        from rhiza.commands.init import _fetch_profiles_from_upstream

        bundles_root = tmp_path / "upstream"
        bundles_root.mkdir()
        self._make_bundles_file(bundles_root, profiles=None)  # no profiles key

        def fake_clone(repo_url, dest, branch, paths):
            import shutil

            src = bundles_root / ".rhiza" / "template-bundles.yml"
            target = dest / ".rhiza" / "template-bundles.yml"
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(src, target)

        with patch("rhiza.commands.init.GitContext.default") as mock_ctx:
            mock_ctx.return_value.clone_repository.side_effect = fake_clone
            result = _fetch_profiles_from_upstream("owner/repo")

        assert result is None


# ---------------------------------------------------------------------------
# _prompt_profile
# ---------------------------------------------------------------------------


class TestPromptProfile:
    """Tests for _prompt_profile().

    Verifies the interactive menu, non-interactive auto-select, and advanced mode.
    """

    _PROFILES = {
        "local": "Local-first setup",
        "github-project": "Standard GitHub project",
    }

    def test_non_interactive_picks_github_project_for_github(self, monkeypatch):
        """In non-interactive mode, github-project is selected automatically for GitHub."""
        from rhiza.commands.init import _prompt_profile
        from rhiza.models import GitHost

        monkeypatch.setattr("sys.stdin.isatty", lambda: False)
        profiles, templates = _prompt_profile(self._PROFILES, git_host=GitHost.GITHUB)

        assert profiles == ["github-project"]
        assert templates == []

    def test_non_interactive_picks_first_profile_when_default_absent(self, monkeypatch):
        """In non-interactive mode, picks the first profile when the default name is not present."""
        from rhiza.commands.init import _prompt_profile
        from rhiza.models import GitHost

        monkeypatch.setattr("sys.stdin.isatty", lambda: False)
        profiles_map = {"local": "Local-first setup"}  # no github-project
        profiles, templates = _prompt_profile(profiles_map, git_host=GitHost.GITHUB)

        assert profiles == ["local"]
        assert templates == []

    def test_interactive_numeric_selection_returns_profile(self, monkeypatch):
        """Selecting the first profile returns it."""
        from unittest.mock import MagicMock

        from rhiza.commands.init import _prompt_profile

        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        mock_q = MagicMock()
        mock_q.ask.return_value = "local"
        monkeypatch.setattr("questionary.select", lambda *a, **kw: mock_q)

        profiles, templates = _prompt_profile(self._PROFILES)

        assert profiles == ["local"]
        assert templates == []

    def test_interactive_selects_second_profile(self, monkeypatch):
        """Selecting the second profile returns it."""
        from unittest.mock import MagicMock

        from rhiza.commands.init import _prompt_profile

        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        mock_q = MagicMock()
        mock_q.ask.return_value = "github-project"
        monkeypatch.setattr("questionary.select", lambda *a, **kw: mock_q)

        profiles, templates = _prompt_profile(self._PROFILES)

        assert profiles == ["github-project"]
        assert templates == []

    def test_interactive_advanced_mode_returns_templates(self, monkeypatch):
        """Selecting advanced falls through to the bundle checkbox."""
        from unittest.mock import MagicMock

        from rhiza.commands.init import _prompt_profile
        from rhiza.models import GitHost

        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        # select returns __advanced__, checkbox returns nothing (triggers default fallback)
        mock_select = MagicMock()
        mock_select.ask.return_value = "__advanced__"
        monkeypatch.setattr("questionary.select", lambda *a, **kw: mock_select)
        mock_checkbox = MagicMock()
        mock_checkbox.ask.return_value = None  # cancelled → defaults
        monkeypatch.setattr("questionary.checkbox", lambda *a, **kw: mock_checkbox)

        profiles, templates = _prompt_profile(self._PROFILES, git_host=GitHost.GITHUB)

        assert profiles == []
        assert len(templates) > 0  # falls back to default github templates

    def test_interactive_advanced_mode_with_bundles_returns_selection(self, monkeypatch):
        """Advanced mode with available_bundles shows a checkbox and returns chosen bundles."""
        from unittest.mock import MagicMock

        from rhiza.commands.init import _prompt_profile
        from rhiza.models.bundle import RhizaBundles

        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        mock_select = MagicMock()
        mock_select.ask.return_value = "__advanced__"
        monkeypatch.setattr("questionary.select", lambda *a, **kw: mock_select)
        mock_checkbox = MagicMock()
        mock_checkbox.ask.return_value = ["core", "tests"]
        monkeypatch.setattr("questionary.checkbox", lambda *a, **kw: mock_checkbox)

        rb = RhizaBundles.from_config({"bundles": {"core": {"description": "Core"}, "tests": {"description": "Tests"}}})
        profiles, templates = _prompt_profile(self._PROFILES, available_bundles=rb)

        assert profiles == []
        assert templates == ["core", "tests"]

    def test_interactive_cancelled_falls_back_to_default(self, monkeypatch):
        """When questionary returns None (Ctrl-C/Escape), the default profile is used."""
        from unittest.mock import MagicMock

        from rhiza.commands.init import _prompt_profile
        from rhiza.models import GitHost

        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        mock_q = MagicMock()
        mock_q.ask.return_value = None  # cancelled
        monkeypatch.setattr("questionary.select", lambda *a, **kw: mock_q)

        profiles, templates = _prompt_profile(self._PROFILES, git_host=GitHost.GITHUB)

        assert profiles == ["github-project"]
        assert templates == []


# ---------------------------------------------------------------------------
# _create_template_file — profile integration
# ---------------------------------------------------------------------------


class TestCreateTemplateFileProfileIntegration:
    """Tests that _create_template_file uses profiles when available and falls back correctly."""

    def test_profiles_written_to_template_yml_when_fetch_succeeds(self, tmp_path, monkeypatch):
        """When upstream profiles are available and user selects one, template.yml gets profiles:."""
        from rhiza.commands.init import _create_template_file
        from rhiza.models import GitHost
        from rhiza.models.bundle import RhizaBundles

        monkeypatch.setattr("sys.stdin.isatty", lambda: False)  # auto-select
        rb = RhizaBundles.from_config({"bundles": {"core": {"description": "Core"}}})
        with patch(
            "rhiza.commands.init._fetch_profiles_from_upstream",
            return_value=({"local": "Local-first", "github-project": "GitHub project"}, rb),
        ):
            _create_template_file(tmp_path, GitHost.GITHUB, template_repository="owner/repo")

        config = yaml.safe_load((tmp_path / ".rhiza" / "template.yml").read_text())
        assert "profiles" in config
        assert config["profiles"] == ["github-project"]
        assert not config.get("templates")  # templates should be absent or empty in profile mode

    def test_templates_written_when_fetch_returns_none(self, tmp_path):
        """When _fetch_profiles_from_upstream returns None, template.yml uses templates: fallback."""
        from rhiza.commands.init import _create_template_file
        from rhiza.models import GitHost

        with patch("rhiza.commands.init._fetch_profiles_from_upstream", return_value=None):
            _create_template_file(tmp_path, GitHost.GITHUB, template_repository="owner/repo")

        config = yaml.safe_load((tmp_path / ".rhiza" / "template.yml").read_text())
        assert "templates" in config
        assert "profiles" not in config

    def test_init_calls_fetch_profiles_from_upstream(self, tmp_path):
        """init() calls _fetch_profiles_from_upstream so the profile menu can appear."""
        fetch_mock = MagicMock(return_value=None)
        with (
            patch("rhiza.commands.init._fetch_profiles_from_upstream", fetch_mock),
            patch("rhiza.commands.init._check_template_repository_reachable", return_value=True),
        ):
            init(tmp_path, git_host="github", template_repository="owner/repo")

        assert fetch_mock.call_count >= 1

    def test_init_calls_prompt_profile_when_profiles_available(self, tmp_path, monkeypatch):
        """init() calls _prompt_profile when upstream profiles are found."""
        from rhiza.models.bundle import RhizaBundles

        monkeypatch.setattr("sys.stdin.isatty", lambda: False)
        prompt_mock = MagicMock(return_value=(["local"], []))
        rb = RhizaBundles.from_config({"bundles": {"core": {"description": "Core"}}})
        with (
            patch(
                "rhiza.commands.init._fetch_profiles_from_upstream",
                return_value=({"local": "Local-first"}, rb),
            ),
            patch("rhiza.commands.init._prompt_profile", prompt_mock),
            patch("rhiza.commands.init._check_template_repository_reachable", return_value=True),
        ):
            init(tmp_path, git_host="github", template_repository="owner/repo")

        prompt_mock.assert_called_once()

    def test_init_does_not_call_prompt_profile_when_fetch_fails(self, tmp_path):
        """init() skips _prompt_profile entirely when _fetch_profiles_from_upstream returns None."""
        prompt_mock = MagicMock(return_value=([], []))
        with (
            patch("rhiza.commands.init._fetch_profiles_from_upstream", return_value=None),
            patch("rhiza.commands.init._prompt_profile", prompt_mock),
            patch("rhiza.commands.init._check_template_repository_reachable", return_value=True),
        ):
            init(tmp_path, git_host="github", template_repository="owner/repo")

        prompt_mock.assert_not_called()
