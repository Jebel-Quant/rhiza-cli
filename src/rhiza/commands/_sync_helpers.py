"""Internal helpers for the ``sync`` command.

This module exposes the private implementation functions used by
:mod:`rhiza.commands.sync`.  Placing them here gives tests a stable import
path (``from rhiza.commands._sync_helpers import ...``) without coupling them
to the command module's public API.

The lock-file persistence and orphan-cleanup helpers actually live in
:mod:`rhiza.models._git.lock_io` (the models layer drives them during the
merge); they are re-exported here so existing
``from rhiza.commands._sync_helpers import ...`` call sites keep working
without creating a ``models -> commands`` import cycle.
"""

from pathlib import Path

from loguru import logger

from rhiza.models import TemplateLock
from rhiza.models._git.lock_io import (
    _FCNTL_AVAILABLE,
    LOCK_FILE,
    _clean_orphaned_files,
    _delete_orphaned_file,
    _files_from_snapshot,
    _lock_content_unchanged,
    _read_previously_tracked_files,
    _warn_about_workflow_files,
    _write_lock,
)

__all__ = [
    "LOCK_FILE",
    "_FCNTL_AVAILABLE",
    "_clean_orphaned_files",
    "_delete_orphaned_file",
    "_files_from_snapshot",
    "_load_lock_or_warn",
    "_lock_content_unchanged",
    "_read_previously_tracked_files",
    "_warn_about_workflow_files",
    "_write_lock",
]


# Shared template helpers
# ---------------------------------------------------------------------------


def _load_lock_or_warn(target: Path, lock_file: Path | None = None) -> TemplateLock | None:
    """Load the template.lock file, or log a warning and return None if missing.

    Args:
        target: Path to the target repository root.
        lock_file: Optional explicit path to the lock file.  When ``None`` the
            default ``<target>/.rhiza/template.lock`` is used.

    Returns:
        The loaded :class:`~rhiza.models.TemplateLock`, or ``None`` when the
        lock file does not exist.
    """
    if lock_file is None:
        lock_file = target / LOCK_FILE
    lock_path = lock_file.resolve()
    if not lock_path.exists():
        logger.warning("No template.lock found — run `rhiza sync` first")
        return None
    return TemplateLock.from_yaml(lock_path)
