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
    "_lock_content_unchanged",
    "_read_previously_tracked_files",
    "_warn_about_workflow_files",
    "_write_lock",
]
