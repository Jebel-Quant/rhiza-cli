"""Git utility helpers for Rhiza models."""

import os
import shutil
import subprocess  # nosec B404
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loguru import logger

if TYPE_CHECKING:
    from rhiza.models.lock import TemplateLock
    from rhiza.models.template import RhizaTemplate


@dataclass
class GitContext:
    """Bundles the git executable path and environment for subprocess calls.

    All git-invoking functions in the sync helpers accept a
    :class:`GitContext` instead of resolving the executable on their own,
    making them easily testable via binary injection.

    Attributes:
        executable: Absolute path to the git binary.
        env: Environment variables passed to every git subprocess.
    """

    executable: str
    env: dict[str, str] = field(default_factory=dict)

    @classmethod
    def default(cls) -> "GitContext":
        """Create a GitContext using the system git and process environment.

        Returns:
            A :class:`GitContext` populated with the real git executable path
            and a copy of the current process environment with
            ``GIT_TERMINAL_PROMPT`` set to ``"0"``.
        """
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"
        return cls(executable=get_git_executable(), env=env)

    def assert_status_clean(self, target: Path) -> None:
        """Raise RuntimeError if the target repository has uncommitted changes.

        Runs ``git status --porcelain`` and raises if the output is non-empty,
        preventing a sync from running on a dirty working tree.

        Args:
            target: Path to the target repository.

        Raises:
            RuntimeError: If the working tree has uncommitted changes.
        """
        result = subprocess.run(  # nosec B603  # noqa: S603
            [self.executable, "status", "--porcelain"],
            cwd=target,
            capture_output=True,
            text=True,
            env=self.env,
        )
        if result.stdout.strip():
            logger.error("Working tree is not clean. Please commit or stash your changes before syncing.")
            logger.error("Uncommitted changes:")
            for line in result.stdout.strip().splitlines():
                logger.error(f"  {line}")
            raise RuntimeError("Working tree is not clean. Please commit or stash your changes before syncing.")  # noqa: TRY003

    def handle_target_branch(self, target: Path, target_branch: str | None) -> None:
        """Handle target branch creation or checkout if specified.

        Args:
            target: Path to the target repository.
            target_branch: Optional branch name to create/checkout.
        """
        if not target_branch:
            return

        logger.info(f"Creating/checking out target branch: {target_branch}")
        try:
            result = subprocess.run(  # nosec B603  # noqa: S603
                [self.executable, "rev-parse", "--verify", target_branch],
                cwd=target,
                capture_output=True,
                text=True,
                env=self.env,
            )

            if result.returncode == 0:
                logger.info(f"Branch '{target_branch}' exists, checking out...")
                subprocess.run(  # nosec B603  # noqa: S603
                    [self.executable, "checkout", target_branch],
                    cwd=target,
                    check=True,
                    capture_output=True,
                    text=True,
                    env=self.env,
                )
            else:
                logger.info(f"Creating new branch '{target_branch}'...")
                subprocess.run(  # nosec B603  # noqa: S603
                    [self.executable, "checkout", "-b", target_branch],
                    cwd=target,
                    check=True,
                    capture_output=True,
                    text=True,
                    env=self.env,
                )
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create/checkout branch '{target_branch}'")
            _log_git_stderr_errors(e.stderr)
            logger.error("Please ensure you have no uncommitted changes or conflicts")
            raise

    def get_diff(self, repo0: Path, repo1: Path) -> str:
        """Compute the raw diff between two directory trees using ``git diff --no-index``.

        Args:
            repo0: Path to the base (old) directory tree.
            repo1: Path to the upstream (new) directory tree.
        """
        repo0_str = repo0.resolve().as_posix()
        repo1_str = repo1.resolve().as_posix()
        result = subprocess.run(  # nosec B603  # noqa: S603
            [
                self.executable,
                "-c",
                "diff.noprefix=",
                "diff",
                "--no-index",
                "--relative",
                "--binary",
                "--src-prefix=upstream-template-old/",
                "--dst-prefix=upstream-template-new/",
                "--no-ext-diff",
                "--no-color",
                repo0_str,
                repo1_str,
            ],
            cwd=repo0_str,
            capture_output=True,
            env=self.env,
        )
        diff = result.stdout.decode() if isinstance(result.stdout, bytes) else (result.stdout or "")
        for repo in [repo0_str, repo1_str]:
            from re import sub

            repo_nix = sub("/[a-z]:", "", repo)
            diff = diff.replace(f"upstream-template-old{repo_nix}", "upstream-template-old").replace(
                f"upstream-template-new{repo_nix}", "upstream-template-new"
            )
        diff = diff.replace(repo0_str + "/", "").replace(repo1_str + "/", "")
        return diff

    def sync_diff(self, target: Path, upstream_snapshot: Path) -> None:
        """Execute the diff (dry-run) strategy.

        Shows what would change without modifying any files.

        Args:
            target: Path to the target repository.
            upstream_snapshot: Path to the upstream snapshot directory.
        """
        diff = self.get_diff(target, upstream_snapshot)
        if diff.strip():
            logger.info(f"\n{diff}")
            changes = diff.count("diff --git")
            logger.info(f"{changes} file(s) would be changed")
        else:
            logger.success("No differences found")

    def _parse_diff_filenames(self, diff: str) -> list[tuple[str, bool, bool]]:
        """Parse a unified diff produced by :func:`GitContext.get_diff` into file entries.

        Each entry is ``(rel_path, is_new, is_deleted)`` where *rel_path* is the
        path relative to both snapshot directories.

        Args:
            diff: Unified diff string from :func:`GitContext.get_diff`.

        Returns:
            List of ``(rel_path, is_new, is_deleted)`` tuples, one per changed file.
        """
        src_prefix = "upstream-template-old/"
        dst_prefix = "upstream-template-new/"

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

        Conflict markers (``<<<<<<<`` / ``=======`` / ``>>>>>>>``) are left in
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
                    self.executable,
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
                env=self.env,
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
            logger.warning(
                f"{len(conflict_files)} file(s) have conflict markers to resolve: " + ", ".join(conflict_files)
            )

        return all_clean

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
            subprocess.run(  # nosec B603  # noqa: S603
                [self.executable, "apply", "-3"],
                input=diff.encode() if isinstance(diff, str) else diff,
                cwd=target,
                check=True,
                capture_output=True,
                env=self.env,
            )
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode() if isinstance(e.stderr, bytes) else (e.stderr or "")

            # git apply -3 cannot do a real 3-way merge when the template blobs are
            # not present in the target repository's object store.  If we have the
            # snapshot directories on disk, use git merge-file instead — it works
            # directly on file content and needs no shared git history.
            if "lacks the necessary blob" in stderr and base_snapshot is not None and upstream_snapshot is not None:
                logger.debug("git apply -3 lacks blob objects; switching to git merge-file fallback")
                return self._merge_file_fallback(diff, target, base_snapshot, upstream_snapshot)

            if stderr:
                logger.warning(f"3-way merge had conflicts:\n{stderr.strip()}")
            # Fall back to --reject for conflict files
            try:
                subprocess.run(  # nosec B603  # noqa: S603
                    [self.executable, "apply", "--reject"],
                    input=diff.encode() if isinstance(diff, str) else diff,
                    cwd=target,
                    check=True,
                    capture_output=True,
                    env=self.env,
                )
            except subprocess.CalledProcessError as e2:
                stderr2 = e2.stderr.decode() if isinstance(e2.stderr, bytes) else (e2.stderr or "")
                if stderr2:
                    logger.warning(stderr2.strip())
                logger.warning(
                    "Some changes could not be applied cleanly. Check for *.rej files and resolve conflicts manually."
                )
            return False
        else:
            return True

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
            lock: Pre-built :class:`~rhiza.models.TemplateLock` for this sync.
        """
        from rhiza.commands._sync_helpers import (
            _clean_orphaned_files,
            _read_previously_tracked_files,
            _warn_about_workflow_files,
            _write_lock,
        )

        # Snapshot the currently-tracked files before the merge runs.  The merge
        # may write a new lock (e.g. on the "template unchanged" early-return path
        # in _merge_with_base), so we must read the old state first to ensure
        # orphan cleanup compares against the previous sync, not the new one.
        old_tracked_files = _read_previously_tracked_files(target)

        base_snapshot = Path(tempfile.mkdtemp())
        try:
            if base_sha:
                self._merge_with_base(
                    target,
                    upstream_snapshot,
                    upstream_sha,
                    base_sha,
                    base_snapshot,
                    template,
                    excludes,
                    lock,
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
        self,
        target: Path,
        upstream_snapshot: Path,
        upstream_sha: str,
        base_sha: str,
        base_snapshot: Path,
        template: "RhizaTemplate",
        excludes: set[str],
        lock: "TemplateLock",
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
            lock: Pre-built :class:`~rhiza.models.TemplateLock` for this sync.
        """
        from rhiza.commands._sync_helpers import _write_lock
        from rhiza.models import RhizaTemplate

        logger.info(f"Cloning base snapshot at {base_sha[:12]}")
        base_clone = Path(tempfile.mkdtemp())
        try:
            template._clone_at_sha(base_sha, base_clone, template.include, self)
            RhizaTemplate._prepare_snapshot(base_clone, template.include, excludes, base_snapshot)
        except Exception:
            logger.warning("Could not checkout base commit — treating all files as new")
        finally:
            if base_clone.exists():
                shutil.rmtree(base_clone)

        diff = self.get_diff(base_snapshot, upstream_snapshot)

        if not diff.strip():
            logger.success("Template unchanged since last sync — nothing to apply")
            _write_lock(target, lock)
            return

        logger.info("Applying template changes via 3-way merge (cruft)...")
        clean = self._apply_diff(diff, target, base_snapshot=base_snapshot, upstream_snapshot=upstream_snapshot)

        if clean:
            logger.success("All changes applied cleanly")
        else:
            logger.warning("Some changes had conflicts. Check for *.rej files and resolve manually.")


def _normalize_to_list(value: Any | list[Any] | None) -> list[Any]:
    r"""Convert a value to a list of strings.

    Handles the case where YAML multi-line strings (using |) are parsed as
    a single string instead of a list. Splits the string by newlines and
    strips whitespace from each item.

    Args:
        value: A string, list of strings, or None.

    Returns:
        A list of strings. Empty list if value is None or empty.

    Examples:
        >>> _normalize_to_list(None)
        []
        >>> _normalize_to_list([])
        []
        >>> _normalize_to_list(['a', 'b', 'c'])
        ['a', 'b', 'c']
        >>> _normalize_to_list('single line')
        ['single line']
        >>> _normalize_to_list('line1\\n' + 'line2\\n' + 'line3')
        ['line1', 'line2', 'line3']
        >>> _normalize_to_list('  item1  \\n' + '  item2  ')
        ['item1', 'item2']
    """
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        # Split by newlines and filter out empty strings
        # Handle both actual newlines (\n) and literal backslash-n (\\n)
        items = value.split("\\n") if "\\n" in value and "\n" not in value else value.split("\n")
        return [item.strip() for item in items if item.strip()]
    return []


def get_git_executable() -> str:
    """Get the absolute path to the git executable.

    This function ensures we use the full path to git to prevent
    security issues related to PATH manipulation.

    Returns:
        str: Absolute path to the git executable.

    Raises:
        RuntimeError: If git executable is not found in PATH.
    """
    git_path = shutil.which("git")
    if git_path is None:
        msg = "git executable not found in PATH. Please ensure git is installed and available."
        raise RuntimeError(msg)
    return git_path


def _log_git_stderr_errors(stderr: str | None) -> None:
    """Extract and log only relevant error messages from git stderr.

    Args:
        stderr: Git command stderr output.
    """
    if stderr:
        for line in stderr.strip().split("\n"):
            line = line.strip()
            if line and (line.startswith("fatal:") or line.startswith("error:")):
                logger.error(line)
