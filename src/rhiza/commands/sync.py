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
import tempfile
from pathlib import Path

from loguru import logger

from rhiza._sync_helpers import (
    LOCK_FILE,
    _clone_and_resolve_upstream,
    _construct_git_url,
    _excluded_set,
    _handle_target_branch,
    _prepare_snapshot,
    _read_lock,
    _sync_diff,
    _sync_merge,
    _validate_and_load_template,
)
from rhiza.models import TemplateLock
from rhiza.subprocess_utils import get_git_executable

__all__ = ["LOCK_FILE", "sync"]


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
        strategy: Sync strategy -- ``"merge"`` for 3-way merge,
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
            logger.success("Already up to date -- nothing to sync")
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
                files=[str(p) for p in materialized],
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
