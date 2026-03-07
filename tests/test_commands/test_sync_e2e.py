"""End-to-end tests for the ``sync`` command.

Tests exercise the full pipeline from the CLI entry point all the way through
``sync()`` → ``_sync_merge()`` / ``_sync_diff()`` → file-system changes.  A
real git repository on disk acts as the upstream template repository, and
``_construct_git_url`` is patched to return a ``file://`` URL so that no
network access occurs at any point.

Security Notes:
- S101 (assert usage): Asserts are the standard way to validate test conditions in pytest.
- S603 (subprocess without shell=True): Subprocess calls use explicit argument lists without
  shell=True, which is the safe pattern for invoking git in tests.
- S607 (partial executable path): git is resolved via shutil.which() in the git_setup
  fixture before use.
"""

import shutil
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from typer.testing import CliRunner

from rhiza import cli
from rhiza._sync_helpers import _read_lock
from rhiza.models import TemplateLock

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

_RUNNER = CliRunner()
_RHIZA_BRANCH = "main"

_INITIAL_MAKEFILE = "install:\n\tpip install -e .\n"
_INITIAL_EDITORCONFIG = "[*]\nend_of_line = lf\n"
_INITIAL_CI_YML = "name: CI\non: [push]\njobs:\n  build:\n    runs-on: ubuntu-latest\n"

_TEMPLATE_FILES: dict[str, str] = {
    "Makefile": _INITIAL_MAKEFILE,
    ".editorconfig": _INITIAL_EDITORCONFIG,
    ".github/workflows/ci.yml": _INITIAL_CI_YML,
}


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _run_git(
    args: list[str],
    cwd: Path,
    git_executable: str,
    git_env: dict[str, str],
    check: bool = True,
) -> subprocess.CompletedProcess:  # type: ignore[type-arg]
    """Run a git command in the given working directory.

    Args:
        args: Git sub-command and arguments (without the ``git`` binary).
        cwd: Working directory for the command.
        git_executable: Absolute path to the git binary.
        git_env: Environment variables to pass to git.
        check: Whether to raise on non-zero exit code.

    Returns:
        The completed process object.
    """
    return subprocess.run(  # nosec B603
        [git_executable, *args],
        cwd=cwd,
        check=check,
        capture_output=True,
        text=True,
        env=git_env,
    )


def _commit_all(
    project: Path,
    git_executable: str,
    git_env: dict[str, str],
    message: str = "add files",
) -> None:
    """Stage all files in *project* and create a commit.

    Args:
        project: Path to the git repository.
        git_executable: Absolute path to git.
        git_env: Environment variables for git.
        message: Commit message.
    """
    _run_git(["add", "."], project, git_executable, git_env)
    _run_git(["commit", "-m", message], project, git_executable, git_env)


def _advance_upstream(
    upstream_bare_path: Path,
    git_executable: str,
    git_env: dict[str, str],
    changes: dict[str, str],
) -> str:
    """Add or modify files in the upstream bare repo and return the new HEAD SHA.

    Clones the bare repo into a temporary working directory, applies
    ``changes``, commits, pushes back to the bare repo, and cleans up.

    Args:
        upstream_bare_path: Path to the upstream bare git repository.
        git_executable: Absolute path to the git binary.
        git_env: Environment variables for git commands.
        changes: Mapping of repository-relative path → new file content.

    Returns:
        The new HEAD commit SHA after the push.
    """
    parent = Path(tempfile.mkdtemp())
    work_dir = parent / "advance_work"
    try:
        _run_git(
            ["clone", str(upstream_bare_path), str(work_dir)],
            parent,
            git_executable,
            git_env,
        )
        _run_git(["config", "user.email", "upstream@test.com"], work_dir, git_executable, git_env)
        _run_git(["config", "user.name", "Upstream Bot"], work_dir, git_executable, git_env)

        for rel_path, content in changes.items():
            file_path = work_dir / rel_path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content)

        _run_git(["add", "."], work_dir, git_executable, git_env)
        _run_git(["commit", "-m", "advance upstream"], work_dir, git_executable, git_env)
        _run_git(["push", "origin", _RHIZA_BRANCH], work_dir, git_executable, git_env)

        result = _run_git(["rev-parse", "HEAD"], work_dir, git_executable, git_env)
        return result.stdout.strip()
    finally:
        shutil.rmtree(parent, ignore_errors=True)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def upstream_bare_repo(tmp_path: Path, git_setup: tuple[str, dict]) -> tuple[Path, str]:
    """Create a bare upstream git repository containing initial template files.

    Initialises a working clone, adds ``Makefile``, ``.editorconfig``, and
    ``.github/workflows/ci.yml``, commits them, then produces a bare clone
    for use as the fake remote.

    Args:
        tmp_path: Pytest-provided temporary directory.
        git_setup: Tuple of ``(git_executable, git_env)`` from the shared fixture.

    Returns:
        Tuple of ``(bare_repo_path, head_sha)``.
    """
    git_executable, git_env = git_setup

    work = tmp_path / "upstream_work"
    bare = tmp_path / "upstream_bare"

    # Initialise working repo.
    work.mkdir()
    _run_git(["init"], work, git_executable, git_env)
    _run_git(["config", "user.email", "upstream@test.com"], work, git_executable, git_env)
    _run_git(["config", "user.name", "Upstream"], work, git_executable, git_env)
    # Force branch name to 'main' (works with any git version via symbolic-ref).
    _run_git(["symbolic-ref", "HEAD", "refs/heads/main"], work, git_executable, git_env)

    # Populate template files.
    for rel_path, content in _TEMPLATE_FILES.items():
        file_path = work / rel_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)

    _run_git(["add", "."], work, git_executable, git_env)
    _run_git(["commit", "-m", "initial template"], work, git_executable, git_env)

    # Create bare clone from the working repo.
    _run_git(["clone", "--bare", str(work), str(bare)], tmp_path, git_executable, git_env)

    # Allow blob filtering so --filter=blob:none works for file:// clones.
    _run_git(["config", "uploadpack.allowFilter", "true"], bare, git_executable, git_env)
    _run_git(["config", "uploadpack.allowAnySHA1InWant", "true"], bare, git_executable, git_env)

    result = _run_git(["rev-parse", "HEAD"], bare, git_executable, git_env)
    head_sha = result.stdout.strip()

    return bare, head_sha


@pytest.fixture
def target_project(
    tmp_path: Path,
    git_setup: tuple[str, dict],
    upstream_bare_repo: tuple[Path, str],
) -> Path:
    """Create a minimal target project with a valid ``.rhiza/template.yml``.

    Initialises a git repository, writes ``.rhiza/template.yml`` pointing to
    the local bare upstream repo (using a dummy ``template-repository`` value
    since the URL is overridden by patching ``_construct_git_url`` in tests),
    and makes an initial commit.

    Args:
        tmp_path: Pytest-provided temporary directory.
        git_setup: Tuple of ``(git_executable, git_env)`` from the shared fixture.
        upstream_bare_repo: Tuple of ``(bare_repo_path, head_sha)`` from the
            upstream fixture.

    Returns:
        Path to the target project directory.
    """
    git_executable, git_env = git_setup
    _bare_path, _ = upstream_bare_repo

    target = tmp_path / "target"
    target.mkdir()

    # Initialise git repo.
    _run_git(["init"], target, git_executable, git_env)
    _run_git(["config", "user.email", "project@test.com"], target, git_executable, git_env)
    _run_git(["config", "user.name", "Project"], target, git_executable, git_env)
    _run_git(["symbolic-ref", "HEAD", "refs/heads/main"], target, git_executable, git_env)

    # Write .rhiza/template.yml.  The template-repository value is a placeholder
    # because _construct_git_url is patched to return the local file:// URL.
    rhiza_dir = target / ".rhiza"
    rhiza_dir.mkdir()
    config: dict = {
        "template-repository": "local/upstream",
        "template-branch": _RHIZA_BRANCH,
        "template-host": "github",
        "include": list(_TEMPLATE_FILES.keys()),
    }
    with open(rhiza_dir / "template.yml", "w") as fh:
        yaml.dump(config, fh)

    # Add pyproject.toml so Python project-structure validation passes.
    (target / "pyproject.toml").write_text('[project]\nname = "test-project"\nversion = "0.1.0"\n')

    # Initial commit so the target has a valid HEAD for git operations.
    (target / "README.md").write_text("# Test Project\n")
    _run_git(["add", "."], target, git_executable, git_env)
    _run_git(["commit", "-m", "initial project"], target, git_executable, git_env)

    return target


# ---------------------------------------------------------------------------
# Helper: build the patched git URL for a given bare repo path
# ---------------------------------------------------------------------------


def _file_url(bare_path: Path) -> str:
    """Return a ``file://`` git URL for the given bare repository path.

    Args:
        bare_path: Absolute path to the bare git repository on disk.

    Returns:
        A ``file://`` URL string suitable for use as a git remote.
    """
    return f"file://{bare_path}"


# ---------------------------------------------------------------------------
# Test classes
# ---------------------------------------------------------------------------


@pytest.mark.e2e
class TestSyncE2EFirstSync:
    """Tests the first-sync path (no lock file present)."""

    def test_first_sync_merge_copies_all_template_files(
        self,
        git_setup: tuple[str, dict],
        upstream_bare_repo: tuple[Path, str],
        target_project: Path,
    ) -> None:
        """After merge sync, every template file exists in target and lock is written.

        Args:
            git_setup: Git executable and environment from the shared fixture.
            upstream_bare_repo: Bare upstream repo path and HEAD SHA.
            target_project: Path to the initialised target project.
        """
        bare_path, head_sha = upstream_bare_repo
        target = target_project

        with patch("rhiza.commands.sync._construct_git_url", return_value=_file_url(bare_path)):
            result = _RUNNER.invoke(cli.app, ["sync", str(target)])

        assert result.exit_code == 0, result.output

        for rel_path in _TEMPLATE_FILES:
            assert (target / rel_path).exists(), f"Expected {rel_path} in target after first sync"

        lock_path = target / ".rhiza" / "template.lock"
        assert lock_path.exists(), "Lock file must be created after first sync"
        assert _read_lock(target) == head_sha, "Lock SHA must equal upstream HEAD"

    def test_first_sync_diff_does_not_copy_files_or_write_lock(
        self,
        upstream_bare_repo: tuple[Path, str],
        target_project: Path,
    ) -> None:
        """The diff strategy reports changes but neither copies files nor writes the lock.

        Args:
            upstream_bare_repo: Bare upstream repo path and HEAD SHA.
            target_project: Path to the initialised target project.
        """
        bare_path, _ = upstream_bare_repo
        target = target_project

        with patch("rhiza.commands.sync._construct_git_url", return_value=_file_url(bare_path)):
            result = _RUNNER.invoke(cli.app, ["sync", str(target), "--strategy", "diff"])

        assert result.exit_code == 0, result.output

        for rel_path in _TEMPLATE_FILES:
            assert not (target / rel_path).exists(), f"{rel_path} must NOT be copied by diff strategy"

        lock_path = target / ".rhiza" / "template.lock"
        assert not lock_path.exists(), "Lock file must NOT be written by diff strategy"

    def test_first_sync_creates_lock_with_correct_metadata(
        self,
        upstream_bare_repo: tuple[Path, str],
        target_project: Path,
    ) -> None:
        """The lock file written after first sync contains the correct structured metadata.

        Args:
            upstream_bare_repo: Bare upstream repo path and HEAD SHA.
            target_project: Path to the initialised target project.
        """
        bare_path, head_sha = upstream_bare_repo
        target = target_project

        with patch("rhiza.commands.sync._construct_git_url", return_value=_file_url(bare_path)):
            result = _RUNNER.invoke(cli.app, ["sync", str(target)])

        assert result.exit_code == 0, result.output

        lock = TemplateLock.from_yaml(target / ".rhiza" / "template.lock")
        assert lock.sha == head_sha
        assert lock.repo == "local/upstream"
        assert lock.host == "github"
        assert lock.ref == _RHIZA_BRANCH
        assert lock.strategy == "merge"
        assert lock.synced_at, "synced_at must be a non-empty timestamp string"


@pytest.mark.e2e
class TestSyncE2ESubsequentSync:
    """Tests the incremental sync path (lock file already present, upstream has changed)."""

    def test_subsequent_sync_applies_upstream_changes(
        self,
        git_setup: tuple[str, dict],
        upstream_bare_repo: tuple[Path, str],
        target_project: Path,
    ) -> None:
        """Upstream modifies Makefile; after sync the target reflects the change and lock is updated.

        Args:
            git_setup: Git executable and environment from the shared fixture.
            upstream_bare_repo: Bare upstream repo path and initial HEAD SHA.
            target_project: Path to the initialised target project.
        """
        bare_path, _ = upstream_bare_repo
        git_executable, git_env = git_setup
        target = target_project

        # First sync to establish baseline.
        with patch("rhiza.commands.sync._construct_git_url", return_value=_file_url(bare_path)):
            result = _RUNNER.invoke(cli.app, ["sync", str(target)])
        assert result.exit_code == 0, result.output

        # Advance upstream: add a test target to Makefile.
        new_makefile = _INITIAL_MAKEFILE + "\ntest:\n\tpytest\n"
        new_sha = _advance_upstream(bare_path, git_executable, git_env, {"Makefile": new_makefile})

        # Second sync.
        with patch("rhiza.commands.sync._construct_git_url", return_value=_file_url(bare_path)):
            result = _RUNNER.invoke(cli.app, ["sync", str(target)])
        assert result.exit_code == 0, result.output

        makefile_content = (target / "Makefile").read_text()
        assert "pytest" in makefile_content, "Upstream change (test target) must be applied"
        assert _read_lock(target) == new_sha, "Lock SHA must be updated to the new upstream HEAD"

    def test_subsequent_sync_preserves_local_modifications(
        self,
        git_setup: tuple[str, dict],
        upstream_bare_repo: tuple[Path, str],
        target_project: Path,
    ) -> None:
        """Local and upstream changes on different lines are both preserved via 3-way merge.

        The upstream adds a ``test:`` target at the end of Makefile; the local
        project adds a comment at the top.  Since the changes are non-overlapping,
        the 3-way merge (``git merge-file``) must preserve both.

        Args:
            git_setup: Git executable and environment from the shared fixture.
            upstream_bare_repo: Bare upstream repo path and initial HEAD SHA.
            target_project: Path to the initialised target project.
        """
        bare_path, _ = upstream_bare_repo
        git_executable, git_env = git_setup
        target = target_project

        # First sync — copies Makefile to target.
        with patch("rhiza.commands.sync._construct_git_url", return_value=_file_url(bare_path)):
            result = _RUNNER.invoke(cli.app, ["sync", str(target)])
        assert result.exit_code == 0, result.output

        # Local modification: prepend a comment (non-overlapping with the upstream change).
        local_makefile = "# local customization\n" + _INITIAL_MAKEFILE
        (target / "Makefile").write_text(local_makefile)
        _commit_all(target, git_executable, git_env, "local: add comment to Makefile")

        # Advance upstream: append a test target at the bottom (non-overlapping).
        new_makefile = _INITIAL_MAKEFILE + "\ntest:\n\tpytest\n"
        _advance_upstream(bare_path, git_executable, git_env, {"Makefile": new_makefile})

        # Second sync — 3-way merge should combine both changes.
        with patch("rhiza.commands.sync._construct_git_url", return_value=_file_url(bare_path)):
            result = _RUNNER.invoke(cli.app, ["sync", str(target)])
        assert result.exit_code == 0, result.output

        content = (target / "Makefile").read_text()
        assert "# local customization" in content, "Local comment must be preserved after merge"
        assert "pytest" in content, "Upstream test target must be applied by the merge"

    def test_subsequent_sync_diff_reports_changes_without_modifying(
        self,
        git_setup: tuple[str, dict],
        upstream_bare_repo: tuple[Path, str],
        target_project: Path,
    ) -> None:
        """With ``--strategy diff``, the output mentions changes but files and lock are unchanged.

        Args:
            git_setup: Git executable and environment from the shared fixture.
            upstream_bare_repo: Bare upstream repo path and initial HEAD SHA.
            target_project: Path to the initialised target project.
        """
        bare_path, initial_sha = upstream_bare_repo
        git_executable, git_env = git_setup
        target = target_project

        # First sync (merge) to establish baseline and lock file.
        with patch("rhiza.commands.sync._construct_git_url", return_value=_file_url(bare_path)):
            result = _RUNNER.invoke(cli.app, ["sync", str(target)])
        assert result.exit_code == 0, result.output
        assert _read_lock(target) == initial_sha

        # Advance upstream.
        new_makefile = _INITIAL_MAKEFILE + "\ntest:\n\tpytest\n"
        _advance_upstream(bare_path, git_executable, git_env, {"Makefile": new_makefile})

        # Record current Makefile content and lock SHA before diff sync.
        makefile_before = (target / "Makefile").read_text()
        lock_sha_before = _read_lock(target)

        # Diff sync — must not modify anything.
        with patch("rhiza.commands.sync._construct_git_url", return_value=_file_url(bare_path)):
            result = _RUNNER.invoke(cli.app, ["sync", str(target), "--strategy", "diff"])
        assert result.exit_code == 0, result.output

        assert (target / "Makefile").read_text() == makefile_before, "Makefile must be unchanged after diff sync"
        assert _read_lock(target) == lock_sha_before, "Lock SHA must not change after diff sync"

    def test_subsequent_sync_already_up_to_date(
        self,
        upstream_bare_repo: tuple[Path, str],
        target_project: Path,
    ) -> None:
        """When lock SHA equals upstream HEAD, sync exits 0 and no files are modified.

        Args:
            upstream_bare_repo: Bare upstream repo path and HEAD SHA.
            target_project: Path to the initialised target project.
        """
        bare_path, head_sha = upstream_bare_repo
        target = target_project

        # First sync.
        with patch("rhiza.commands.sync._construct_git_url", return_value=_file_url(bare_path)):
            result = _RUNNER.invoke(cli.app, ["sync", str(target)])
        assert result.exit_code == 0, result.output
        assert _read_lock(target) == head_sha

        # Record state before second sync (no upstream change).
        makefile_mtime = (target / "Makefile").stat().st_mtime

        # Second sync — upstream is unchanged, so early-exit path is taken.
        with patch("rhiza.commands.sync._construct_git_url", return_value=_file_url(bare_path)):
            result = _RUNNER.invoke(cli.app, ["sync", str(target)])
        assert result.exit_code == 0, result.output

        assert (target / "Makefile").stat().st_mtime == makefile_mtime, (
            "Makefile must not be touched when already up to date"
        )
        assert _read_lock(target) == head_sha, "Lock SHA must remain unchanged"


@pytest.mark.e2e
class TestSyncE2ETargetBranch:
    """Tests the ``--target-branch`` flag."""

    def test_target_branch_creates_new_branch(
        self,
        git_setup: tuple[str, dict],
        upstream_bare_repo: tuple[Path, str],
        target_project: Path,
    ) -> None:
        """``--target-branch`` creates the named branch in the target repository.

        Args:
            git_setup: Git executable and environment from the shared fixture.
            upstream_bare_repo: Bare upstream repo path and HEAD SHA.
            target_project: Path to the initialised target project.
        """
        bare_path, _ = upstream_bare_repo
        git_executable, git_env = git_setup
        target = target_project

        with patch("rhiza.commands.sync._construct_git_url", return_value=_file_url(bare_path)):
            result = _RUNNER.invoke(
                cli.app,
                ["sync", str(target), "--target-branch", "update-templates"],
            )
        assert result.exit_code == 0, result.output

        branch_result = _run_git(["branch", "--list", "update-templates"], target, git_executable, git_env)
        assert "update-templates" in branch_result.stdout, "Branch 'update-templates' must exist after sync"

    def test_target_branch_checks_out_existing_branch(
        self,
        git_setup: tuple[str, dict],
        upstream_bare_repo: tuple[Path, str],
        target_project: Path,
    ) -> None:
        """If the branch already exists, sync checks it out and applies changes there.

        Args:
            git_setup: Git executable and environment from the shared fixture.
            upstream_bare_repo: Bare upstream repo path and HEAD SHA.
            target_project: Path to the initialised target project.
        """
        bare_path, _ = upstream_bare_repo
        git_executable, git_env = git_setup
        target = target_project

        # Pre-create the target branch.
        _run_git(["checkout", "-b", "update-templates"], target, git_executable, git_env)
        _run_git(["checkout", _RHIZA_BRANCH], target, git_executable, git_env)

        with patch("rhiza.commands.sync._construct_git_url", return_value=_file_url(bare_path)):
            result = _RUNNER.invoke(
                cli.app,
                ["sync", str(target), "--target-branch", "update-templates"],
            )
        assert result.exit_code == 0, result.output

        current_branch = _run_git(["branch", "--show-current"], target, git_executable, git_env)
        assert current_branch.stdout.strip() == "update-templates", (
            "Active branch must be 'update-templates' after sync with --target-branch"
        )


@pytest.mark.e2e
class TestSyncE2ECLIErrors:
    """Tests error handling paths exposed via the CLI."""

    def test_invalid_strategy_exits_nonzero(self, tmp_path: Path) -> None:
        """An unrecognised strategy value causes a non-zero exit code.

        Args:
            tmp_path: Pytest-provided temporary directory (used as target placeholder).
        """
        result = _RUNNER.invoke(cli.app, ["sync", str(tmp_path), "--strategy", "invalid"])
        assert result.exit_code != 0

    def test_missing_template_yml_exits_nonzero(
        self,
        tmp_path: Path,
        git_setup: tuple[str, dict],
    ) -> None:
        """Target directory with no ``.rhiza/template.yml`` causes a non-zero exit.

        Args:
            tmp_path: Pytest-provided temporary directory.
            git_setup: Git executable and environment from the shared fixture.
        """
        git_executable, git_env = git_setup
        target = tmp_path / "no_template"
        target.mkdir()
        _run_git(["init"], target, git_executable, git_env)

        result = _RUNNER.invoke(cli.app, ["sync", str(target)])
        assert result.exit_code != 0

    def test_nonexistent_target_exits_nonzero(self, tmp_path: Path) -> None:
        """Passing a path that does not exist causes a non-zero exit code.

        Args:
            tmp_path: Pytest-provided temporary directory.
        """
        nonexistent = tmp_path / "does_not_exist"
        result = _RUNNER.invoke(cli.app, ["sync", str(nonexistent)])
        assert result.exit_code != 0


@pytest.mark.e2e
class TestSyncE2EOrphanCleanup:
    """Tests that orphaned files (no longer in the template) are deleted on sync."""

    def test_orphaned_files_deleted_on_first_sync_after_history(
        self,
        upstream_bare_repo: tuple[Path, str],
        target_project: Path,
    ) -> None:
        """A file listed in ``.rhiza/history`` but absent from the template is deleted.

        Scenario: a previous sync tracked ``old.txt`` via the legacy history file.
        The upstream template no longer includes ``old.txt``.  After sync the
        file must be removed from the target.

        Args:
            upstream_bare_repo: Bare upstream repo path and HEAD SHA.
            target_project: Path to the initialised target project.
        """
        bare_path, _ = upstream_bare_repo
        target = target_project

        # Create the orphaned file in the target.
        (target / "old.txt").write_text("old content\n")

        # Write a legacy history file that tracks old.txt.
        history_file = target / ".rhiza" / "history"
        history_file.write_text("# Rhiza Template History\nold.txt\n")

        with patch("rhiza.commands.sync._construct_git_url", return_value=_file_url(bare_path)):
            result = _RUNNER.invoke(cli.app, ["sync", str(target)])
        assert result.exit_code == 0, result.output

        assert not (target / "old.txt").exists(), "Orphaned file must be deleted after sync"
