"""Internal helpers for the ``sync`` command.

This module exposes the private implementation functions used by
:mod:`rhiza.commands.sync`.  Placing them here gives tests a stable import
path (``from rhiza.commands._sync_helpers import ...``) without coupling them
to the command module's public API.
"""

import contextlib
import dataclasses
import os
from pathlib import Path

try:
    import fcntl

    _FCNTL_AVAILABLE = True
except ImportError:  # pragma: no cover - Windows
    _FCNTL_AVAILABLE = False

from loguru import logger

from rhiza.models import TemplateLock

# ---------------------------------------------------------------------------
# Lock-file constant
# ---------------------------------------------------------------------------

LOCK_FILE = ".rhiza/template.lock"


# Shared template helpers
# ---------------------------------------------------------------------------


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


def _write_lock(target: Path, lock: TemplateLock) -> None:
    """Persist the lock data to the YAML lock file.

    Writes to a ``.tmp`` sibling file first, then replaces the real lock file
    atomically with ``os.replace()``.  An exclusive advisory lock (via
    ``fcntl.flock``) is held for the entire write + rename sequence when
    ``fcntl`` is available so that concurrent writers do not corrupt the file.
    Falls back silently on platforms without ``fcntl`` (e.g. Windows).

    Only files that actually exist in *target* are recorded in ``lock.files``.
    This guarantees that the lock never references paths that are absent from
    the repository.

    Args:
        target: Path to the target repository.
        lock: The :class:`~rhiza.models.TemplateLock` to record.
    """
    # Filter the files list to only include paths that exist on disk so that
    # the lock never contains entries for files that are absent from the repo.
    existing_files = [f for f in lock.files if (target / f).exists()]
    missing = sorted(set(lock.files) - set(existing_files))
    if missing:
        missing_str = ", ".join(missing)
        logger.warning(f"{len(missing)} file(s) in lock absent from target and excluded: {missing_str}")
        lock = dataclasses.replace(lock, files=existing_files)

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
