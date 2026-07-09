"""The 3-way merge strategy: apply, fallback, conflict scanning, and lock update."""

import shutil
import subprocess  # nosec B404
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from rhiza.models._git import lock_io
from rhiza.models._git.diff import DiffMixin
from rhiza.models._git.remote import RemoteOpsMixin
from rhiza.models._git.snapshot import _prepare_snapshot

if TYPE_CHECKING:
    from rhiza.models.lock import TemplateLock
    from rhiza.models.template import RhizaTemplate


@dataclass(frozen=True)
class _MergePaths:
    """The three on-disk locations for a single file in a 3-way merge."""

    target: Path
    upstream: Path
    base: Path


class MergeMixin(RemoteOpsMixin, DiffMixin):
    """Apply template changes to the target via a cruft-style 3-way merge."""

    def _apply_non_merge(self, rel_path: str, paths: "_MergePaths", *, is_new: bool, is_deleted: bool) -> None:
        """Handle the non-3-way cases: additions, deletions, and overwrite-from-upstream."""
        if is_deleted:
            if paths.target.exists():
                paths.target.unlink()
                logger.debug(f"[merge-file] Deleted: {rel_path}")
            return

        # New, missing-in-target, or no-base: just take upstream when it exists.
        if paths.upstream.exists():
            target_existed = paths.target.exists()
            paths.target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(paths.upstream, paths.target)
            if is_new:
                logger.debug(f"[merge-file] Added: {rel_path}")
            elif not target_existed:
                logger.debug(f"[merge-file] Created (missing in target): {rel_path}")
            else:
                logger.debug(f"[merge-file] Overwrite (no base): {rel_path}")

    def _git_merge_file(self, rel_path: str, paths: "_MergePaths") -> tuple[bool, bool]:
        """Run ``git merge-file`` for one modified file.

        Returns:
            A ``(is_clean, is_conflict)`` tuple. ``is_clean`` is False on either
            a conflict or a merge error; ``is_conflict`` is True only when
            conflict markers were written and need manual resolution.
        """
        result = subprocess.run(  # nosec B603  # noqa: S603
            [
                self.executable,
                "merge-file",
                "-L",
                "HEAD",
                "-L",
                "base",
                "-L",
                "rhiza-template",
                str(paths.target),
                str(paths.base),
                str(paths.upstream),
            ],
            capture_output=True,
            env=self.env,
        )

        if result.returncode > 0:
            logger.warning(f"[merge-file] Conflict in {rel_path} — resolve markers manually")
            return False, True
        if result.returncode < 0:
            logger.warning(f"[merge-file] Error merging {rel_path}: {result.stderr.decode().strip()}")
            return False, False
        logger.debug(f"[merge-file] Clean merge: {rel_path}")
        return True, False

    def _merge_file_fallback(
        self,
        diff: str,
        target: Path,
        base_snapshot: Path,
        upstream_snapshot: Path,
    ) -> bool:
        """Apply *diff* file-by-file using ``git merge-file``.

        Unlike ``git apply -3``, ``git merge-file`` works directly on the file
        contents from *base_snapshot* and *upstream_snapshot*, so it does not
        require the template's blob objects to exist in the target repository.

        Conflict markers (``<<<<<<< HEAD`` / ``=======`` / ``>>>>>>> rhiza-template``) are left in
        place for manual resolution when both sides changed the same region.

        Args:
            diff: Unified diff string (used only for file-list parsing).
            target: Path to the target repository.
            base_snapshot: Directory containing files at the previously-synced SHA.
            upstream_snapshot: Directory containing files at the new upstream SHA.

        Returns:
            True if every file merged cleanly, False if any conflicts remain.
        """
        file_entries = self._parse_diff_filenames(diff)
        all_clean = True
        conflict_files: list[str] = []

        for rel_path, is_new, is_deleted in file_entries:
            is_clean, is_conflict = self._merge_one_file(
                rel_path,
                target,
                base_snapshot,
                upstream_snapshot,
                is_new=is_new,
                is_deleted=is_deleted,
            )
            if not is_clean:
                all_clean = False
            if is_conflict:
                conflict_files.append(rel_path)

        if conflict_files:
            detail = "\n".join(f"  {f}" for f in conflict_files)
            logger.warning(
                f"The following file(s) have conflict markers to resolve:\n{detail}\n"
                "  Resolve each <<<<<<< / ======= / >>>>>>> block and remove the markers\n"
                "  before committing."
            )

        return all_clean

    def _merge_one_file(
        self,
        rel_path: str,
        target: Path,
        base_snapshot: Path,
        upstream_snapshot: Path,
        *,
        is_new: bool,
        is_deleted: bool,
    ) -> tuple[bool, bool]:
        """Merge a single file, returning ``(is_clean, is_conflict)``.

        Files that were added, deleted, are absent from the target, or lack a
        base/upstream counterpart cannot be three-way merged and are applied
        wholesale via :meth:`_apply_non_merge`; everything else goes through
        ``git merge-file``.

        Args:
            rel_path: Path of the file relative to the repository root.
            target: Path to the target repository.
            base_snapshot: Directory containing files at the previously-synced SHA.
            upstream_snapshot: Directory containing files at the new upstream SHA.
            is_new: Whether the diff marks this file as newly added.
            is_deleted: Whether the diff marks this file as deleted.

        Returns:
            ``(is_clean, is_conflict)`` — ``is_clean`` is ``False`` when the
            merge failed, ``is_conflict`` is ``True`` when markers were written.
        """
        paths = _MergePaths(
            target=target / rel_path,
            upstream=upstream_snapshot / rel_path,
            base=base_snapshot / rel_path,
        )

        if is_new or is_deleted or not paths.target.exists() or not (paths.base.exists() and paths.upstream.exists()):
            self._apply_non_merge(rel_path, paths, is_new=is_new, is_deleted=is_deleted)
            return True, False

        return self._git_merge_file(rel_path, paths)

    def _scan_conflict_artifacts(self, target: Path) -> tuple[list[str], list[str]]:
        """Scan *target* for merge-conflict artifacts left by git.

        Looks for:

        - ``*.rej`` files produced by ``git apply --reject``.
        - Text files that contain ``<<<<<<<`` conflict markers (from
          ``git apply -3`` or ``git merge-file``).

        Args:
            target: Root of the working tree to scan.

        Returns:
            A ``(rej_files, marker_files)`` tuple, each a sorted list of
            paths relative to *target*.
        """
        rej_files: list[str] = []
        marker_files: list[str] = []
        for path in sorted(target.rglob("*")):
            if not path.is_file():
                continue
            rel = str(path.relative_to(target))
            if path.suffix == ".rej":
                rej_files.append(rel)
            else:
                try:
                    # Read up to 1 MB to avoid stalling on large binary files.
                    content = path.read_bytes()[:1_048_576]
                    if b"<<<<<<<" in content:
                        marker_files.append(rel)
                except OSError:
                    pass
        return rej_files, marker_files

    def _apply_diff(
        self,
        diff: str,
        target: Path,
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
            base_snapshot: Optional directory containing files at the base SHA.
            upstream_snapshot: Optional directory containing files at the upstream SHA.

        Returns:
            True if the diff applied cleanly, False if there were conflicts.
        """
        if not diff.strip():
            return True

        try:
            self._git_apply(["apply", "-3"], diff, target)
        except subprocess.CalledProcessError as e:
            stderr = self._decode_stderr(e.stderr)

            # git apply -3 cannot do a real 3-way merge when the template blobs are
            # not present in the target repository's object store.  If we have the
            # snapshot directories on disk, use git merge-file instead — it works
            # directly on file content and needs no shared git history.
            if base_snapshot is not None and upstream_snapshot is not None and "lacks the necessary blob" in stderr:
                logger.debug("git apply -3 lacks blob objects; switching to git merge-file fallback")
                return self._merge_file_fallback(diff, target, base_snapshot, upstream_snapshot)

            if stderr:
                logger.warning(f"3-way merge had conflicts:\n{stderr.strip()}")
            return self._apply_reject(diff, target)
        else:
            return True

    @staticmethod
    def _decode_stderr(stderr: bytes | str | None) -> str:
        """Decode subprocess stderr to a string, treating ``None`` as empty.

        Args:
            stderr: Captured stderr as bytes, str, or None.

        Returns:
            The decoded stderr, or an empty string when there was none.
        """
        return stderr.decode() if isinstance(stderr, bytes) else (stderr or "")

    def _git_apply(self, mode_args: list[str], diff: str, target: Path) -> None:
        """Run ``git apply`` with *mode_args*, feeding *diff* on stdin.

        Args:
            mode_args: Git apply arguments (e.g. ``["apply", "-3"]``).
            diff: Unified diff string.
            target: Path to the target repository.

        Raises:
            subprocess.CalledProcessError: If the git apply invocation exits non-zero.
        """
        subprocess.run(  # nosec B603  # noqa: S603
            [self.executable, *mode_args],
            input=diff.encode() if isinstance(diff, str) else diff,
            cwd=target,
            check=True,
            capture_output=True,
            env=self.env,
        )

    def _apply_reject(self, diff: str, target: Path) -> bool:
        """Apply *diff* with ``git apply --reject`` and report conflict artifacts.

        Args:
            diff: Unified diff string.
            target: Path to the target repository.

        Returns:
            Always False — a ``--reject`` apply means the 3-way merge did not
            apply cleanly.
        """
        try:
            self._git_apply(["apply", "--reject"], diff, target)
        except subprocess.CalledProcessError as e2:
            stderr2 = self._decode_stderr(e2.stderr)
            if stderr2:
                logger.warning(stderr2.strip())

        # Scan and report any conflict artifacts left behind so users know
        # exactly which files need attention.
        self._report_conflict_artifacts(target)
        return False

    def _report_conflict_artifacts(self, target: Path) -> None:
        """Scan *target* and emit guidance for any ``.rej`` files or conflict markers left behind."""
        rej_files, marker_files = self._scan_conflict_artifacts(target)
        if rej_files:
            rej_detail = "\n".join(f"  {f.removesuffix('.rej')}  (unresolved hunks saved to {f})" for f in rej_files)
            logger.warning(
                f"The following file(s) have unresolved hunks:\n{rej_detail}\n"
                "  Open each .rej file, manually apply the diff hunks to the source file,\n"
                "  then delete the .rej file before committing."
            )
        if marker_files:
            marker_detail = "\n".join(f"  {f}" for f in marker_files)
            logger.warning(
                f"The following file(s) contain conflict markers:\n{marker_detail}\n"
                "  Resolve each <<<<<<< / ======= / >>>>>>> block and remove the markers\n"
                "  before committing."
            )
        if not rej_files and not marker_files:
            logger.warning("Some changes could not be applied cleanly — check the working tree for partial edits.")

    def _copy_files_to_target(self, snapshot_dir: Path, target: Path, materialized: list[Path]) -> None:
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

    def sync_merge(
        self,
        target: Path,
        upstream_snapshot: Path,
        upstream_sha: str,
        base_sha: str | None,
        materialized: list[Path],
        template: "RhizaTemplate",
        excludes: set[str],
        lock: "TemplateLock",
        lock_file: "Path | None" = None,
        path_map: "dict[str, str] | None" = None,
    ) -> bool:
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
            lock: Pre-built :class:`~rhiza.models.TemplateLock` for this sync.
            lock_file: Optional explicit path for the lock file.  When ``None``
                the default ``<target>/.rhiza/template.lock`` is used.
            path_map: Optional source→destination path mapping for remapped
                bundle file entries.

        Returns:
            True if all changes applied cleanly, False if any conflicts remain.
        """
        # Snapshot the currently-tracked files before the merge runs.  The merge
        # may write a new lock (e.g. on the "template unchanged" early-return path
        # in _merge_with_base), so we must read the old state first to ensure
        # orphan cleanup compares against the previous sync, not the new one.
        old_tracked_files = lock_io._read_previously_tracked_files(target, lock_file=lock_file)

        base_snapshot = Path(tempfile.mkdtemp())
        clean = True
        try:
            if base_sha:
                clean = self._merge_with_base(
                    target,
                    upstream_snapshot,
                    upstream_sha,
                    base_sha,
                    base_snapshot,
                    template,
                    excludes,
                    lock,
                    lock_file=lock_file,
                    path_map=path_map,
                )
            else:
                logger.info("First sync — copying all template files")
                self._copy_files_to_target(upstream_snapshot, target, materialized)

            # Restore any template-managed files that are absent from the target.
            # This can happen when files tracked by the template do not exist in the
            # downstream repository — for example when the template snapshot was
            # unchanged since the last sync so no diff was applied, but the files
            # were never present or were manually deleted.
            missing_from_target = [p for p in materialized if not (target / p).exists()]
            if missing_from_target:
                logger.info(f"Restoring {len(missing_from_target)} template file(s) missing from target")
                self._copy_files_to_target(upstream_snapshot, target, missing_from_target)

            lock_io._warn_about_workflow_files(materialized)
            lock_io._clean_orphaned_files(
                target,
                materialized,
                excludes=excludes,
                base_snapshot=base_snapshot,
                previously_tracked_files=old_tracked_files if old_tracked_files else None,
                lock_file=lock_file,
            )
            lock_io._write_lock(target, lock, lock_file=lock_file)
            logger.success(f"Sync complete — {len(materialized)} file(s) processed")
        finally:
            if base_snapshot.exists():
                shutil.rmtree(base_snapshot)

        return clean

    def _merge_with_base(
        self,
        target: Path,
        upstream_snapshot: Path,
        upstream_sha: str,  # noqa: ARG002  # part of the merge-call signature; lock carries the sha
        base_sha: str,
        base_snapshot: Path,
        template: "RhizaTemplate",
        excludes: set[str],
        lock: "TemplateLock",
        lock_file: "Path | None" = None,
        path_map: "dict[str, str] | None" = None,
    ) -> bool:
        """Compute and apply the diff between base and upstream snapshots.

        Args:
            target: Path to the target repository.
            upstream_snapshot: Path to the upstream snapshot directory.
            upstream_sha: HEAD SHA of the upstream template.
            base_sha: Previously synced commit SHA.
            base_snapshot: Directory to populate with the base snapshot.
            template: The :class:`~rhiza.models.RhizaTemplate` driving this sync.
            excludes: Set of relative paths to exclude.
            lock: Pre-built :class:`~rhiza.models.TemplateLock` for this sync.
            lock_file: Optional explicit path for the lock file.  When ``None``
                the default ``<target>/.rhiza/template.lock`` is used.
            path_map: Optional source→destination path mapping for remapped
                bundle file entries.

        Returns:
            True if all changes applied cleanly, False if any conflicts remain.
        """
        logger.info(f"Cloning base snapshot at {base_sha[:12]}")
        base_clone = Path(tempfile.mkdtemp())
        try:
            self.clone_at_sha(template.git_url, base_sha, base_clone, template.include)
            _prepare_snapshot(base_clone, template.include, excludes, base_snapshot, path_map=path_map)
        except Exception:  # noqa: BLE001  # clone/snapshot can fail many ways; on any failure treat all files as new
            logger.warning("Could not checkout base commit — treating all files as new")
        finally:
            if base_clone.exists():
                shutil.rmtree(base_clone)

        diff = self.get_diff(base_snapshot, upstream_snapshot)

        if not diff.strip():
            logger.success("Template unchanged since last sync — nothing to apply")
            lock_io._write_lock(target, lock, lock_file=lock_file)
            return True

        logger.info("Applying template changes via 3-way merge (cruft)...")
        clean = self._apply_diff(diff, target, base_snapshot=base_snapshot, upstream_snapshot=upstream_snapshot)

        if clean:
            logger.success("All changes applied cleanly")
        else:
            logger.warning("Some changes had conflicts. Check for *.rej files and resolve manually.")

        return clean
