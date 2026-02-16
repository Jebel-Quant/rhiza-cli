"""Command for syncing Rhiza template files using diff/merge.

This module implements the ``sync`` command. Unlike ``materialize --force``
which overwrites files, ``sync`` uses cruft's diff/patch approach so that
local customisations are preserved and upstream changes are applied safely.

The approach:
1. Read the last-synced commit SHA from ``.rhiza/template.lock``.
2. Clone the template repository and obtain two tree snapshots:
   - **base**: the template at the previously synced commit (the common ancestor).
   - **upstream**: the template at the current HEAD of the configured branch.
3. Compute a diff between base and upstream using ``git diff --no-index``
   (via ``cruft._commands.utils.diff.get_diff``).
4. Apply the diff to the project using ``git apply -3`` for a 3-way merge.
5. Update the lock file.

When no lock file exists (first sync), the command falls back to a simple
copy (equivalent to ``materialize --force``) and records the commit SHA.
"""

import os
import shutil
import subprocess  # nosec B404
import sys
import tempfile
from pathlib import Path

from cruft._commands.utils.diff import get_diff
from loguru import logger

from rhiza.bundle_resolver import load_bundles_from_clone, resolve_include_paths
from rhiza.commands.materialize import (
    _clone_template_repository,
    _construct_git_url,
    _handle_target_branch,
    _log_git_stderr_errors,
    _update_sparse_checkout,
    _validate_and_load_template,
    _warn_about_workflow_files,
    _write_history_file,
)
from rhiza.subprocess_utils import get_git_executable

# ---------------------------------------------------------------------------
# Lock-file helpers
# ---------------------------------------------------------------------------

LOCK_FILE = ".rhiza/template.lock"


def _read_lock(target: Path) -> str | None:
    """Read the last-synced commit SHA from the lock file.

    Args:
        target: Path to the target repository.

    Returns:
        The commit SHA string or ``None`` when no lock exists.
    """
    lock_path = target / LOCK_FILE
    if not lock_path.exists():
        return None
    return lock_path.read_text(encoding="utf-8").strip()


def _write_lock(target: Path, sha: str) -> None:
    """Persist the synced commit SHA to the lock file.

    Args:
        target: Path to the target repository.
        sha: The commit SHA to record.
    """
    lock_path = target / LOCK_FILE
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(sha + "\n", encoding="utf-8")
    logger.info(f"Updated {LOCK_FILE} → {sha[:12]}")


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
        sys.exit(1)

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
        sys.exit(1)

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
        sys.exit(1)


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
# Main entry point
# ---------------------------------------------------------------------------


def sync(
    target: Path,
    branch: str,
    target_branch: str | None,
    strategy: str,
) -> None:
    """Sync Rhiza templates using cruft-style diff/merge instead of overwrite.

    Uses ``cruft``'s diff utilities to compute the diff between the base
    (last-synced) and upstream (latest) template snapshots, then applies
    the diff to the project using ``git apply -3`` for a 3-way merge.

    Args:
        target: Path to the target repository.
        branch: The Rhiza template branch to use.
        target_branch: Optional branch name to create/checkout in the target.
        strategy: Sync strategy — ``"merge"`` for 3-way merge,
            ``"overwrite"`` for traditional overwrite (same as materialize --force),
            ``"diff"`` for dry-run showing what would change.
    """
    target = target.resolve()
    logger.info(f"Target repository: {target}")
    logger.info(f"Rhiza branch: {branch}")
    logger.info(f"Sync strategy: {strategy}")

    git_executable = get_git_executable()
    git_env = os.environ.copy()
    git_env["GIT_TERMINAL_PROMPT"] = "0"

    # Handle target branch if specified
    _handle_target_branch(target, target_branch, git_executable, git_env)

    # Validate and load template configuration
    template, rhiza_repo, rhiza_branch, include_paths, excluded_paths = _validate_and_load_template(target, branch)
    rhiza_host = template.template_host or "github"
    git_url = _construct_git_url(rhiza_repo, rhiza_host)

    # --- Clone upstream (latest) ---
    upstream_dir = Path(tempfile.mkdtemp())
    logger.info(f"Cloning {rhiza_repo}@{rhiza_branch} (upstream)")

    try:
        initial_paths = [".rhiza"] if template.templates else include_paths
        _clone_template_repository(upstream_dir, git_url, rhiza_branch, initial_paths, git_executable, git_env)

        # Resolve bundles if needed
        if template.templates:
            bundles_config = load_bundles_from_clone(upstream_dir)
            resolved_paths = resolve_include_paths(template, bundles_config)
            _update_sparse_checkout(upstream_dir, resolved_paths, git_executable, git_env)
            include_paths = resolved_paths

        upstream_sha = _get_head_sha(upstream_dir, git_executable, git_env)
        logger.info(f"Upstream HEAD: {upstream_sha[:12]}")

        # --- Determine base SHA ---
        base_sha = _read_lock(target)

        if base_sha == upstream_sha:
            logger.success("Already up to date — nothing to sync")
            return

        # --- Build excluded set ---
        excludes = _excluded_set(upstream_dir, excluded_paths)

        # --- Create upstream snapshot ---
        upstream_snapshot = Path(tempfile.mkdtemp())
        try:
            materialized = _prepare_snapshot(upstream_dir, include_paths, excludes, upstream_snapshot)
            logger.info(f"Upstream: {len(materialized)} file(s) to consider")

            # ------------------------------------------------------------------
            # Strategy: diff (dry-run) — uses cruft's get_diff
            # ------------------------------------------------------------------
            if strategy == "diff":
                diff = get_diff(target, upstream_snapshot)
                if diff.strip():
                    logger.info(f"\n{diff}")
                    # Count changed files from diff headers
                    changes = diff.count("\ndiff --git")
                    if not diff.startswith("diff --git"):
                        changes += 0
                    else:
                        changes += 1
                    logger.info(f"{changes} file(s) would be changed")
                else:
                    logger.success("No differences found")
                return

            # ------------------------------------------------------------------
            # Strategy: overwrite  (same as materialize --force)
            # ------------------------------------------------------------------
            if strategy == "overwrite":
                for rel_path in sorted(materialized):
                    src = upstream_snapshot / rel_path
                    dst = target / rel_path
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
                    logger.success(f"[COPY] {rel_path}")

                _warn_about_workflow_files(materialized)
                _write_history_file(target, materialized, rhiza_repo, rhiza_branch)
                _write_lock(target, upstream_sha)
                logger.success("Sync complete (overwrite strategy)")
                return

            # ------------------------------------------------------------------
            # Strategy: merge (default — cruft-style 3-way merge)
            # ------------------------------------------------------------------
            base_snapshot = Path(tempfile.mkdtemp())
            try:
                if base_sha:
                    # Clone the base version for comparison
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

                    # Use cruft's get_diff to compute the diff between base and upstream
                    diff = get_diff(base_snapshot, upstream_snapshot)

                    if not diff.strip():
                        logger.success("Template unchanged since last sync — nothing to apply")
                        _write_lock(target, upstream_sha)
                        return

                    logger.info("Applying template changes via 3-way merge (cruft)...")
                    clean = _apply_diff(diff, target, git_executable, git_env)

                    if clean:
                        logger.success("All changes applied cleanly")
                    else:
                        logger.warning("Some changes had conflicts. Check for *.rej files and resolve manually.")
                else:
                    # No base — first sync, copy all files
                    logger.info("First sync — copying all template files")
                    for rel_path in sorted(materialized):
                        src = upstream_snapshot / rel_path
                        dst = target / rel_path
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(src, dst)
                        logger.success(f"[COPY] {rel_path}")

                _warn_about_workflow_files(materialized)
                _write_history_file(target, materialized, rhiza_repo, rhiza_branch)
                _write_lock(target, upstream_sha)
                logger.success(f"Sync complete — {len(materialized)} file(s) processed")

            finally:
                if base_snapshot.exists():
                    shutil.rmtree(base_snapshot)

        finally:
            if upstream_snapshot.exists():
                shutil.rmtree(upstream_snapshot)

    finally:
        if upstream_dir.exists():
            shutil.rmtree(upstream_dir)
