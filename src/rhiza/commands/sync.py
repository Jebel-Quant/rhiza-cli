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
from typing import cast

from loguru import logger

from rhiza.commands._sync_helpers import (
    LOCK_FILE,
    _assert_git_status_clean,
    _handle_target_branch,
    _read_lock,
    _sync_diff,
    _sync_merge,
)
from rhiza.models import RhizaTemplate, TemplateLock, get_git_executable

__all__ = ["LOCK_FILE", "sync"]


def sync(
    target: Path,
    branch: str,
    target_branch: str | None,
    strategy: str,
) -> None:
    """Sync Rhiza templates using cruft-style diff/merge.

    Uses diff utilities to compute the diff between the base
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

    _assert_git_status_clean(target, git_executable, git_env)
    _handle_target_branch(target, target_branch, git_executable, git_env)

    template = RhizaTemplate.from_project(target, branch)
    # from_project guarantees these are set; cast for type narrowing
    template.template_repository = cast(str, template.template_repository)
    template.template_branch = cast(str, template.template_branch)

    logger.info(f"Cloning {template.template_repository}@{template.template_branch} (upstream)")
    upstream_dir, upstream_sha = template.clone(git_executable, git_env, branch=branch)

    # Synchronizes target with upstream template snapshot transactionally; cleans up resources
    try:
        base_sha = _read_lock(target)

        upstream_snapshot = Path(tempfile.mkdtemp())
        try:
            materialized, excludes = template.snapshot(upstream_dir, upstream_snapshot)
            logger.info(f"Upstream: {len(materialized)} file(s) to consider")
            lock = TemplateLock(
                sha=upstream_sha,
                repo=template.template_repository,
                host=template.template_host,
                ref=template.template_branch,
                include=template.include,
                exclude=template.exclude,
                templates=template.templates,
                files=[str(p) for p in materialized],
                synced_at=datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                strategy=strategy,
            )

            if strategy == "diff":
                _sync_diff(target=target, upstream_snapshot=upstream_snapshot)
            else:
                _sync_merge(
                    target,
                    upstream_snapshot,
                    upstream_sha,
                    base_sha,
                    materialized,
                    template,
                    excludes,
                    git_executable,
                    git_env,
                    lock,
                )
        finally:
            if upstream_snapshot.exists():
                shutil.rmtree(upstream_snapshot)
    finally:
        if upstream_dir.exists():
            shutil.rmtree(upstream_dir)
