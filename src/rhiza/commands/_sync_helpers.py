"""Internal helpers for the ``sync`` command.

This module exposes the private implementation functions used by
:mod:`rhiza.commands.sync`.  Placing them here gives tests a stable import
path (``from rhiza.commands._sync_helpers import ...``) without coupling them
to the command module's public API.
"""

import contextlib
import dataclasses
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

from rhiza.models import RhizaTemplate, TemplateLock
from rhiza.models._git_utils import GitContext, _log_git_stderr_errors

# ---------------------------------------------------------------------------
# Diff prefix constants
# ---------------------------------------------------------------------------

_DIFF_SRC_PREFIX = "upstream-template-old"
_DIFF_DST_PREFIX = "upstream-template-new"

# ---------------------------------------------------------------------------
# Lock-file constant
# ---------------------------------------------------------------------------

LOCK_FILE = ".rhiza/template.lock"


def _get_diff(repo0: Path, repo1: Path, git_ctx: GitContext) -> str:
    """Compute the raw diff between two directory trees using ``git diff --no-index``.

    Args:
        repo0: Path to the base (old) directory tree.
        repo1: Path to the upstream (new) directory tree.
        git_ctx: :class:`~rhiza.models.GitContext` supplying the git executable
            and environment to use.  Accepting an explicit context (rather than
            resolving the executable internally) keeps this function consistent
            with all other git-invoking helpers in this module and allows tests
            to inject a custom binary without patching globals.
    """
    repo0_str = repo0.resolve().as_posix()
    repo1_str = repo1.resolve().as_posix()
    result = subprocess.run(  # nosec B603  # noqa: S603
        [
            git_ctx.executable,
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
        env=git_ctx.env,
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


def _assert_git_status_clean(target: Path, git_ctx: GitContext) -> None:
    """Raise RuntimeError if the target repository has uncommitted changes.

    Runs ``git status --porcelain`` and raises if the output is non-empty,
    preventing a sync from running on a dirty working tree.

    Args:
        target: Path to the target repository.
        git_ctx: Git context.

    Raises:
        RuntimeError: If the working tree has uncommitted changes.
    """
    result = subprocess.run(  # nosec B603  # noqa: S603
        [git_ctx.executable, "status", "--porcelain"],
        cwd=target,
        capture_output=True,
        text=True,
        env=git_ctx.env,
    )
    if result.stdout.strip():
        logger.error("Working tree is not clean. Please commit or stash your changes before syncing.")
        logger.error("Uncommitted changes:")
        for line in result.stdout.strip().splitlines():
            logger.error(f"  {line}")
        raise RuntimeError("Working tree is not clean. Please commit or stash your changes before syncing.")  # noqa: TRY003


def _handle_target_branch(target: Path, target_branch: str | None, git_ctx: GitContext) -> None:
    """Handle target branch creation or checkout if specified.

    Args:
        target: Path to the target repository.
        target_branch: Optional branch name to create/checkout.
        git_ctx: Git context.
    """
    if not target_branch:
        return

    logger.info(f"Creating/checking out target branch: {target_branch}")
    try:
        result = subprocess.run(  # nosec B603  # noqa: S603
            [git_ctx.executable, "rev-parse", "--verify", target_branch],
            cwd=target,
            capture_output=True,
            text=True,
            env=git_ctx.env,
        )

        if result.returncode == 0:
            logger.info(f"Branch '{target_branch}' exists, checking out...")
            subprocess.run(  # nosec B603  # noqa: S603
                [git_ctx.executable, "checkout", target_branch],
                cwd=target,
                check=True,
                capture_output=True,
                text=True,
                env=git_ctx.env,
            )
        else:
            logger.info(f"Creating new branch '{target_branch}'...")
            subprocess.run(  # nosec B603  # noqa: S603
                [git_ctx.executable, "checkout", "-b", target_branch],
                cwd=target,
                check=True,
                capture_output=True,
                text=True,
                env=git_ctx.env,
            )
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to create/checkout branch '{target_branch}'")
        _log_git_stderr_errors(e.stderr)
        logger.error("Please ensure you have no uncommitted changes or conflicts")
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
    git_ctx: GitContext,
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
        git_ctx: Git context.

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
                git_ctx.executable,
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
            env=git_ctx.env,
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
    git_ctx: GitContext,
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
        git_ctx: Git context.
        base_snapshot: Optional directory containing files at the base SHA.
        upstream_snapshot: Optional directory containing files at the upstream SHA.

    Returns:
        True if the diff applied cleanly, False if there were conflicts.
    """
    if not diff.strip():
        return True

    try:
        subprocess.run(  # nosec B603  # noqa: S603
            [git_ctx.executable, "apply", "-3"],
            input=diff.encode(),
            cwd=target,
            check=True,
            capture_output=True,
            env=git_ctx.env,
        )
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode() if e.stderr else ""

        # git apply -3 cannot do a real 3-way merge when the template blobs are
        # not present in the target repository's object store.  If we have the
        # snapshot directories on disk, use git merge-file instead — it works
        # directly on file content and needs no shared git history.
        if "lacks the necessary blob" in stderr and base_snapshot is not None and upstream_snapshot is not None:
            logger.debug("git apply -3 lacks blob objects; switching to git merge-file fallback")
            return _merge_file_fallback(diff, target, base_snapshot, upstream_snapshot, git_ctx)

        if stderr:
            logger.warning(f"3-way merge had conflicts:\n{stderr.strip()}")
        # Fall back to --reject for conflict files
        try:
            subprocess.run(  # nosec B603  # noqa: S603
                [git_ctx.executable, "apply", "--reject"],
                input=diff.encode(),
                cwd=target,
                check=True,
                capture_output=True,
                env=git_ctx.env,
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


def _sync_diff(target: Path, upstream_snapshot: Path, git_ctx: GitContext) -> None:
    """Execute the diff (dry-run) strategy.

    Shows what would change without modifying any files.

    Args:
        target: Path to the target repository.
        upstream_snapshot: Path to the upstream snapshot directory.
        git_ctx: :class:`~rhiza.models.GitContext` supplying the git executable
            and environment for the underlying diff invocation.
    """
    diff = _get_diff(target, upstream_snapshot, git_ctx)
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
    template: "RhizaTemplate",
    excludes: set[str],
    git_ctx: GitContext,
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
        template: The :class:`~rhiza.models.RhizaTemplate` driving this sync.
        excludes: Set of relative paths to exclude.
        git_ctx: Git context.
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
                template,
                excludes,
                git_ctx,
                lock,
            )
        else:
            logger.info("First sync — copying all template files")
            _copy_files_to_target(upstream_snapshot, target, materialized)

        # Restore any template-managed files that are absent from the target.
        # This can happen when files tracked by the template do not exist in the
        # downstream repository — for example when the template snapshot was
        # unchanged since the last sync so no diff was applied, but the files
        # were never present or were manually deleted.
        missing_from_target = [p for p in materialized if not (target / p).exists()]
        if missing_from_target:
            logger.info(f"Restoring {len(missing_from_target)} template file(s) missing from target")
            _copy_files_to_target(upstream_snapshot, target, missing_from_target)

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
    template: "RhizaTemplate",
    excludes: set[str],
    git_ctx: GitContext,
    lock: TemplateLock,
) -> None:
    """Compute and apply the diff between base and upstream snapshots.

    Args:
        target: Path to the target repository.
        upstream_snapshot: Path to the upstream snapshot directory.
        upstream_sha: HEAD SHA of the upstream template.
        base_sha: Previously synced commit SHA.
        base_snapshot: Directory to populate with the base snapshot.
        template: The :class:`~rhiza.models.RhizaTemplate` driving this sync.
        excludes: Set of relative paths to exclude.
        git_ctx: Git context.
        lock: Pre-built :class:`~rhiza.models.TemplateLock` for this sync.
    """
    logger.info(f"Cloning base snapshot at {base_sha[:12]}")
    base_clone = Path(tempfile.mkdtemp())
    try:
        template._clone_at_sha(base_sha, base_clone, template.include, git_ctx)
        RhizaTemplate._prepare_snapshot(base_clone, template.include, excludes, base_snapshot)
    except Exception:
        logger.warning("Could not checkout base commit — treating all files as new")
    finally:
        if base_clone.exists():
            shutil.rmtree(base_clone)

    diff = _get_diff(base_snapshot, upstream_snapshot, git_ctx)

    if not diff.strip():
        logger.success("Template unchanged since last sync — nothing to apply")
        _write_lock(target, lock)
        return

    logger.info("Applying template changes via 3-way merge (cruft)...")
    clean = _apply_diff(diff, target, git_ctx, base_snapshot=base_snapshot, upstream_snapshot=upstream_snapshot)

    if clean:
        logger.success("All changes applied cleanly")
    else:
        logger.warning("Some changes had conflicts. Check for *.rej files and resolve manually.")
