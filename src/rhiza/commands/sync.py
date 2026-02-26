"""Command for syncing Rhiza template files using diff/merge.

This module implements the ``sync`` command. It uses a cruft-style diff/patch
approach so that local customisations are preserved and upstream changes
are applied safely.

The approach:
1. Read the last-synced commit SHA from ``.rhiza/template.lock``.
2. Clone the template repository and obtain two tree snapshots:
   - **base**: the template at the previously synced commit (the common ancestor).
   - **upstream**: the template at the current HEAD of the configured branch.
3. Compute a diff between base and upstream using ``git diff --no-index``.
4. Apply the diff to the project using ``git apply -3`` for a 3-way merge.
5. Update the lock file.

When no lock file exists (first sync), the command falls back to a simple
copy and records the commit SHA.
"""

import datetime
import os
import shutil
import subprocess  # nosec B404
import tempfile
from pathlib import Path
from re import sub

import yaml
from loguru import logger

from rhiza.bundle_resolver import load_bundles_from_clone, resolve_include_paths
from rhiza.commands.validate import validate
from rhiza.models import RhizaTemplate, TemplateLock
from rhiza.subprocess_utils import get_git_executable

_DIFF_SRC_PREFIX = "upstream-template-old"
_DIFF_DST_PREFIX = "upstream-template-new"


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
# Shared template helpers (canonical home for helpers used by sync)
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


def _read_previously_tracked_files(target: Path) -> set[Path]:
    """Return the set of files tracked by the last sync.

    Prefers ``template.lock.files`` and falls back to legacy ``.rhiza/history``
    and ``.rhiza.history`` files for backward compatibility.

    Args:
        target: Target repository path.

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
        except Exception as e:
            logger.debug(f"Could not read template.lock for orphan cleanup: {e}")

    new_history_file = target / ".rhiza" / "history"
    old_history_file = target / ".rhiza.history"

    if new_history_file.exists():
        history_file = new_history_file
        logger.debug(f"Reading existing history file from new location: {history_file.relative_to(target)}")
    elif old_history_file.exists():
        history_file = old_history_file
        logger.debug(f"Reading existing history file from old location: {history_file.relative_to(target)}")
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


def _clean_orphaned_files(target: Path, materialized_files: list[Path]) -> None:
    """Clean up files that are no longer maintained by template.

    Args:
        target: Target repository path.
        materialized_files: List of currently materialized files.
    """
    previously_tracked_files = _read_previously_tracked_files(target)
    if not previously_tracked_files:
        return

    logger.debug(f"Found {len(previously_tracked_files)} file(s) in previous tracking")

    orphaned_files = previously_tracked_files - set(materialized_files)

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

LOCK_FILE = ".rhiza/template.lock"


def _read_lock(target: Path) -> str | None:
    """Read the last-synced commit SHA from the lock file.

    Handles both the structured YAML format and the legacy plain-SHA format.

    Args:
        target: Path to the target repository.

    Returns:
        The commit SHA string or ``None`` when no lock exists.
    """
    lock_path = target / LOCK_FILE
    if not lock_path.exists():
        return None
    content = lock_path.read_text(encoding="utf-8").strip()
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
    """Persist the commit SHA to the lock file.

    Writes the plain-SHA format for backward compatibility with rhiza 0.11.3
    and earlier, whose ``_read_lock`` reads the file as a raw string.

    Args:
        target: Path to the target repository.
        lock: The :class:`~rhiza.models.TemplateLock` to record.
    """
    lock_path = target / LOCK_FILE
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(lock.sha + "\n", encoding="utf-8")
    logger.info(f"Updated {LOCK_FILE} → {lock.sha[:12]}")


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


def _apply_diff(diff: str, target: Path, git_executable: str, git_env: dict[str, str]) -> bool:
    """Apply a diff to the target project using ``git apply -3`` (3-way merge).

    Falls back to ``git apply --reject`` if the target is not a git repository.

    Args:
        diff: Unified diff string.
        target: Path to the target repository.
        git_executable: Absolute path to git.
        git_env: Environment variables for git commands.

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
        _clean_orphaned_files(target, materialized)
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
    clean = _apply_diff(diff, target, git_executable, git_env)

    if clean:
        logger.success("All changes applied cleanly")
    else:
        logger.warning("Some changes had conflicts. Check for *.rej files and resolve manually.")


# ---------------------------------------------------------------------------
# Upstream clone and resolution
# ---------------------------------------------------------------------------


def _clone_and_resolve_upstream(
    template,
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


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def sync(
    target: Path,
    branch: str,
    target_branch: str | None,
    strategy: str,
) -> None:
    """Sync Rhiza templates using cruft-style diff/merge.

    Uses ``cruft``'s diff utilities to compute the diff between the base
    (last-synced) and upstream (latest) template snapshots, then applies
    the diff to the project using ``git apply -3`` for a 3-way merge.

    Args:
        target: Path to the target repository.
        branch: The Rhiza template branch to use.
        target_branch: Optional branch name to create/checkout in the target.
        strategy: Sync strategy — ``"merge"`` for 3-way merge,
            or ``"diff"`` for dry-run showing what would change.
    """
    target = target.resolve()
    logger.info(f"Target repository: {target}")
    logger.info(f"Rhiza branch: {branch}")
    logger.info(f"Sync strategy: {strategy}")

    git_executable = get_git_executable()
    git_env = os.environ.copy()
    git_env["GIT_TERMINAL_PROMPT"] = "0"

    _handle_target_branch(target, target_branch, git_executable, git_env)

    template, rhiza_repo, rhiza_branch, include_paths, excluded_paths = _validate_and_load_template(target, branch)
    rhiza_host = template.template_host or "github"
    git_url = _construct_git_url(rhiza_repo, rhiza_host)

    logger.info(f"Cloning {rhiza_repo}@{rhiza_branch} (upstream)")
    upstream_dir, upstream_sha, include_paths = _clone_and_resolve_upstream(
        template,
        git_url,
        rhiza_branch,
        include_paths,
        git_executable,
        git_env,
    )

    try:
        base_sha = _read_lock(target)
        if base_sha == upstream_sha:
            logger.success("Already up to date — nothing to sync")
            return

        excludes = _excluded_set(upstream_dir, excluded_paths)

        upstream_snapshot = Path(tempfile.mkdtemp())
        try:
            materialized = _prepare_snapshot(upstream_dir, include_paths, excludes, upstream_snapshot)
            logger.info(f"Upstream: {len(materialized)} file(s) to consider")

            lock = TemplateLock(
                sha=upstream_sha,
                repo=rhiza_repo,
                host=rhiza_host,
                ref=rhiza_branch,
                include=template.include,
                exclude=excluded_paths,
                templates=template.templates,
                synced_at=datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                strategy=strategy,
            )

            if strategy == "diff":
                _sync_diff(target, upstream_snapshot)
            else:
                _sync_merge(
                    target,
                    upstream_snapshot,
                    upstream_sha,
                    base_sha,
                    materialized,
                    include_paths,
                    excludes,
                    git_url,
                    git_executable,
                    git_env,
                    rhiza_repo,
                    rhiza_branch,
                    lock,
                )
        finally:
            if upstream_snapshot.exists():
                shutil.rmtree(upstream_snapshot)
    finally:
        if upstream_dir.exists():
            shutil.rmtree(upstream_dir)
