"""End-to-end tests for rhiza init.

These tests invoke the CLI (not the Python function directly) and verify
that the generated project is *functional*: the test file produced by
``rhiza init`` must pass under pytest without any manual edits.

The distinguishing characteristic of these tests is that they run an
out-of-process ``pytest`` invocation against the scaffold created by
``rhiza init``, providing a stronger guarantee than unit tests that only
inspect file contents.
"""

import os
import subprocess
import sys
from pathlib import Path

import yaml
from typer.testing import CliRunner

from rhiza import cli


def _git_init(path: Path) -> None:
    """Initialise a bare git repository at *path* (required by ``validate``)."""
    subprocess.run(["git", "init", str(path)], check=True, capture_output=True)  # nosec B603 B607
    subprocess.run(
        ["git", "config", "user.email", "ci@test.local"],
        check=True,
        capture_output=True,
        cwd=path,
    )  # nosec B603 B607
    subprocess.run(
        ["git", "config", "user.name", "CI Test"],
        check=True,
        capture_output=True,
        cwd=path,
    )  # nosec B603 B607


class TestInitE2E:
    """End-to-end tests for ``rhiza init``."""

    # ------------------------------------------------------------------
    # Core E2E: the generated tests must pass under pytest
    # ------------------------------------------------------------------

    def test_generated_tests_pass(self, tmp_path):
        """Generated tests/test_main.py must pass when run with pytest.

        This is the primary end-to-end assertion: ``rhiza init`` should
        produce a *working* project, not just a skeleton that happens to
        contain valid Python syntax.
        """
        _git_init(tmp_path)

        runner = CliRunner()
        result = runner.invoke(
            cli.app,
            ["init", str(tmp_path), "--git-host", "github", "--project-name", "myproject"],
        )
        assert result.exit_code == 0, f"rhiza init failed:\n{result.stdout}"

        test_file = tmp_path / "tests" / "test_main.py"
        assert test_file.exists(), "tests/test_main.py was not created"

        env = {**os.environ, "PYTHONPATH": str(tmp_path / "src")}
        proc = subprocess.run(  # nosec B603
            [sys.executable, "-m", "pytest", str(test_file), "--tb=short", "-q"],
            capture_output=True,
            text=True,
            env=env,
        )
        assert proc.returncode == 0, (
            f"Generated tests failed:\n--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}"
        )

    # ------------------------------------------------------------------
    # Full file-structure checks
    # ------------------------------------------------------------------

    def test_github_structure(self, tmp_path):
        """``rhiza init --git-host github`` produces the complete expected layout."""
        _git_init(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            cli.app,
            ["init", str(tmp_path), "--git-host", "github", "--project-name", "demo"],
        )
        assert result.exit_code == 0, f"rhiza init failed:\n{result.stdout}"

        # .rhiza/template.yml
        template_file = tmp_path / ".rhiza" / "template.yml"
        assert template_file.exists()
        config = yaml.safe_load(template_file.read_text())
        assert config["repository"] == "jebel-quant/rhiza"
        assert config["ref"] == "main"
        assert "github" in config["templates"]
        assert "gitlab" not in config["templates"]

        # Python package structure
        pkg = tmp_path / "src" / "demo"
        assert pkg.is_dir()
        assert (pkg / "__init__.py").exists()
        assert (pkg / "main.py").exists()

        # Test scaffold
        assert (tmp_path / "tests" / "test_main.py").exists()

        # Project metadata
        assert (tmp_path / "pyproject.toml").exists()
        assert (tmp_path / "README.md").exists()

    def test_gitlab_structure(self, tmp_path):
        """``rhiza init --git-host gitlab`` selects the gitlab template bundle."""
        _git_init(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            cli.app,
            ["init", str(tmp_path), "--git-host", "gitlab", "--project-name", "demo"],
        )
        assert result.exit_code == 0, f"rhiza init failed:\n{result.stdout}"

        config = yaml.safe_load((tmp_path / ".rhiza" / "template.yml").read_text())
        assert "gitlab" in config["templates"]
        assert "github" not in config["templates"]

    # ------------------------------------------------------------------
    # Chained commands
    # ------------------------------------------------------------------

    def test_init_then_validate(self, tmp_path):
        """``rhiza validate`` must exit 0 immediately after ``rhiza init``."""
        _git_init(tmp_path)
        runner = CliRunner()

        init_result = runner.invoke(
            cli.app,
            ["init", str(tmp_path), "--git-host", "github"],
        )
        assert init_result.exit_code == 0, f"rhiza init failed:\n{init_result.stdout}"

        validate_result = runner.invoke(cli.app, ["validate", str(tmp_path)])
        assert validate_result.exit_code == 0, f"rhiza validate failed:\n{validate_result.stdout}"

    # ------------------------------------------------------------------
    # Idempotency
    # ------------------------------------------------------------------

    def test_init_is_idempotent(self, tmp_path):
        """Running ``rhiza init`` twice must not alter files created by the first run."""
        _git_init(tmp_path)
        runner = CliRunner()
        args = ["init", str(tmp_path), "--git-host", "github", "--project-name", "stable"]

        first = runner.invoke(cli.app, args)
        assert first.exit_code == 0, f"First rhiza init failed:\n{first.stdout}"

        snapshot = {
            p.relative_to(tmp_path): p.read_text() for p in tmp_path.rglob("*") if p.is_file() and ".git" not in p.parts
        }

        second = runner.invoke(cli.app, args)
        assert second.exit_code == 0, f"Second rhiza init failed:\n{second.stdout}"

        for rel_path, original_content in snapshot.items():
            current_content = (tmp_path / rel_path).read_text()
            assert current_content == original_content, f"File changed after second init: {rel_path}"
