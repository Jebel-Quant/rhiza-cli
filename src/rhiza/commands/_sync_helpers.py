"""Internal helpers for the ``sync`` command.

This module exposes the private implementation functions used by
:mod:`rhiza.commands.sync`.  Placing them here gives tests a stable import
path (``from rhiza.commands._sync_helpers import ...``) without coupling them
to the command module's public API.
"""

import contextlib
import os
import shutil
import subprocess  # nosec B404
import tempfile
from pathlib import Path
from re import sub

try:
    import fcntl

    _FCNTL_AVAILABLE = True
except ImportError:  # pragma: no cover - Windows
    _FCNTL_AVAILABLE = False

import yaml
from loguru import logger

from rhiza.bundle_resolver import load_bundles_from_clone, resolve_include_paths
from rhiza.models import RhizaTemplate, TemplateLock
from rhiza.subprocess_utils import get_git_executable

# ---------------------------------------------------------------------------
# Diff prefix constants
# ---------------------------------------------------------------------------

_DIFF_SRC_PREFIX = "upstream-template-old"
_DIFF_DST_PREFIX = "upstream-template-new"

# ---------------------------------------------------------------------------
# Lock-file constant
# ---------------------------------------------------------------------------

LOCK_FILE = ".rhiza/template.lock"


def _get_diff(repo0: Path, repo1: Path) -> str:
    """Compute the raw diff between two directory trees using ``git diff --no-index``."""
    git = get_git_executable()
    repo0_str = repo0.resolve().as_posix()
    repo1_str = repo1.resolve().as_posix()
    result = subprocess.run(  # nosec B603  # noqa: S603
        [
            git,
            "-c",
            "diff.noprefix=",
            "diff",
            "--no-index",
            "--relative",
            "--binary",
            f"--src-prefix={_DIFF_SRC_PREFIX}/",
            f"--dst-prefix={_DIFF_DST_PREFIX}/",
            "--no-ext-diff",
            "--no-color",
            repo0_str,
            repo1_str,
        ],
        cwd=repo0_str,
        capture_output=True,
    )
    diff = result.stdout.decode()
    for repo in [repo0_str, repo1_str]:
        repo_nix = sub("/[a-z]:", "", repo)
        diff = diff.replace(f"{_DIFF_SRC_PREFIX}{repo_nix}", _DIFF_SRC_PREFIX).replace(
            f"{_DIFF_DST_PREFIX}{repo_nix}", _DIFF_DST_PREFIX
        )
    diff = diff.replace(repo0_str + "/", "").replace(repo1_str + "/", "")
    return diff


# ---------------------------------------------------------------------------
# Shared template helpers
# ---------------------------------------------------------------------------


def _log_git_stderr_errors(stderr: str | None) -> None:
    """Extract and log only relevant error messages from git stderr.

    Args:
        stderr: Git command stderr output.
    """
    if stderr:
        for line in stderr.strip().split("\n"):
            line = line.strip()
            if line and (line.startswith("fatal:") or line.startswith("error:")):
                logger.error(line)


def _handle_target_branch(
    target: Path, target_branch: str | None, git_executable: str, git_env: dict[str, str]
) -> None:
    """Handle target branch creation or checkout if specified.

    Args:
        target: Path to the target repository.
        target_branch: Optional branch name to create/checkout.
        git_executable: Path to git executable.
        git_env: Environment variables for git commands.
    """
    if not target_branch:
        return

    logger.info(f"Creating/checking out target branch: {target_branch}")
    try:
        result = subprocess.run(  # nosec B603  # noqa: S603
            [git_executable, "rev-parse", "--verify", target_branch],
            cwd=target,
            capture_output=True,
            text=True,
            env=git_env,
        )

        if result.returncode == 0:
            logger.info(f"Branch '{target_branch}' exists, checking out...")
            subprocess.run(  # nosec B603  # noqa: S603
                [git_executable, "checkout", target_branch],
                cwd=target,
                check=True,
                capture_output=True,
                text=True,
                env=git_env,
            )
        else:
            logger.info(f"Creating new branch '{target_branch}'...")
            subprocess.run(  # nosec B603  # noqa: S603
                [git_executable, "checkout", "-b", target_branch],
                cwd=target,
                check=True,
                capture_output=True,
                text=True,
                env=git_env,
            )
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to create/checkout branch '{target_branch}'")
        _log_git_stderr_errors(e.stderr)
        logger.error("Please ensure you have no uncommitted changes or conflicts")
        raise


def _validate_and_load_template(target: Path, branch: str) -> tuple[RhizaTemplate, str, str, list[str], list[str]]:
    """Validate configuration and load template settings.

    Args:
        target: Path to the target repository.
        branch: The Rhiza template branch to use (CLI argument).

    Returns:
        Tuple of (template, rhiza_repo, rhiza_branch, include_paths, excluded_paths).
    """
    from rhiza.commands.validate import validate

    valid = validate(target)
    if not valid:
        logger.error(f"Rhiza template is invalid in: {target}")
        logger.error("Please fix validation errors and try again")
        raise RuntimeError("Rhiza template validation failed")  # noqa: TRY003

    template_file = target / ".rhiza" / "template.yml"
    template = RhizaTemplate.from_yaml(template_file)

    rhiza_repo = template.template_repository
    if not rhiza_repo:
        logger.error("template-repository is not configured in template.yml")
        raise RuntimeError("template-repository is required")  # noqa: TRY003
    rhiza_branch = template.template_branch or branch
    excluded_paths = template.exclude
    include_paths = template.include

    if not template.templates and not include_paths:
        logger.error("No templates or include paths found in template.yml")
        logger.error("Add either 'templates' or 'include' list in template.yml")
        raise RuntimeError("No templates or include paths found in template.yml")  # noqa: TRY003

    if template.templates:
        logger.info("Templates:")
        for t in template.templates:
            logger.info(f"  - {t}")

    if include_paths:
        logger.info("Include paths:")
        for p in include_paths:
            logger.info(f"  - {p}")

    if excluded_paths:
        logger.info("Exclude paths:")
        for p in excluded_paths:
            logger.info(f"  - {p}")

    return template, rhiza_repo, rhiza_branch, include_paths, excluded_paths


def _construct_git_url(rhiza_repo: str, rhiza_host: str) -> str:
    """Construct git clone URL based on host.

    Args:
        rhiza_repo: Repository name in 'owner/repo' format.
        rhiza_host: Git hosting platform ('github' or 'gitlab').

    Returns:
        Git URL for cloning.

    Raises:
        ValueError: If rhiza_host is not supported.
    """
    if rhiza_host == "gitlab":
        git_url = f"https://gitlab.com/{rhiza_repo}.git"
        logger.debug(f"Using GitLab repository: {git_url}")
    elif rhiza_host == "github":
        git_url = f"https://github.com/{rhiza_repo}.git"
        logger.debug(f"Using GitHub repository: {git_url}")
    else:
        logger.error(f"Unsupported template-host: {rhiza_host}")
        logger.error("template-host must be 'github' or 'gitlab'")
        raise ValueError(f"Unsupported template-host: {rhiza_host}. Must be 'github' or 'gitlab'.")  # noqa: TRY003
    return git_url


def _update_sparse_checkout(
    tmp_dir: Path,
    include_paths: list[str],
    git_executable: str,
    git_env: dict[str, str],
) -> None:
    """Update sparse checkout paths in an already-cloned repository.

    Args:
        tmp_dir: Temporary directory with cloned repository.
        include_paths: Paths to include in sparse checkout.
        git_executable: Path to git executable.
        git_env: Environment variables for git commands.
    """
    try:
        logger.debug(f"Updating sparse checkout paths: {include_paths}")
        subprocess.run(  # nosec B603  # noqa: S603
            [git_executable, "sparse-checkout", "set", "--skip-checks", *include_paths],
            cwd=tmp_dir,
            check=True,
            capture_output=True,
            text=True,
            env=git_env,
        )
        logger.debug("Sparse checkout paths updated")
    except subprocess.CalledProcessError as e:
        logger.error("Failed to update sparse checkout paths")
        _log_git_stderr_errors(e.stderr)
        raise


def _clone_template_repository(
    tmp_dir: Path,
    git_url: str,
    rhiza_branch: str,
    include_paths: list[str],
    git_executable: str,
    git_env: dict[str, str],
) -> None:
    """Clone template repository with sparse checkout.

    Args:
        tmp_dir: Temporary directory for cloning.
        git_url: Git repository URL.
        rhiza_branch: Branch to clone.
        include_paths: Initial paths to include in sparse checkout.
        git_executable: Path to git executable.
        git_env: Environment variables for git commands.
    """
    try:
        logger.debug("Executing git clone with sparse checkout")
        subprocess.run(  # nosec B603  # noqa: S603
            [
                git_executable,
                "clone",
                "--depth",
                "1",
                "--filter=blob:none",
                "--sparse",
                "--branch",
                rhiza_branch,
                git_url,
                str(tmp_dir),
            ],
            check=True,
            capture_output=True,
            text=True,
            env=git_env,
        )
        logger.debug("Git clone completed successfully")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to clone repository from {git_url}")
        _log_git_stderr_errors(e.stderr)
        logger.error("Please check that:")
        logger.error("  - The repository exists and is accessible")
        logger.error(f"  - Branch '{rhiza_branch}' exists in the repository")
        logger.error("  - You have network access to the git hosting service")
        raise

    try:
        logger.debug("Initializing sparse checkout")
        subprocess.run(  # nosec B603  # noqa: S603
            [git_executable, "sparse-checkout", "init", "--cone"],
            cwd=tmp_dir,
            check=True,
            capture_output=True,
            text=True,
            env=git_env,
        )
        logger.debug("Sparse checkout initialized")
    except subprocess.CalledProcessError as e:
        logger.error("Failed to initialize sparse checkout")
        _log_git_stderr_errors(e.stderr)
        raise

    try:
        logger.debug(f"Setting sparse checkout paths: {include_paths}")
        subprocess.run(  # nosec B603  # noqa: S603
            [git_executable, "sparse-checkout", "set", "--skip-checks", *include_paths],
            cwd=tmp_dir,
            check=True,
            capture_output=True,
            text=True,
            env=git_env,
        )
        logger.debug("Sparse checkout paths configured")
    except subprocess.CalledProcessError as e:
        logger.error("Failed to configure sparse checkout paths")
        _log_git_stderr_errors(e.stderr)
        raise


def _warn_about_workflow_files(materialized_files: list[Path]) -> None:
    """Warn if workflow files were materialized.

    Args:
        materialized_files: List of materialized file paths.
    """
    workflow_files = [p for p in materialized_files if p.parts[:2] == (".github", "workflows")]

    if workflow_files:
        logger.warning(
            "Workflow files were materialized. Updating these files requires "
            "a token with the 'workflow' permission in GitHub Actions."
        )
        logger.info(f"Workflow files affected: {len(workflow_files)}")


def _files_from_snapshot(snapshot_dir: Path) -> set[Path]:
    """Return all files in *snapshot_dir* as paths relative to that directory.

    Args:
        snapshot_dir: Root of a snapshot directory tree.

    Returns:
        Set of relative file paths found under *snapshot_dir*.
    """
    return {f.relative_to(snapshot_dir) for f in snapshot_dir.rglob("*") if f.is_file()}


def _read_previously_tracked_files(target: Path, base_snapshot: Path | None = None) -> set[Path]:
    """Return the set of files tracked by the last sync.

    Resolution order:
    1. ``template.lock.files`` when the field is present and non-empty.
    2. *base_snapshot* directory listing when provided and non-empty (used as a
       fallback for lock files that pre-date the ``files`` field).
    3. Legacy ``.rhiza/history`` file for backward compatibility.

    Args:
        target: Target repository path.
        base_snapshot: Optional directory containing the template snapshot at
            the previously-synced SHA.  When the lock file has no ``files``
            entry this snapshot is used to reconstruct the tracked-file list,
            avoiding an extra network fetch.

    Returns:
        Set of previously tracked file paths (relative to target), or an empty
        set when no tracking information is found.
    """
    lock_file = target / ".rhiza" / "template.lock"
    if lock_file.exists():
        try:
            lock = TemplateLock.from_yaml(lock_file)
            if lock.files:
                files = {Path(f) for f in lock.files}
                logger.debug(f"Reading previous file list from template.lock ({len(files)} files)")
                return files
            # Lock exists but has no files list - try to reconstruct from the
            # base snapshot that was already fetched during this sync run.
            if base_snapshot is not None and base_snapshot.is_dir():
                snapshot_files = _files_from_snapshot(base_snapshot)
                if snapshot_files:
                    logger.debug(f"Reconstructing previous file list from base snapshot ({len(snapshot_files)} files)")
                    return snapshot_files
        except Exception as e:
            logger.debug(f"Could not read template.lock for orphan cleanup: {e}")

    history_file = target / ".rhiza" / "history"

    if history_file.exists():
        logger.debug(f"Reading existing history file: {history_file.relative_to(target)}")
    else:
        logger.debug("No previous file tracking found")
        return set()

    files = set()
    with history_file.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                files.add(Path(line))
    return files


def _delete_orphaned_file(target: Path, file_path: Path) -> None:
    """Delete a single orphaned file from the target repository.

    Args:
        target: Target repository path.
        file_path: Relative path of the orphaned file to delete.
    """
    full_path = target / file_path
    if full_path.exists():
        try:
            full_path.unlink()
            logger.success(f"[DEL] {file_path}")
        except Exception as e:
            logger.warning(f"Failed to delete {file_path}: {e}")
    else:
        logger.debug(f"Skipping {file_path} (already deleted)")


def _clean_orphaned_files(
    target: Path,
    materialized_files: list[Path],
    base_snapshot: Path | None = None,
    excludes: set[str] | None = None,
    previously_tracked_files: set[Path] | None = None,
) -> None:
    """Clean up files that are no longer maintained by template.

    Files that are explicitly excluded via the ``exclude:`` setting in
    ``template.yml`` are never deleted even if they appear in a previous lock
    but are absent from *materialized_files*.

    Args:
        target: Target repository path.
        materialized_files: List of currently materialized files.
        base_snapshot: Optional directory containing the template snapshot at
            the previously-synced SHA.  Passed through to
            :func:`_read_previously_tracked_files` as a fallback when the lock
            file has no ``files`` entry.  Ignored when *previously_tracked_files*
            is supplied directly.
        excludes: Optional set of relative path strings that are currently
            excluded from the template sync.  Any previously-tracked file
            present in this set is kept (the user explicitly opted it out).
        previously_tracked_files: Optional pre-read set of files that were
            tracked by the previous sync.  When supplied this takes precedence
            over reading from the on-disk lock file, which allows callers to
            snapshot the old state before the lock is overwritten by the merge.
    """
    if previously_tracked_files is None:
        previously_tracked_files = _read_previously_tracked_files(target, base_snapshot=base_snapshot)
    if not previously_tracked_files:
        return

    logger.debug(f"Found {len(previously_tracked_files)} file(s) in previous tracking")

    orphaned_files = previously_tracked_files - set(materialized_files)

    # Don't delete files that the user has explicitly excluded — they have
    # opted those files out of template management and want to keep them.
    if excludes:
        excluded_as_paths = {Path(e) for e in excludes}
        orphaned_files = orphaned_files - excluded_as_paths

    protected_files = {Path(".rhiza/template.yml")}

    if not orphaned_files:
        logger.debug("No orphaned files to clean up")
        return

    logger.info(f"Found {len(orphaned_files)} orphaned file(s) no longer maintained by template")
    for file_path in sorted(orphaned_files):
        if file_path in protected_files:
            logger.info(f"Skipping protected file: {file_path}")
            continue
        _delete_orphaned_file(target, file_path)


# ---------------------------------------------------------------------------
# Lock-file helpers
# ---------------------------------------------------------------------------


def _read_lock(target: Path) -> str | None:
    """Read the last-synced commit SHA from the lock file.

    Handles both the structured YAML format and the legacy plain-SHA format.
    Uses an exclusive advisory lock (via ``fcntl.flock``) when available so
    that two concurrent ``rhiza sync`` processes cannot read a partially-written
    file.  Falls back silently on platforms without ``fcntl`` (e.g. Windows).

    Args:
        target: Path to the target repository.

    Returns:
        The commit SHA string or ``None`` when no lock exists.
    """
    lock_path = target / LOCK_FILE
    if not lock_path.exists():
        return None
    with lock_path.open(encoding="utf-8") as fh:
        if _FCNTL_AVAILABLE:
            fcntl.flock(fh, fcntl.LOCK_EX)
        else:
            logger.debug("fcntl not available - skipping advisory lock on read")
        content = fh.read().strip()
    # Try structured YAML format first
    try:
        data = yaml.safe_load(content)
        if isinstance(data, dict) and "sha" in data:
            return data["sha"]
    except yaml.YAMLError:
        pass
    # Legacy plain-SHA format
    return content


def _write_lock(target: Path, lock: TemplateLock) -> None:
    """Persist the lock data to the YAML lock file.

    Writes to a ``.tmp`` sibling file first, then replaces the real lock file
    atomically with ``os.replace()``.  An exclusive advisory lock (via
    ``fcntl.flock``) is held for the entire write + rename sequence when
    ``fcntl`` is available so that concurrent writers do not corrupt the file.
    Falls back silently on platforms without ``fcntl`` (e.g. Windows).

    Args:
        target: Path to the target repository.
        lock: The :class:`~rhiza.models.TemplateLock` to record.
    """
    lock_path = target / LOCK_FILE
    tmp_path = Path(str(lock_path) + ".tmp")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    # Acquire an exclusive advisory lock via a dedicated lock-fd file so that
    # the flock survives the os.replace() rename of the actual lock file.
    lock_fd_path = Path(str(lock_path) + ".fd")
    try:
        with lock_fd_path.open("a", encoding="utf-8") as lock_fd:
            if _FCNTL_AVAILABLE:
                fcntl.flock(lock_fd, fcntl.LOCK_EX)
            else:
                logger.debug("fcntl not available - skipping advisory lock on write")
            lock.to_yaml(tmp_path)
            os.replace(tmp_path, lock_path)
    finally:
        # Best-effort cleanup of the fd file; failures here are non-critical.
        with contextlib.suppress(OSError):
            lock_fd_path.unlink(missing_ok=True)
    logger.info(f"Updated {LOCK_FILE} -> {lock.sha[:12]}")


def _is_template_config_changed(
    target: Path,
    template: RhizaTemplate,
    rhiza_repo: str,
    rhiza_host: str,
    rhiza_branch: str,
) -> bool:
    """Return True when template.yml settings differ from those recorded in template.lock.

    Compares the key configuration fields that determine *which files* the sync
    manages — repository, host, branch, include paths, exclude paths, and
    template bundle names.  The SHA is intentionally excluded from this
    comparison; it is managed by the sync process itself.

    When no lock file exists this function returns False (first-time sync
    is handled separately by the ``base_sha is None`` path in :func:`sync`).

    Args:
        target: Path to the target repository.
        template: The :class:`~rhiza.models.RhizaTemplate` loaded from
            the current ``template.yml``.
        rhiza_repo: Resolved template repository (e.g. ``"jebel-quant/rhiza"``).
        rhiza_host: Resolved git host (``"github"`` or ``"gitlab"``).
        rhiza_branch: Resolved branch name.

    Returns:
        True if any configuration field differs from the lock, False otherwise.
    """
    lock_path = target / LOCK_FILE
    if not lock_path.exists():
        return False
    try:
        lock = TemplateLock.from_yaml(lock_path)
    except (yaml.YAMLError, TypeError, ValueError):
        return False
    return (
        lock.repo != rhiza_repo
        or lock.host != rhiza_host
        or lock.ref != rhiza_branch
        or lock.include != (template.include or [])
        or lock.exclude != (template.exclude or [])
        or lock.templates != (template.templates or [])
    )


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def _get_head_sha(repo_dir: Path, git_executable: str, git_env: dict[str, str]) -> str:
    """Return the HEAD commit SHA of a cloned repository.

    Args:
        repo_dir: Path to the git repository.
        git_executable: Absolute path to git.
        git_env: Environment variables for git commands.

    Returns:
        The full HEAD SHA.
    """
    result = subprocess.run(  # nosec B603  # noqa: S603
        [git_executable, "rev-parse", "HEAD"],
        cwd=repo_dir,
        capture_output=True,
        text=True,
        check=True,
        env=git_env,
    )
    return result.stdout.strip()


def _clone_at_sha(
    git_url: str,
    sha: str,
    dest: Path,
    include_paths: list[str],
    git_executable: str,
    git_env: dict[str, str],
) -> None:
    """Clone a repository and checkout a specific commit.

    Args:
        git_url: Remote URL to clone from.
        sha: Commit SHA to check out.
        dest: Target directory for the clone.
        include_paths: Paths for sparse checkout.
        git_executable: Absolute path to git.
        git_env: Environment variables for git commands.
    """
    try:
        subprocess.run(  # nosec B603  # noqa: S603
            [
                git_executable,
                "clone",
                "--filter=blob:none",
                "--sparse",
                "--no-checkout",
                git_url,
                str(dest),
            ],
            check=True,
            capture_output=True,
            text=True,
            env=git_env,
        )
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to clone repository for base snapshot: {git_url}")
        _log_git_stderr_errors(e.stderr)
        raise

    # Init sparse checkout and set paths
    try:
        subprocess.run(  # nosec B603  # noqa: S603
            [git_executable, "sparse-checkout", "init", "--cone"],
            cwd=dest,
            check=True,
            capture_output=True,
            text=True,
            env=git_env,
        )
        subprocess.run(  # nosec B603  # noqa: S603
            [git_executable, "sparse-checkout", "set", "--skip-checks", *include_paths],
            cwd=dest,
            check=True,
            capture_output=True,
            text=True,
            env=git_env,
        )
    except subprocess.CalledProcessError as e:
        logger.error("Failed to configure sparse checkout for base snapshot")
        _log_git_stderr_errors(e.stderr)
        raise

    # Checkout the specific SHA
    try:
        subprocess.run(  # nosec B603  # noqa: S603
            [git_executable, "checkout", sha],
            cwd=dest,
            check=True,
            capture_output=True,
            text=True,
            env=git_env,
        )
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to checkout base commit {sha[:12]}")
        _log_git_stderr_errors(e.stderr)
        raise


# ---------------------------------------------------------------------------
# Expand helpers (shared logic with materialize)
# ---------------------------------------------------------------------------


def _expand_paths(base_dir: Path, paths: list[str]) -> list[Path]:
    """Expand file/directory paths relative to *base_dir* into individual files.

    Args:
        base_dir: Root directory to resolve against.
        paths: Relative path strings.

    Returns:
        Flat list of file paths.
    """
    all_files: list[Path] = []
    for p in paths:
        full = base_dir / p
        if full.is_file():
            all_files.append(full)
        elif full.is_dir():
            all_files.extend(f for f in full.rglob("*") if f.is_file())
        else:
            logger.debug(f"Path not found in template repository: {p}")
    return all_files


def _excluded_set(base_dir: Path, excluded_paths: list[str]) -> set[str]:
    """Build a set of relative path strings that should be excluded.

    Args:
        base_dir: Root of the template clone.
        excluded_paths: User-configured exclude list.

    Returns:
        Set of relative path strings.
    """
    result: set[str] = set()
    for f in _expand_paths(base_dir, excluded_paths):
        result.add(str(f.relative_to(base_dir)))

    # Always exclude template config and history
    result.add(".rhiza/template.yml")
    result.add(".rhiza/history")
    return result


# ---------------------------------------------------------------------------
# Cruft-based diff / patch helpers
# ---------------------------------------------------------------------------


def _prepare_snapshot(
    clone_dir: Path,
    include_paths: list[str],
    excludes: set[str],
    snapshot_dir: Path,
) -> list[Path]:
    """Copy included (non-excluded) files from a clone into a clean snapshot directory.

    This creates a flat directory tree suitable for ``git diff --no-index``.

    Args:
        clone_dir: Root of the template clone.
        include_paths: Paths to include.
        excludes: Set of relative paths to exclude.
        snapshot_dir: Destination directory for the snapshot.

    Returns:
        List of relative file paths that were copied.
    """
    materialized: list[Path] = []
    for f in _expand_paths(clone_dir, include_paths):
        rel = str(f.relative_to(clone_dir))
        if rel not in excludes:
            dst = snapshot_dir / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dst)
            materialized.append(Path(rel))
    return materialized


def _parse_diff_filenames(diff: str) -> list[tuple[str, bool, bool]]:
    """Parse a unified diff produced by :func:`_get_diff` into file entries.

    Each entry is ``(rel_path, is_new, is_deleted)`` where *rel_path* is the
    path relative to both snapshot directories.

    Args:
        diff: Unified diff string from :func:`_get_diff`.

    Returns:
        List of ``(rel_path, is_new, is_deleted)`` tuples, one per changed file.
    """
    src_prefix = f"{_DIFF_SRC_PREFIX}/"
    dst_prefix = f"{_DIFF_DST_PREFIX}/"

    results: list[tuple[str, bool, bool]] = []
    is_new = False
    is_deleted = False
    src_path: str | None = None
    dst_path: str | None = None
    in_diff = False

    def _flush() -> None:
        rel = dst_path if not is_deleted else src_path
        if rel:
            results.append((rel, is_new, is_deleted))

    for line in diff.splitlines():
        if line.startswith("diff --git "):
            if in_diff:
                _flush()
            is_new = False
            is_deleted = False
            src_path = None
            dst_path = None
            in_diff = True
        elif line.startswith("new file mode"):
            is_new = True
        elif line.startswith("deleted file mode"):
            is_deleted = True
        elif line.startswith("--- "):
            raw = line[4:].strip().strip('"').split("\t")[0]
            if raw != "/dev/null" and raw.startswith(src_prefix):
                src_path = raw[len(src_prefix) :]
        elif line.startswith("+++ "):
            raw = line[4:].strip().strip('"').split("\t")[0]
            if raw != "/dev/null" and raw.startswith(dst_prefix):
                dst_path = raw[len(dst_prefix) :]

    if in_diff:
        _flush()

    return results


def _merge_file_fallback(
    diff: str,
    target: Path,
    base_snapshot: Path,
    upstream_snapshot: Path,
    git_executable: str,
    git_env: dict[str, str],
) -> bool:
    """Apply *diff* file-by-file using ``git merge-file``.

    Unlike ``git apply -3``, ``git merge-file`` works directly on the file
    contents from *base_snapshot* and *upstream_snapshot*, so it does not
    require the template's blob objects to exist in the target repository.

    Conflict markers (``<<<<<<<`` / ``=======`` / ``>>>>>>>``) are left in
    place for manual resolution when both sides changed the same region.

    Args:
        diff: Unified diff string (used only for file-list parsing).
        target: Path to the target repository.
        base_snapshot: Directory containing files at the previously-synced SHA.
        upstream_snapshot: Directory containing files at the new upstream SHA.
        git_executable: Absolute path to git.
        git_env: Environment variables for git commands.

    Returns:
        True if every file merged cleanly, False if any conflicts remain.
    """
    file_entries = _parse_diff_filenames(diff)
    all_clean = True
    conflict_files: list[str] = []

    for rel_path, is_new, is_deleted in file_entries:
        target_file = target / rel_path
        upstream_file = upstream_snapshot / rel_path
        base_file = base_snapshot / rel_path

        if is_new:
            if upstream_file.exists():
                target_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(upstream_file, target_file)
                logger.debug(f"[merge-file] Added: {rel_path}")
            continue

        if is_deleted:
            if target_file.exists():
                target_file.unlink()
                logger.debug(f"[merge-file] Deleted: {rel_path}")
            continue

        # Modified file — attempt a 3-way merge using the on-disk snapshots.
        if not target_file.exists():
            if upstream_file.exists():
                target_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(upstream_file, target_file)
                logger.debug(f"[merge-file] Created (missing in target): {rel_path}")
            continue

        if not base_file.exists() or not upstream_file.exists():
            # Cannot 3-way-merge without both sides; just take upstream.
            if upstream_file.exists():
                shutil.copy2(upstream_file, target_file)
                logger.debug(f"[merge-file] Overwrite (no base): {rel_path}")
            continue

        result = subprocess.run(  # nosec B603  # noqa: S603
            [
                git_executable,
                "merge-file",
                "-L",
                "ours",
                "-L",
                "base",
                "-L",
                "upstream",
                str(target_file),
                str(base_file),
                str(upstream_file),
            ],
            capture_output=True,
            env=git_env,
        )

        if result.returncode > 0:
            conflict_files.append(rel_path)
            all_clean = False
            logger.warning(f"[merge-file] Conflict in {rel_path} — resolve markers manually")
        elif result.returncode < 0:
            logger.warning(f"[merge-file] Error merging {rel_path}: {result.stderr.decode().strip()}")
            all_clean = False
        else:
            logger.debug(f"[merge-file] Clean merge: {rel_path}")

    if conflict_files:
        logger.warning(f"{len(conflict_files)} file(s) have conflict markers to resolve: " + ", ".join(conflict_files))

    return all_clean


def _apply_diff(
    diff: str,
    target: Path,
    git_executable: str,
    git_env: dict[str, str],
    base_snapshot: Path | None = None,
    upstream_snapshot: Path | None = None,
) -> bool:
    """Apply a diff to the target project using ``git apply -3`` (3-way merge).

    When ``git apply -3`` fails because the template's blob objects are absent
    from the target repository *and* both *base_snapshot* and
    *upstream_snapshot* are provided, falls back to :func:`_merge_file_fallback`
    which uses ``git merge-file`` on the on-disk snapshot files instead.

    Otherwise falls back to ``git apply --reject``.

    Args:
        diff: Unified diff string.
        target: Path to the target repository.
        git_executable: Absolute path to git.
        git_env: Environment variables for git commands.
        base_snapshot: Optional directory containing files at the base SHA.
        upstream_snapshot: Optional directory containing files at the upstream SHA.

    Returns:
        True if the diff applied cleanly, False if there were conflicts.
    """
    if not diff.strip():
        return True

    try:
        subprocess.run(  # nosec B603  # noqa: S603
            [git_executable, "apply", "-3"],
            input=diff.encode(),
            cwd=target,
            check=True,
            capture_output=True,
            env=git_env,
        )
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode() if e.stderr else ""

        # git apply -3 cannot do a real 3-way merge when the template blobs are
        # not present in the target repository's object store.  If we have the
        # snapshot directories on disk, use git merge-file instead — it works
        # directly on file content and needs no shared git history.
        if "lacks the necessary blob" in stderr and base_snapshot is not None and upstream_snapshot is not None:
            logger.debug("git apply -3 lacks blob objects; switching to git merge-file fallback")
            return _merge_file_fallback(diff, target, base_snapshot, upstream_snapshot, git_executable, git_env)

        if stderr:
            logger.warning(f"3-way merge had conflicts:\n{stderr.strip()}")
        # Fall back to --reject for conflict files
        try:
            subprocess.run(  # nosec B603  # noqa: S603
                [git_executable, "apply", "--reject"],
                input=diff.encode(),
                cwd=target,
                check=True,
                capture_output=True,
                env=git_env,
            )
        except subprocess.CalledProcessError as e2:
            stderr2 = e2.stderr.decode() if e2.stderr else ""
            if stderr2:
                logger.warning(stderr2.strip())
            logger.warning(
                "Some changes could not be applied cleanly. Check for *.rej files and resolve conflicts manually."
            )
        return False
    else:
        return True


# ---------------------------------------------------------------------------
# Strategy implementations
# ---------------------------------------------------------------------------


def _copy_files_to_target(snapshot_dir: Path, target: Path, materialized: list[Path]) -> None:
    """Copy all materialized files from a snapshot into the target project.

    Args:
        snapshot_dir: Directory containing the snapshot files.
        target: Path to the target repository.
        materialized: List of relative file paths to copy.
    """
    for rel_path in sorted(materialized):
        src = snapshot_dir / rel_path
        dst = target / rel_path
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        logger.success(f"[COPY] {rel_path}")


def _sync_diff(target: Path, upstream_snapshot: Path) -> None:
    """Execute the diff (dry-run) strategy.

    Shows what would change without modifying any files.

    Args:
        target: Path to the target repository.
        upstream_snapshot: Path to the upstream snapshot directory.
    """
    diff = _get_diff(target, upstream_snapshot)
    if diff.strip():
        logger.info(f"\n{diff}")
        changes = diff.count("diff --git")
        logger.info(f"{changes} file(s) would be changed")
    else:
        logger.success("No differences found")


def _sync_merge(
    target: Path,
    upstream_snapshot: Path,
    upstream_sha: str,
    base_sha: str | None,
    materialized: list[Path],
    include_paths: list[str],
    excludes: set[str],
    git_url: str,
    git_executable: str,
    git_env: dict[str, str],
    rhiza_repo: str,
    rhiza_branch: str,
    lock: TemplateLock,
) -> None:
    """Execute the merge strategy (cruft-style 3-way merge).

    When a base SHA exists, computes the diff between base and upstream
    snapshots and applies it via ``git apply -3``.  On first sync (no base),
    falls back to a simple copy.

    Args:
        target: Path to the target repository.
        upstream_snapshot: Path to the upstream snapshot directory.
        upstream_sha: HEAD SHA of the upstream template.
        base_sha: Previously synced commit SHA, or None for first sync.
        materialized: List of relative file paths.
        include_paths: Paths to include from the template.
        excludes: Set of relative paths to exclude.
        git_url: Remote URL of the template repository.
        git_executable: Absolute path to git.
        git_env: Environment variables for git commands.
        rhiza_repo: Template repository name.
        rhiza_branch: Template branch name.
        lock: Pre-built :class:`~rhiza.models.TemplateLock` for this sync.
    """
    # Snapshot the currently-tracked files before the merge runs.  The merge
    # may write a new lock (e.g. on the "template unchanged" early-return path
    # in _merge_with_base), so we must read the old state first to ensure
    # orphan cleanup compares against the previous sync, not the new one.
    old_tracked_files = _read_previously_tracked_files(target)

    base_snapshot = Path(tempfile.mkdtemp())
    try:
        if base_sha:
            _merge_with_base(
                target,
                upstream_snapshot,
                upstream_sha,
                base_sha,
                base_snapshot,
                include_paths,
                excludes,
                git_url,
                git_executable,
                git_env,
                lock,
            )
        else:
            logger.info("First sync — copying all template files")
            _copy_files_to_target(upstream_snapshot, target, materialized)

        _warn_about_workflow_files(materialized)
        _clean_orphaned_files(
            target,
            materialized,
            excludes=excludes,
            base_snapshot=base_snapshot,
            previously_tracked_files=old_tracked_files if old_tracked_files else None,
        )
        _write_lock(target, lock)
        logger.success(f"Sync complete — {len(materialized)} file(s) processed")
    finally:
        if base_snapshot.exists():
            shutil.rmtree(base_snapshot)


def _merge_with_base(
    target: Path,
    upstream_snapshot: Path,
    upstream_sha: str,
    base_sha: str,
    base_snapshot: Path,
    include_paths: list[str],
    excludes: set[str],
    git_url: str,
    git_executable: str,
    git_env: dict[str, str],
    lock: TemplateLock,
) -> None:
    """Compute and apply the diff between base and upstream snapshots.

    Args:
        target: Path to the target repository.
        upstream_snapshot: Path to the upstream snapshot directory.
        upstream_sha: HEAD SHA of the upstream template.
        base_sha: Previously synced commit SHA.
        base_snapshot: Directory to populate with the base snapshot.
        include_paths: Paths to include from the template.
        excludes: Set of relative paths to exclude.
        git_url: Remote URL of the template repository.
        git_executable: Absolute path to git.
        git_env: Environment variables for git commands.
        lock: Pre-built :class:`~rhiza.models.TemplateLock` for this sync.
    """
    logger.info(f"Cloning base snapshot at {base_sha[:12]}")
    base_clone = Path(tempfile.mkdtemp())
    try:
        _clone_at_sha(git_url, base_sha, base_clone, include_paths, git_executable, git_env)
        _prepare_snapshot(base_clone, include_paths, excludes, base_snapshot)
    except Exception:
        logger.warning("Could not checkout base commit — treating all files as new")
    finally:
        if base_clone.exists():
            shutil.rmtree(base_clone)

    diff = _get_diff(base_snapshot, upstream_snapshot)

    if not diff.strip():
        logger.success("Template unchanged since last sync — nothing to apply")
        _write_lock(target, lock)
        return

    logger.info("Applying template changes via 3-way merge (cruft)...")
    clean = _apply_diff(
        diff, target, git_executable, git_env, base_snapshot=base_snapshot, upstream_snapshot=upstream_snapshot
    )

    if clean:
        logger.success("All changes applied cleanly")
    else:
        logger.warning("Some changes had conflicts. Check for *.rej files and resolve manually.")


# ---------------------------------------------------------------------------
# Upstream clone and resolution
# ---------------------------------------------------------------------------


def _clone_and_resolve_upstream(
    template: RhizaTemplate,
    git_url: str,
    rhiza_branch: str,
    include_paths: list[str],
    git_executable: str,
    git_env: dict[str, str],
) -> tuple[Path, str, list[str]]:
    """Clone the upstream template repository and resolve bundle paths.

    Args:
        template: The loaded RhizaTemplate configuration.
        git_url: Remote URL of the template repository.
        rhiza_branch: Branch to clone.
        include_paths: Initial include paths from template config.
        git_executable: Absolute path to git.
        git_env: Environment variables for git commands.

    Returns:
        Tuple of (upstream_dir, upstream_sha, resolved_include_paths).
    """
    upstream_dir = Path(tempfile.mkdtemp())

    initial_paths = [".rhiza"] if template.templates else include_paths
    _clone_template_repository(upstream_dir, git_url, rhiza_branch, initial_paths, git_executable, git_env)

    if template.templates:
        bundles_config = load_bundles_from_clone(upstream_dir)
        resolved_paths = resolve_include_paths(template, bundles_config)
        _update_sparse_checkout(upstream_dir, resolved_paths, git_executable, git_env)
        include_paths = resolved_paths

    upstream_sha = _get_head_sha(upstream_dir, git_executable, git_env)
    logger.info(f"Upstream HEAD: {upstream_sha[:12]}")

    return upstream_dir, upstream_sha, include_paths
