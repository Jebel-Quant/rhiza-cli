"""Rhiza-specific benchmark tests.

Measures the performance of core sync helper functions on local fixtures so
that regressions in I/O-heavy or computation-heavy paths are detectable in CI.

Uses pytest-benchmark for timing and comparison.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from rhiza._sync_helpers import (
    _excluded_set,
    _expand_paths,
    _read_lock,
    _write_lock,
)
from rhiza.commands.status import status
from rhiza.commands.validate import validate
from rhiza.models import TemplateLock
from rhiza.subprocess_utils import get_git_executable

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def lock_fixture(tmp_path: Path) -> Path:
    """Write a YAML lock file and return the project directory."""
    lock = TemplateLock(
        sha="abcdef1234567890abcdef1234567890abcdef12",
        repo="jebel-quant/rhiza",
        host="github",
        ref="main",
        include=[".github/", ".rhiza/"],
        exclude=[],
        templates=[],
    )
    _write_lock(tmp_path, lock)
    return tmp_path


@pytest.fixture
def clone_dir(tmp_path: Path) -> Path:
    """Create a realistic template clone directory tree."""
    root = tmp_path / "clone"
    # Simulate a few common template paths
    for path in [
        ".github/workflows/ci.yml",
        ".github/workflows/release.yml",
        ".rhiza/template.yml",
        ".rhiza/history",
        "Makefile",
        "README.md",
        "pyproject.toml",
        ".pre-commit-config.yaml",
    ]:
        full = root / path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(f"# {path}\n", encoding="utf-8")
    return root


@pytest.fixture
def fixture_project(tmp_path: Path) -> Path:
    """Create a minimal valid project for validate()."""
    git = shutil.which("git") or get_git_executable()
    # Initialise a bare git repo so validate() is happy
    subprocess.run(  # nosec B603
        [git, "init", str(tmp_path)],
        check=True,
        capture_output=True,
    )
    subprocess.run(  # nosec B603
        [git, "-C", str(tmp_path), "config", "user.email", "test@example.com"],
        check=True,
        capture_output=True,
    )
    subprocess.run(  # nosec B603
        [git, "-C", str(tmp_path), "config", "user.name", "Test"],
        check=True,
        capture_output=True,
    )

    rhiza_dir = tmp_path / ".rhiza"
    rhiza_dir.mkdir()
    template_yml = rhiza_dir / "template.yml"
    template_yml.write_text(
        yaml.dump(
            {
                "repository": "jebel-quant/rhiza",
                "ref": "main",
                "include": [".github", ".rhiza"],
            }
        ),
        encoding="utf-8",
    )

    # Create a minimal pyproject.toml so the Python language validator passes
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n", encoding="utf-8")

    return tmp_path


# ---------------------------------------------------------------------------
# Benchmarks
# ---------------------------------------------------------------------------


class TestSyncHelperBenchmarks:
    """Benchmark suite for core rhiza sync helpers."""

    def test_read_lock_yaml(self, benchmark, lock_fixture: Path) -> None:
        """Benchmark reading a structured YAML lock file."""
        result = benchmark(_read_lock, lock_fixture)
        assert result == "abcdef1234567890abcdef1234567890abcdef12"

    def test_write_lock_yaml(self, benchmark, tmp_path: Path) -> None:
        """Benchmark writing a YAML lock file."""
        lock = TemplateLock(
            sha="deadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
            repo="jebel-quant/rhiza",
            host="github",
            ref="main",
            include=[".github/", ".rhiza/"],
            exclude=[],
            templates=[],
        )

        def _write() -> None:
            _write_lock(tmp_path, lock)

        benchmark(_write)
        assert (tmp_path / ".rhiza" / "template.lock").exists()

    def test_excluded_set(self, benchmark, clone_dir: Path) -> None:
        """Benchmark building the exclusion set from a fixture directory."""
        result = benchmark(_excluded_set, clone_dir, ["README.md"])
        assert "README.md" in result
        assert ".rhiza/template.yml" in result

    def test_expand_paths(self, benchmark, clone_dir: Path) -> None:
        """Benchmark expanding a mix of files and directories."""
        result = benchmark(_expand_paths, clone_dir, ["Makefile", ".github"])
        rel_paths = [str(p.relative_to(clone_dir)) for p in result]
        assert "Makefile" in rel_paths
        assert any(p.startswith(".github") for p in rel_paths)

    def test_validate(self, benchmark, fixture_project: Path) -> None:
        """Benchmark validate() on a known-good template.yml."""
        result = benchmark(validate, fixture_project)
        assert result is True

    def test_status(self, benchmark, lock_fixture: Path) -> None:
        """Benchmark status() with a pre-written lock file."""
        benchmark(status, lock_fixture)
