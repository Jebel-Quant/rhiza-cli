"""Tests for the init command and CLI wiring.

This module verifies that `init` creates/validates `.rhiza/template.yml` and
that the Typer CLI entry `rhiza init` works as expected.
"""

import subprocess  # nosec B404
from urllib.parse import urlparse
from unittest.mock import MagicMock, patch

import pytest
import yaml
from typer.testing import CliRunner

from rhiza import cli
from rhiza.commands.init import (
    _check_template_repository_reachable,
    _create_uv_lock,
    _detect_git_host,
    _get_github_username,
    _get_latest_tag,
    init,
)
from rhiza.models import GitHost


class TestInitCommand:
    """Tests for the init command."""

    @patch("rhiza.commands.init._get_latest_tag", return_value="v1.2.3")
    def test_init_creates_default_template_yml(self, mock_tag, git_tmp_path):
        """Test that init creates a default template.yml when it doesn't exist."""
        init(git_tmp_path)

        # Verify template.yml was created
        template_file = git_tmp_path / ".rhiza" / "template.yml"
        assert template_file.exists()

        # Verify it contains expected content
        with open(template_file) as f:
            config = yaml.safe_load(f)

        assert config["repository"] == "jebel-quant/rhiza"
        assert config["ref"] == "v1.2.3"
        assert "profiles" in config
        assert "github-project" in config["profiles"]

    def test_init_validates_existing_template_yml(self, git_tmp_path):
        """Test that init validates an existing template.yml."""
        # Create existing template.yml
        rhiza_dir = git_tmp_path / ".rhiza"
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
        init(git_tmp_path)

        # Verify original content is preserved
        with open(template_file) as f:
            config = yaml.safe_load(f)

        assert config["repository"] == "custom/repo"
        assert config["ref"] == "dev"

    def test_init_warns_on_missing_template_repository(self, git_tmp_path):
        """Test that init warns when template-repository is missing."""
        # Create template.yml without template-repository
        rhiza_dir = git_tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump({"template-branch": "main", "include": [".github"]}, f)

        # Run init - should validate but warn
        init(git_tmp_path)
        # If we reach here, the function completed without raising an exception

    def test_init_warns_on_missing_include(self, git_tmp_path):
        """Test that init warns when include field is missing or empty."""
        # Create template.yml without include
        rhiza_dir = git_tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump({"template-repository": "jebel-quant/rhiza", "template-branch": "main"}, f)

        # Run init - should validate but warn
        init(git_tmp_path)

    def test_init_creates_rhiza_directory(self, git_tmp_path):
        """Test that init creates .rhiza directory if it doesn't exist."""
        init(git_tmp_path)

        rhiza_dir = git_tmp_path / ".rhiza"
        assert rhiza_dir.exists()
        assert rhiza_dir.is_dir()

    def test_init_with_old_template_location(self, git_tmp_path):
        """Test that init works when template.yml exists in old location."""
        # Create old location template.yml
        github_dir = git_tmp_path / ".github"
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
        init(git_tmp_path)

        # Verify new template was created in new location
        new_template_file = git_tmp_path / ".rhiza" / "template.yml"
        assert new_template_file.exists()

        # Verify it has default content (not copied from old location)
        with open(new_template_file) as f:
            config = yaml.safe_load(f)

        assert config["repository"] == "jebel-quant/rhiza"

        # Old file should still exist (not moved)
        assert old_template_file.exists()

    def test_init_cli_command(self, tmp_path, monkeypatch):
        """Test the CLI init command via Typer runner."""
        monkeypatch.chdir(tmp_path)
        subprocess.run(["git", "init"], capture_output=True, cwd=tmp_path)  # nosec B603 B607
        runner = CliRunner()
        result = runner.invoke(cli.app, ["init"])
        assert result.exit_code == 0
        assert (tmp_path / ".rhiza" / "template.yml").exists()

    def test_init_creates_correctly_formatted_files(self, git_tmp_path):
        """Test that init creates files with correct formatting (no indentation)."""
        init(git_tmp_path)

        # Check pyproject.toml content
        pyproject_file = git_tmp_path / "pyproject.toml"
        assert pyproject_file.exists()

        # We expect the default template output
        content = pyproject_file.read_text()
        assert f'name = "{git_tmp_path.name}"' in content
        assert 'packages = ["src/' in content

        # Check main.py content
        main_file = git_tmp_path / "src" / git_tmp_path.name / "main.py"
        assert main_file.exists()

        content = main_file.read_text()
        assert f'"""Main module for {git_tmp_path.name}."""' in content
        assert "def say_hello(name: str) -> str:" in content

    def test_init_with_custom_names(self, git_tmp_path):
        """Test init with custom project and package names."""
        init(git_tmp_path, project_name="My Project", package_name="my_pkg")

        # Check pyproject.toml
        pyproject_file = git_tmp_path / "pyproject.toml"
        content = pyproject_file.read_text()
        assert 'name = "My Project"' in content
        assert 'packages = ["src/my_pkg"]' in content

        # Check directory structure
        assert (git_tmp_path / "src" / "my_pkg").exists()
        assert (git_tmp_path / "src" / "my_pkg" / "__init__.py").exists()
        assert (git_tmp_path / "src" / "my_pkg" / "main.py").exists()

        # Check __init__.py docstring
        init_file = git_tmp_path / "src" / "my_pkg" / "__init__.py"
        assert '"""My Project."""' in init_file.read_text()

    def test_init_always_includes_dependency_groups(self, git_tmp_path):
        """Test init always creates a pyproject.toml with test, lint, and dev dependency-groups."""
        init(git_tmp_path)

        content = (git_tmp_path / "pyproject.toml").read_text()

        assert "[dependency-groups]" in content
        assert "test = [" in content
        assert "lint = [" in content
        assert "dev = []" in content
        assert "pytest" in content
        assert "ruff" in content

    def test_init_creates_makefile(self, git_tmp_path):
        """Test init creates a Makefile with a bootstrap sync target."""
        init(git_tmp_path)

        makefile = git_tmp_path / "Makefile"
        assert makefile.exists()
        content = makefile.read_text()

        assert "uvx rhiza sync ." in content
        assert "-include .rhiza/rhiza.mk" in content

    def test_init_skips_makefile_creation_when_exists(self, git_tmp_path):
        """Test that init does not overwrite an existing Makefile."""
        makefile = git_tmp_path / "Makefile"
        makefile.write_text("# existing\n")

        init(git_tmp_path)

        assert makefile.read_text() == "# existing\n"

    def test_init_creates_mkdocs_yml_github(self, git_tmp_path):
        """Test init creates mkdocs.yml with GitHub URLs."""
        with patch("rhiza.commands.init._get_github_username", return_value="acme"):
            init(git_tmp_path, project_name="my-project", git_host="github")

        mkdocs_file = git_tmp_path / "mkdocs.yml"
        assert mkdocs_file.exists()
        content = mkdocs_file.read_text()

        assert "INHERIT: docs/mkdocs-base.yml" in content
        assert "site_name: my-project" in content
        assert "acme.github.io/my-project" in content
        assert "github.com/acme/my-project" in content
        assert "reports/html-report/report.html" in content
        assert "reports/html-coverage/index.html" in content

    def test_init_creates_mkdocs_yml_gitlab(self, git_tmp_path):
        """Test init creates mkdocs.yml with GitLab URLs."""
        with patch("rhiza.commands.init._get_github_username", return_value="acme"):
            init(git_tmp_path, project_name="my-project", git_host="gitlab")

        content = (git_tmp_path / "mkdocs.yml").read_text()

        assert "acme.gitlab.io/my-project" in content
        assert "gitlab.com/acme/my-project" in content

    def test_init_skips_mkdocs_yml_creation_when_exists(self, git_tmp_path):
        """Test that init does not overwrite an existing mkdocs.yml."""
        mkdocs_file = git_tmp_path / "mkdocs.yml"
        mkdocs_file.write_text("# existing\n")

        init(git_tmp_path)

        assert mkdocs_file.read_text() == "# existing\n"

    def test_init_generates_valid_toml(self, git_tmp_path):
        """Test that the generated pyproject.toml is valid TOML."""
        import tomllib

        init(git_tmp_path)

        pyproject_file = git_tmp_path / "pyproject.toml"
        assert pyproject_file.exists()

        with open(pyproject_file, "rb") as f:
            data = tomllib.load(f)

        assert "project" in data
        assert "name" in data["project"]
        assert data["project"]["name"] == git_tmp_path.name

    def test_init_with_hyphenated_project_name_normalises_test_import(self, git_tmp_path):
        """Test that the generated test file imports from the normalised package name.

        Regression: previously the test template was rendered with the raw project
        name (e.g. 'mini-commodities'), producing an invalid import statement such as
        ``from mini-commodities.main import …``.  The import must use the normalised
        package name (e.g. 'example_project').
        """
        init(git_tmp_path, project_name="example-project", git_host="github")

        test_file = git_tmp_path / "tests" / "test_main.py"
        assert test_file.exists()
        content = test_file.read_text()
        # Import must reference the normalised name, not the raw hyphenated one
        assert "from example_project.main import" in content
        assert "from example-project.main import" not in content

    def test_init_with_project_name_starting_with_digit(self, git_tmp_path):
        """Test init with project name starting with a digit (auto-normalized package name)."""
        # Don't pass package_name, so it will be auto-normalized from project_name
        init(git_tmp_path, project_name="123project")

        # Check that package name was normalized to _123project
        assert (git_tmp_path / "src" / "_123project").exists()
        assert (git_tmp_path / "src" / "_123project" / "__init__.py").exists()

        # Check pyproject.toml references the normalized package
        pyproject_file = git_tmp_path / "pyproject.toml"
        content = pyproject_file.read_text()
        assert 'packages = ["src/_123project"]' in content

    def test_init_with_project_name_as_keyword(self, git_tmp_path):
        """Test init with project name that is a Python keyword (auto-normalized package name)."""
        # Don't pass package_name, so it will be auto-normalized from project_name
        init(git_tmp_path, project_name="class")

        # Check that package name was normalized to class_
        assert (git_tmp_path / "src" / "class_").exists()
        assert (git_tmp_path / "src" / "class_" / "__init__.py").exists()

        # Check pyproject.toml references the normalized package
        pyproject_file = git_tmp_path / "pyproject.toml"
        content = pyproject_file.read_text()
        assert 'packages = ["src/class_"]' in content

    def test_init_with_github_explicit(self, git_tmp_path):
        """Test init with explicitly specified GitHub target platform."""
        init(git_tmp_path, git_host="github")

        # Verify template.yml was created
        template_file = git_tmp_path / ".rhiza" / "template.yml"
        assert template_file.exists()

        with open(template_file) as f:
            config = yaml.safe_load(f)

        assert "profiles" in config
        assert "github-project" in config["profiles"]
        assert "gitlab-project" not in config["profiles"]

    def test_init_with_gitlab_explicit(self, git_tmp_path):
        """Test init with explicitly specified GitLab target platform."""
        init(git_tmp_path, git_host="gitlab")

        # Verify template.yml was created
        template_file = git_tmp_path / ".rhiza" / "template.yml"
        assert template_file.exists()

        with open(template_file) as f:
            config = yaml.safe_load(f)

        assert "profiles" in config
        assert "gitlab-project" in config["profiles"]
        assert "github-project" not in config["profiles"]

    def test_init_with_invalid_git_host(self, git_tmp_path):
        """Test init with invalid git-host raises error."""
        with pytest.raises(ValueError, match="Invalid git-host"):
            init(git_tmp_path, git_host="bitbucket")

    def test_init_with_git_host_case_insensitive(self, git_tmp_path):
        """Test init with git-host is case insensitive."""
        init(git_tmp_path, git_host="GitLab")

        # Verify template.yml was created
        template_file = git_tmp_path / ".rhiza" / "template.yml"
        assert template_file.exists()

        with open(template_file) as f:
            config = yaml.safe_load(f)

        assert "profiles" in config
        assert "gitlab-project" in config["profiles"]
        assert "github-project" not in config["profiles"]

    def test_init_with_go_language(self, git_tmp_path):
        """Test that init with go language creates Go-specific structure."""
        init(git_tmp_path, git_host="github", language="go")

        # Verify template.yml was created with go language
        template_file = git_tmp_path / ".rhiza" / "template.yml"
        assert template_file.exists()

        with open(template_file) as f:
            config = yaml.safe_load(f)

        assert config["repository"] == "jebel-quant/rhiza-go"
        assert config["language"] == "go"

        # Verify Go-specific structure was NOT created (user should run go mod init)
        assert not (git_tmp_path / "go.mod").exists()
        assert not (git_tmp_path / "src").exists()
        assert not (git_tmp_path / "pyproject.toml").exists()

        # Only README should be created
        assert (git_tmp_path / "README.md").exists()

    def test_init_with_python_language_explicit(self, git_tmp_path):
        """Test that init with explicit python language creates Python structure."""
        init(git_tmp_path, git_host="github", language="python")

        # Verify template.yml was created WITHOUT language field (it's default)
        template_file = git_tmp_path / ".rhiza" / "template.yml"
        with open(template_file) as f:
            config = yaml.safe_load(f)

        assert config["repository"] == "jebel-quant/rhiza"
        assert "language" not in config  # python is the default, not emitted

        # Verify Python-specific structure
        assert (git_tmp_path / "pyproject.toml").exists()
        assert (git_tmp_path / "src" / git_tmp_path.name).is_dir()
        assert (git_tmp_path / "README.md").exists()

    def test_init_defaults_to_python_language(self, git_tmp_path):
        """Test that init defaults to python when no language specified."""
        init(git_tmp_path, git_host="github")

        # Verify Python structure was created
        assert (git_tmp_path / "pyproject.toml").exists()
        assert (git_tmp_path / "src").is_dir()

    @patch("rhiza.commands.init._check_template_repository_reachable", return_value=True)
    def test_init_go_with_custom_template_repository(self, mock_check, git_tmp_path):
        """Test that custom template repository works with Go language."""
        init(
            git_tmp_path,
            git_host="github",
            language="go",
            template_repository="custom/go-templates",
        )

        template_file = git_tmp_path / ".rhiza" / "template.yml"
        with open(template_file) as f:
            config = yaml.safe_load(f)

        assert config["repository"] == "custom/go-templates"
        assert config["language"] == "go"

    def test_init_unknown_language(self, git_tmp_path):
        """Test that init handles unknown languages gracefully."""
        init(git_tmp_path, git_host="github", language="rust")

        # Should create minimal structure
        assert (git_tmp_path / ".rhiza" / "template.yml").exists()
        assert (git_tmp_path / "README.md").exists()

        # Should not create language-specific files
        assert not (git_tmp_path / "pyproject.toml").exists()
        assert not (git_tmp_path / "go.mod").exists()

        # Verify template.yml
        template_file = git_tmp_path / ".rhiza" / "template.yml"
        with open(template_file) as f:
            config = yaml.safe_load(f)

        assert config["language"] == "rust"
        assert config["repository"] == "jebel-quant/rhiza"

    def test_init_go_language_with_gitlab(self, git_tmp_path):
        """Test Go init with GitLab hosting."""
        init(git_tmp_path, git_host="gitlab", language="go")

        template_file = git_tmp_path / ".rhiza" / "template.yml"
        with open(template_file) as f:
            config = yaml.safe_load(f)

        assert config["repository"] == "jebel-quant/rhiza-go"
        assert config["language"] == "go"
        assert "profiles" in config
        assert "gitlab-project" in config["profiles"]
        assert "github-project" not in config["profiles"]

    def test_init_skips_src_folder_creation_when_exists(self, git_tmp_path):
        """Test that init skips creating src folder when it already exists."""
        # Create existing src folder structure
        src_folder = git_tmp_path / "src" / "mypackage"
        src_folder.mkdir(parents=True)
        init_file = src_folder / "__init__.py"
        init_file.write_text("# Existing package")

        # Run init with explicit git_host to avoid prompting
        init(git_tmp_path, git_host="github")

        # Verify existing src structure is preserved
        assert init_file.exists()
        assert init_file.read_text() == "# Existing package"

        # Verify template.yml was still created
        template_file = git_tmp_path / ".rhiza" / "template.yml"
        assert template_file.exists()

    def test_init_skips_pyproject_creation_when_exists(self, git_tmp_path):
        """Test that init skips creating pyproject.toml when it already exists."""
        # Create existing pyproject.toml
        pyproject_file = git_tmp_path / "pyproject.toml"
        existing_content = "[project]\nname = 'existing-project'\n"
        pyproject_file.write_text(existing_content)

        # Run init with explicit git_host to avoid prompting
        init(git_tmp_path, git_host="github")

        # Verify existing pyproject.toml is preserved
        assert pyproject_file.exists()
        assert pyproject_file.read_text() == existing_content

        # Verify template.yml was still created
        template_file = git_tmp_path / ".rhiza" / "template.yml"
        assert template_file.exists()

    def test_init_skips_readme_creation_when_exists(self, git_tmp_path):
        """Test that init skips creating README.md when it already exists."""
        # Create existing README.md
        readme_file = git_tmp_path / "README.md"
        existing_content = "# My Existing Project\n\nExisting content.\n"
        readme_file.write_text(existing_content)

        # Run init with explicit git_host to avoid prompting
        init(git_tmp_path, git_host="github")

        # Verify existing README.md is preserved
        assert readme_file.exists()
        assert readme_file.read_text() == existing_content

        # Verify template.yml was still created
        template_file = git_tmp_path / ".rhiza" / "template.yml"
        assert template_file.exists()

    def test_init_fails_when_not_git_repository(self, tmp_path):
        """init() returns False and creates nothing when target is not a git repository."""
        result = init(tmp_path, git_host="github")

        assert result is False
        assert not (tmp_path / ".rhiza").exists()

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
    def test_init_with_custom_template_repository(self, mock_check, git_tmp_path):
        """Test init with custom template repository."""
        init(git_tmp_path, git_host="github", template_repository="myorg/my-templates")

        # Verify template.yml was created
        template_file = git_tmp_path / ".rhiza" / "template.yml"
        assert template_file.exists()

        with open(template_file) as f:
            config = yaml.safe_load(f)

        assert config["repository"] == "myorg/my-templates"
        assert config["ref"] == "main"

    @patch("rhiza.commands.init._check_template_repository_reachable", return_value=True)
    def test_init_with_custom_template_repository_and_branch(self, mock_check, git_tmp_path):
        """Test init with custom template repository and branch."""
        init(
            git_tmp_path,
            git_host="github",
            template_repository="myorg/my-templates",
            template_branch="develop",
        )

        # Verify template.yml was created
        template_file = git_tmp_path / ".rhiza" / "template.yml"
        assert template_file.exists()

        with open(template_file) as f:
            config = yaml.safe_load(f)

        assert config["repository"] == "myorg/my-templates"
        assert config["ref"] == "develop"

    def test_init_with_custom_template_branch_only(self, git_tmp_path):
        """Test init with custom template branch but default repository."""
        init(git_tmp_path, git_host="github", template_branch="v2.0")

        # Verify template.yml was created
        template_file = git_tmp_path / ".rhiza" / "template.yml"
        assert template_file.exists()

        with open(template_file) as f:
            config = yaml.safe_load(f)

        assert config["repository"] == "jebel-quant/rhiza"
        assert config["ref"] == "v2.0"

    def test_create_template_file_with_gitlab_path_based(self, git_tmp_path):
        """Test that path-based config with gitlab creates .gitlab paths."""
        from rhiza.commands.init import _create_template_file

        rhiza_dir = git_tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)

        _create_template_file(git_tmp_path, git_host="gitlab")

        template_file = git_tmp_path / ".rhiza" / "template.yml"
        assert template_file.exists()

        with open(template_file) as f:
            config = yaml.safe_load(f)

        assert "profiles" in config
        assert "gitlab-project" in config["profiles"]

    def test_create_template_file_with_github_path_based(self, git_tmp_path):
        """Test that path-based config with github creates .github paths."""
        from rhiza.commands.init import _create_template_file

        rhiza_dir = git_tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)

        _create_template_file(git_tmp_path, git_host="github")

        template_file = git_tmp_path / ".rhiza" / "template.yml"
        assert template_file.exists()

        with open(template_file) as f:
            config = yaml.safe_load(f)

        assert "profiles" in config
        assert "github-project" in config["profiles"]


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
    def test_init_returns_false_when_repository_unreachable(self, mock_check, git_tmp_path):
        """Test that init returns False when template repository is unreachable."""
        result = init(git_tmp_path, git_host="github", template_repository="typo/nonexistent")
        assert result is False
        # Template file should not be created
        template_file = git_tmp_path / ".rhiza" / "template.yml"
        assert not template_file.exists()

    @patch("rhiza.commands.init._check_template_repository_reachable", return_value=False)
    def test_cli_init_exits_with_error_when_repository_unreachable(self, mock_check, git_tmp_path):
        """Test that CLI exits with non-zero code when template repository is unreachable."""
        runner = CliRunner()
        result = runner.invoke(
            cli.app, ["init", str(git_tmp_path), "--git-host", "github", "--template-repository", "typo/nonexistent"]
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

    def test_enter_selects_first_repo(self, monkeypatch):
        """Pressing Enter (default '1') selects the first repository in the list."""
        from rhiza.commands.init import _prompt_template_repository
        from rhiza.commands.list_repos import _RepoInfo

        repos = [
            _RepoInfo("org/repo-a", "desc A", "2026-01-01"),
            _RepoInfo("org/repo-b", "desc B", "2026-02-01"),
        ]
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        monkeypatch.setattr("typer.prompt", lambda *a, **kw: "1")
        with patch("rhiza.commands.init._fetch_repos", return_value=repos):
            assert _prompt_template_repository() == "org/repo-a"

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

    def test_init_calls_prompt_when_no_template_repo_specified(self, git_tmp_path):
        """init() should call _prompt_template_repository() when no repo is provided and no yml exists."""
        prompt_mock = MagicMock(return_value=None)
        with patch("rhiza.commands.init._prompt_template_repository", prompt_mock):
            init(git_tmp_path, git_host="github")
        prompt_mock.assert_called_once()

    def test_init_skips_prompt_when_template_repo_specified(self, git_tmp_path):
        """init() should skip the prompt when --template-repository is provided."""
        prompt_mock = MagicMock(return_value=None)
        with (
            patch("rhiza.commands.init._prompt_template_repository", prompt_mock),
            patch("rhiza.commands.init._check_template_repository_reachable", return_value=True),
        ):
            init(git_tmp_path, git_host="github", template_repository="org/custom")
        prompt_mock.assert_not_called()

    def test_init_skips_prompt_when_template_yml_exists(self, git_tmp_path):
        """init() should skip the prompt when .rhiza/template.yml already exists."""
        rhiza_dir = git_tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        template_file = rhiza_dir / "template.yml"
        template_file.write_text("repository: org/existing\nref: main\ninclude:\n  - .github\n")
        prompt_mock = MagicMock(return_value=None)
        with patch("rhiza.commands.init._prompt_template_repository", prompt_mock):
            init(git_tmp_path, git_host="github")
        prompt_mock.assert_not_called()

    def test_init_uses_selected_repo_from_prompt(self, git_tmp_path):
        """init() should use the repository returned by _prompt_template_repository()."""
        with (
            patch("rhiza.commands.init._prompt_template_repository", return_value="org/selected-repo"),
            patch("rhiza.commands.init._check_template_repository_reachable", return_value=True),
        ):
            init(git_tmp_path, git_host="github")

        template_file = git_tmp_path / ".rhiza" / "template.yml"
        assert template_file.exists()
        with open(template_file) as f:
            config = yaml.safe_load(f)
        assert config["repository"] == "org/selected-repo"


class TestInitCustomTemplatePath:
    """Tests for the --path-to-template option on init."""

    def test_init_creates_template_in_custom_directory(self, git_tmp_path):
        """init() writes template.yml to the custom directory when template_file is given."""
        (git_tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
        custom_dir = git_tmp_path / "my-rhiza"
        custom_dir.mkdir()
        custom_file = custom_dir / "template.yml"

        result = init(git_tmp_path, git_host="github", template_file=custom_file)
        assert result is True
        assert custom_file.exists()
        # Default .rhiza/template.yml must NOT have been created.
        assert not (git_tmp_path / ".rhiza" / "template.yml").exists()

    def test_init_creates_parent_directory_for_custom_file(self, git_tmp_path):
        """init() creates parent directories for the custom template_file path."""
        (git_tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
        custom_file = git_tmp_path / "deep" / "nested" / "template.yml"

        result = init(git_tmp_path, git_host="github", template_file=custom_file)
        assert result is True
        assert custom_file.exists()

    def test_init_skips_prompt_when_custom_template_yml_exists(self, git_tmp_path):
        """init() skips the interactive prompt when the custom template file already exists."""
        custom_dir = git_tmp_path / "my-rhiza"
        custom_dir.mkdir()
        custom_file = custom_dir / "template.yml"
        custom_file.write_text("repository: org/existing\nref: main\ninclude:\n  - .github\n")

        prompt_mock = MagicMock(return_value=None)
        with patch("rhiza.commands.init._prompt_template_repository", prompt_mock):
            init(git_tmp_path, git_host="github", template_file=custom_file)
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


class TestGetLatestTag:
    """Tests for the _get_latest_tag function."""

    @patch("rhiza.commands.init.subprocess.run")
    def test_returns_latest_version_tag(self, mock_run):
        """Returns the highest version tag from ls-remote output."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=(
                "abc\trefs/tags/v0.9.0\n"
                "def\trefs/tags/v0.10.0\n"
                "ghi\trefs/tags/v0.10.0^{}\n"
                "jkl\trefs/tags/v0.18.4\n"
                "mno\trefs/tags/v0.18.4^{}\n"
            ),
        )
        assert _get_latest_tag("owner/repo") == "v0.18.4"

    @patch("rhiza.commands.init.subprocess.run")
    def test_skips_non_version_tags(self, mock_run):
        """Ignores tags that don't look like version numbers."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="abc\trefs/tags/latest\nabc\trefs/tags/v1.2.3\n",
        )
        assert _get_latest_tag("owner/repo") == "v1.2.3"

    @patch("rhiza.commands.init.subprocess.run")
    def test_returns_none_on_nonzero_exit(self, mock_run):
        """Returns None when git ls-remote fails."""
        mock_run.return_value = MagicMock(returncode=128, stdout="")
        assert _get_latest_tag("owner/repo") is None

    @patch("rhiza.commands.init.subprocess.run")
    def test_returns_none_when_no_tags(self, mock_run):
        """Returns None when the repository has no version tags."""
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        assert _get_latest_tag("owner/repo") is None

    def test_returns_none_on_timeout(self):
        """Returns None on network timeout."""
        with patch("rhiza.commands.init.subprocess.run", side_effect=subprocess.TimeoutExpired("git", 30)):
            assert _get_latest_tag("owner/repo") is None

    @patch("rhiza.commands.init.subprocess.run")
    def test_uses_gitlab_url_for_gitlab_host(self, mock_run):
        """Passes the GitLab URL when git_host is gitlab."""
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        _get_latest_tag("owner/repo", git_host="gitlab")
        args = mock_run.call_args[0][0]
        remote_url = next((arg for arg in args if isinstance(arg, str) and arg.startswith(("http://", "https://"))), "")
        assert urlparse(remote_url).hostname == "gitlab.com"

    def test_init_uses_latest_tag_as_ref(self, git_tmp_path):
        """init() writes the latest tag to ref in template.yml."""
        with patch("rhiza.commands.init._get_latest_tag", return_value="v2.0.0"):
            init(git_tmp_path, git_host="github")
        config = yaml.safe_load((git_tmp_path / ".rhiza" / "template.yml").read_text())
        assert config["ref"] == "v2.0.0"

    def test_init_falls_back_to_main_when_no_tag(self, git_tmp_path):
        """init() falls back to 'main' when no tag can be resolved (autouse stub returns None)."""
        init(git_tmp_path, git_host="github")
        config = yaml.safe_load((git_tmp_path / ".rhiza" / "template.yml").read_text())
        assert config["ref"] == "main"


class TestDetectGitHost:
    """Tests for the _detect_git_host function."""

    @patch("rhiza.commands.init.subprocess.run")
    def test_detects_github_from_https_url(self, mock_run, tmp_path):
        """Returns GITHUB when origin URL contains github.com."""
        mock_run.return_value = MagicMock(returncode=0, stdout="https://github.com/owner/repo.git\n")
        assert _detect_git_host(tmp_path) == GitHost.GITHUB

    @patch("rhiza.commands.init.subprocess.run")
    def test_detects_gitlab_from_https_url(self, mock_run, tmp_path):
        """Returns GITLAB when origin URL contains gitlab.com."""
        mock_run.return_value = MagicMock(returncode=0, stdout="https://gitlab.com/owner/repo.git\n")
        assert _detect_git_host(tmp_path) == GitHost.GITLAB

    @patch("rhiza.commands.init.subprocess.run")
    def test_detects_github_from_ssh_url(self, mock_run, tmp_path):
        """Returns GITHUB for SSH remote URLs."""
        mock_run.return_value = MagicMock(returncode=0, stdout="git@github.com:owner/repo.git\n")
        assert _detect_git_host(tmp_path) == GitHost.GITHUB

    @patch("rhiza.commands.init.subprocess.run")
    def test_detects_gitlab_from_ssh_url(self, mock_run, tmp_path):
        """Returns GITLAB for SSH remote URLs."""
        mock_run.return_value = MagicMock(returncode=0, stdout="git@gitlab.com:owner/repo.git\n")
        assert _detect_git_host(tmp_path) == GitHost.GITLAB

    @patch("rhiza.commands.init.subprocess.run")
    def test_returns_none_for_unknown_host(self, mock_run, tmp_path):
        """Returns None when the remote URL doesn't match a known host."""
        mock_run.return_value = MagicMock(returncode=0, stdout="https://bitbucket.org/owner/repo.git\n")
        assert _detect_git_host(tmp_path) is None

    @patch("rhiza.commands.init.subprocess.run")
    def test_returns_none_when_no_origin(self, mock_run, tmp_path):
        """Returns None when there is no origin remote."""
        mock_run.return_value = MagicMock(returncode=128, stdout="")
        assert _detect_git_host(tmp_path) is None

    @patch("rhiza.commands.init.subprocess.run", side_effect=OSError("git not found"))
    def test_returns_none_on_os_error(self, mock_run, tmp_path):
        """Returns None when git is not available."""
        assert _detect_git_host(tmp_path) is None

    def test_init_uses_detected_host_without_prompt(self, git_tmp_path):
        """init() skips the git-host prompt when detection succeeds."""
        with (
            patch("rhiza.commands.init._detect_git_host", return_value=GitHost.GITLAB),
            patch("rhiza.commands.init._prompt_git_host") as mock_prompt,
        ):
            init(git_tmp_path)
        mock_prompt.assert_not_called()

    def test_init_falls_back_to_prompt_when_detection_fails(self, git_tmp_path):
        """init() prompts when detection returns None."""
        with (
            patch("rhiza.commands.init._detect_git_host", return_value=None),
            patch("rhiza.commands.init._prompt_git_host", return_value=GitHost.GITHUB) as mock_prompt,
        ):
            init(git_tmp_path)
        mock_prompt.assert_called_once()

    def test_init_explicit_host_skips_detection(self, git_tmp_path):
        """Explicit git_host= bypasses detection entirely."""
        with patch("rhiza.commands.init._detect_git_host") as mock_detect:
            init(git_tmp_path, git_host="github")
        mock_detect.assert_not_called()


class TestPyprojectTomlContent:
    """Snapshot test for the full pyproject.toml produced by init."""

    EXPECTED = """\
[build-system]
requires = ["hatchling>=1.29"]
build-backend = "hatchling.build"

[project]
name = "my-project"
version = "0.1.0"
description = "Add your description here"
readme = "README.md"
requires-python = ">=3.11"
license = "MIT"
license-files = ["LICENSE"]
authors = [
  { name = "acme" }
]
keywords = []
classifiers = [
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3 :: Only",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Programming Language :: Python :: 3.14",
    "License :: OSI Approved :: MIT License",
    "Intended Audience :: Developers",
]
dependencies = []

[project.urls]
Homepage = "https://github.com/acme/my-project"
Repository = "https://github.com/acme/my-project"

[tool.hatch.build.targets.wheel]
packages = ["src/my_project"]

[dependency-groups]
test = [
    "pytest>=8.0.0",
    "pytest-cov>=6.0.0",
    "pytest-xdist>=3.0.0",
]
lint = [
    "ruff>=0.11.0",
]
dev = []
"""

    def test_pyproject_toml_full_content(self, git_tmp_path):
        """The generated pyproject.toml must match the expected snapshot exactly."""
        with patch("rhiza.commands.init._get_github_username", return_value="acme"):
            init(git_tmp_path, project_name="my-project", package_name="my_project", git_host="github")

        content = (git_tmp_path / "pyproject.toml").read_text()
        assert content == self.EXPECTED


class TestGetGithubUsername:
    """Tests for the _get_github_username helper."""

    @patch("rhiza.commands.init.subprocess.run")
    def test_extracts_username_from_https_url(self, mock_run, tmp_path):
        """Parses the org/user from an HTTPS remote URL."""
        mock_run.return_value = MagicMock(returncode=0, stdout="https://github.com/acme/my-project.git\n")
        assert _get_github_username(tmp_path) == "acme"

    @patch("rhiza.commands.init.subprocess.run")
    def test_extracts_username_from_ssh_url(self, mock_run, tmp_path):
        """Parses the org/user from an SSH remote URL."""
        mock_run.return_value = MagicMock(returncode=0, stdout="git@github.com:acme/my-project.git\n")
        assert _get_github_username(tmp_path) == "acme"

    @patch("rhiza.commands.init.subprocess.run")
    def test_falls_back_when_no_remote(self, mock_run, tmp_path):
        """Returns 'your-org' when git remote get-url fails."""
        mock_run.return_value = MagicMock(returncode=128, stdout="")
        assert _get_github_username(tmp_path) == "your-org"

    @patch("rhiza.commands.init.subprocess.run", side_effect=OSError("git not found"))
    def test_falls_back_on_os_error(self, mock_run, tmp_path):
        """Returns 'your-org' when git is unavailable."""
        assert _get_github_username(tmp_path) == "your-org"


class TestCreateUvLock:
    """Tests for the _create_uv_lock helper."""

    @patch("rhiza.commands.init.subprocess.run")
    def test_runs_uv_lock_when_no_lockfile(self, mock_run, tmp_path):
        """Calls 'uv lock' when uv.lock does not exist."""
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        _create_uv_lock(tmp_path)
        mock_run.assert_called_once()
        assert mock_run.call_args[0][0] == ["uv", "lock"]

    @patch("rhiza.commands.init.subprocess.run")
    def test_skips_when_lockfile_already_exists(self, mock_run, tmp_path):
        """Does not call 'uv lock' when uv.lock already exists."""
        (tmp_path / "uv.lock").write_text("")
        _create_uv_lock(tmp_path)
        mock_run.assert_not_called()

    @patch("rhiza.commands.init.subprocess.run")
    def test_warns_on_nonzero_exit(self, mock_run, tmp_path):
        """Logs a warning but does not raise when uv lock fails."""
        mock_run.return_value = MagicMock(returncode=1, stderr="some error")
        _create_uv_lock(tmp_path)  # must not raise

    @patch("rhiza.commands.init.subprocess.run", side_effect=FileNotFoundError("uv not found"))
    def test_warns_when_uv_not_installed(self, mock_run, tmp_path):
        """Logs a warning but does not raise when uv is not on PATH."""
        _create_uv_lock(tmp_path)  # must not raise

    def test_init_creates_uv_lock(self, git_tmp_path):
        """init() calls _create_uv_lock as part of the Python project bootstrap."""
        with (
            patch("rhiza.commands.init._create_uv_lock") as mock_lock,
            patch("rhiza.commands.init._get_github_username", return_value="acme"),
        ):
            init(git_tmp_path, git_host="github")
        mock_lock.assert_called_once_with(git_tmp_path)
