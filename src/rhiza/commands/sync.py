"""Command for syncing Rhiza template files using diff/merge.

This module implements the ``sync`` command. Unlike ``materialize --force``
which overwrites files, ``sync`` uses a 3-way merge approach (inspired by
cruft) so that local customisations are preserved and upstream changes are
applied safely.

The approach:
1. Read the last-synced commit SHA from ``.rhiza/template.lock``.
2. Clone the template repository and obtain two tree snapshots:
   - **base**: the template at the previously synced commit (the common ancestor).
   - **upstream**: the template at the current HEAD of the configured branch.
3. For every managed file, perform a 3-way merge:
   ``base → upstream`` (template changes) merged with ``base → local`` (user changes).
4. Write the result and update the lock file.

When no lock file exists (first sync), the command falls back to a simple
copy (equivalent to ``materialize --force``) and records the commit SHA.
"""

import os
import shutil
import subprocess  # nosec B404
import sys
import tempfile
from pathlib import Path

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
# 3-way merge
# ---------------------------------------------------------------------------


def _merge_file(
    base_content: str | None,
    upstream_content: str,
    local_content: str | None,
    rel_path: str,
    git_executable: str,
    git_env: dict[str, str],
) -> tuple[str, bool]:
    """Perform a 3-way merge on a single file using ``git merge-file``.

    Args:
        base_content: Content of the file at the base (last-synced) commit.
            ``None`` when the file is new in the template.
        upstream_content: Content from the latest template version.
        local_content: Current content in the user's project.
            ``None`` when the file does not exist locally.
        rel_path: Relative path (used for labelling conflict markers).
        git_executable: Absolute path to git.
        git_env: Environment variables for git commands.

    Returns:
        Tuple of (merged content, had_conflicts).
    """
    # If there's no local file, the upstream content wins
    if local_content is None:
        return upstream_content, False

    # If there's no base, treat as new file with conflict on difference
    if base_content is None:
        if local_content == upstream_content:
            return upstream_content, False
        # No common ancestor — use upstream as base for a best-effort merge
        base_content = ""

    # Write the three versions to temp files
    tmp_dir = Path(tempfile.mkdtemp())
    try:
        base_file = tmp_dir / "base"
        upstream_file = tmp_dir / "upstream"
        local_file = tmp_dir / "local"

        base_file.write_text(base_content, encoding="utf-8")
        upstream_file.write_text(upstream_content, encoding="utf-8")
        local_file.write_text(local_content, encoding="utf-8")

        # git merge-file writes merged output into the first file
        # Returns 0 on clean merge, >0 on conflicts, <0 on error
        result = subprocess.run(  # nosec B603  # noqa: S603
            [
                git_executable,
                "merge-file",
                "-L",
                f"local ({rel_path})",
                "-L",
                f"base ({rel_path})",
                "-L",
                f"upstream ({rel_path})",
                str(local_file),
                str(base_file),
                str(upstream_file),
            ],
            capture_output=True,
            text=True,
            env=git_env,
        )

        merged = local_file.read_text(encoding="utf-8")
        had_conflicts = result.returncode > 0
        return merged, had_conflicts
    finally:
        shutil.rmtree(tmp_dir)


# ---------------------------------------------------------------------------
# Diff-only (dry-run)
# ---------------------------------------------------------------------------


def _diff_file(
    upstream_content: str,
    local_content: str | None,
    rel_path: str,
) -> str | None:
    """Return a unified diff between local and upstream, or ``None`` if equal.

    Args:
        upstream_content: Template content.
        local_content: Local file content (or ``None``).
        rel_path: Relative path for diff header.

    Returns:
        Diff string or ``None``.
    """
    import difflib

    if local_content is None:
        # New file
        diff_lines = list(
            difflib.unified_diff(
                [],
                upstream_content.splitlines(keepends=True),
                fromfile=f"a/{rel_path}",
                tofile=f"b/{rel_path}",
                lineterm="",
            )
        )
    else:
        diff_lines = list(
            difflib.unified_diff(
                local_content.splitlines(keepends=True),
                upstream_content.splitlines(keepends=True),
                fromfile=f"a/{rel_path}",
                tofile=f"b/{rel_path}",
                lineterm="",
            )
        )

    return "\n".join(diff_lines) if diff_lines else None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def sync(
    target: Path,
    branch: str,
    target_branch: str | None,
    strategy: str,
) -> None:
    """Sync Rhiza templates using diff/merge instead of overwrite.

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

        # --- Collect upstream files ---
        upstream_files: dict[str, str] = {}
        for f in _expand_paths(upstream_dir, include_paths):
            rel = str(f.relative_to(upstream_dir))
            if rel not in excludes:
                upstream_files[rel] = f.read_text(encoding="utf-8")

        logger.info(f"Upstream: {len(upstream_files)} file(s) to consider")

        # --- Clone base snapshot (if we have a previous SHA) ---
        base_files: dict[str, str] = {}
        base_dir: Path | None = None

        if base_sha:
            logger.info(f"Cloning base snapshot at {base_sha[:12]}")
            base_dir = Path(tempfile.mkdtemp())
            try:
                _clone_at_sha(git_url, base_sha, base_dir, include_paths, git_executable, git_env)
                for f in _expand_paths(base_dir, include_paths):
                    rel = str(f.relative_to(base_dir))
                    if rel not in excludes:
                        base_files[rel] = f.read_text(encoding="utf-8")
                logger.info(f"Base: {len(base_files)} file(s)")
            except Exception:
                logger.warning("Could not checkout base commit — falling back to no-base merge")
                base_files = {}
            finally:
                if base_dir and base_dir.exists():
                    shutil.rmtree(base_dir)

        # ------------------------------------------------------------------
        # Strategy: diff (dry-run)
        # ------------------------------------------------------------------
        if strategy == "diff":
            changes = 0
            for rel_path, upstream_content in sorted(upstream_files.items()):
                local_path = target / rel_path
                local_content = local_path.read_text(encoding="utf-8") if local_path.exists() else None
                diff = _diff_file(upstream_content, local_content, rel_path)
                if diff:
                    changes += 1
                    logger.info(f"\n{diff}")
            if changes == 0:
                logger.success("No differences found")
            else:
                logger.info(f"{changes} file(s) would be changed")
            # Update lock even in diff mode? No — diff is read-only.
            return

        # ------------------------------------------------------------------
        # Strategy: overwrite  (same as materialize --force)
        # ------------------------------------------------------------------
        materialized: list[Path] = []

        if strategy == "overwrite":
            for rel_path, content in sorted(upstream_files.items()):
                dst = target / rel_path
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_text(content, encoding="utf-8")
                materialized.append(Path(rel_path))
                logger.success(f"[COPY] {rel_path}")

            _warn_about_workflow_files(materialized)
            _write_history_file(target, materialized, rhiza_repo, rhiza_branch)
            _write_lock(target, upstream_sha)
            logger.success("Sync complete (overwrite strategy)")
            return

        # ------------------------------------------------------------------
        # Strategy: merge (default — 3-way merge)
        # ------------------------------------------------------------------
        conflicts: list[str] = []

        for rel_path, upstream_content in sorted(upstream_files.items()):
            local_path = target / rel_path
            local_content = local_path.read_text(encoding="utf-8") if local_path.exists() else None
            base_content = base_files.get(rel_path)

            # Skip if upstream and local are identical
            if local_content is not None and local_content == upstream_content:
                materialized.append(Path(rel_path))
                logger.debug(f"[SKIP] {rel_path} (unchanged)")
                continue

            # Skip if upstream hasn't changed since base (user change only)
            if base_content is not None and base_content == upstream_content:
                materialized.append(Path(rel_path))
                logger.debug(f"[KEEP] {rel_path} (local-only changes)")
                continue

            merged, had_conflicts = _merge_file(
                base_content,
                upstream_content,
                local_content,
                rel_path,
                git_executable,
                git_env,
            )

            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_text(merged, encoding="utf-8")
            materialized.append(Path(rel_path))

            if had_conflicts:
                conflicts.append(rel_path)
                logger.warning(f"[CONFLICT] {rel_path}")
            else:
                logger.success(f"[MERGE] {rel_path}")

        _warn_about_workflow_files(materialized)
        _write_history_file(target, materialized, rhiza_repo, rhiza_branch)
        _write_lock(target, upstream_sha)

        if conflicts:
            logger.warning(f"{len(conflicts)} file(s) have merge conflicts — resolve manually:")
            for c in conflicts:
                logger.warning(f"  {c}")
            logger.info(
                "Conflict markers use standard git format:\n"
                "  <<<<<<< local\n"
                "  ... your changes ...\n"
                "  =======\n"
                "  ... upstream changes ...\n"
                "  >>>>>>> upstream"
            )
        else:
            logger.success(f"Sync complete — {len(materialized)} file(s) merged cleanly")

    finally:
        if upstream_dir.exists():
            shutil.rmtree(upstream_dir)
