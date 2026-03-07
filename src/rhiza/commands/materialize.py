"""Backward-compatibility shim for the retired ``materialize`` command.

All shared helpers have moved to :mod:`rhiza.commands.sync`, which is the
canonical home for template-management logic. This module re-exports them for
any code that still imports directly from here, and provides a deprecated
:func:`materialize` wrapper that delegates to :func:`~rhiza.commands.sync.sync`.

The ``rhiza materialize`` CLI command is already marked deprecated and routes
to ``rhiza sync``. The Python-level :func:`materialize` function is retained
solely for backward compatibility and will be removed in a future release.
"""

import warnings

from rhiza.commands._sync_helpers import (
    _clean_orphaned_files,
    _clone_template_repository,
    _construct_git_url,
    _handle_target_branch,
    _log_git_stderr_errors,
    _update_sparse_checkout,
    _validate_and_load_template,
    _warn_about_workflow_files,
)
from rhiza.commands.sync import sync

__all__ = [
    "_clean_orphaned_files",
    "_clone_template_repository",
    "_construct_git_url",
    "_handle_target_branch",
    "_log_git_stderr_errors",
    "_update_sparse_checkout",
    "_validate_and_load_template",
    "_warn_about_workflow_files",
    "materialize",
    "sync",
]


def materialize(target, branch, target_branch, force):
    """[Deprecated] Materialize Rhiza templates — use :func:`~rhiza.commands.sync.sync` instead.

    This function is a backward-compatibility shim. The ``--force`` flag has no
    effect; the underlying :func:`~rhiza.commands.sync.sync` call always uses the
    ``"merge"`` strategy.

    Args:
        target: Path to the target repository.
        branch: The Rhiza template branch to use.
        target_branch: Optional branch name to create/checkout in the target.
        force: Ignored — kept for API compatibility only.
    """
    from pathlib import Path

    warnings.warn(
        "materialize() is deprecated and will be removed in a future release. Use sync() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    sync(Path(target), branch, target_branch, "merge")
