"""Diff computation and parsing for the sync engine."""

import subprocess  # nosec B404
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from rhiza.models._git._base import GitContextBase

_SRC_PREFIX = "upstream-template-old/"
_DST_PREFIX = "upstream-template-new/"


def _path_after(line: str, marker: str, prefix: str) -> str | None:
    """Return the diff path on a ``---``/``+++`` header line, stripped of *prefix*."""
    raw = line[len(marker) :].strip().strip('"').split("\t")[0]
    if raw != "/dev/null" and raw.startswith(prefix):
        return raw[len(prefix) :]
    return None


@dataclass
class _DiffFileState:
    """Accumulates the per-file flags/paths seen while scanning one ``diff --git`` block."""

    is_new: bool = False
    is_deleted: bool = False
    src_path: str | None = None
    dst_path: str | None = None
    started: bool = False

    def reset(self) -> None:
        """Begin a new file block, clearing all accumulated state."""
        self.is_new = False
        self.is_deleted = False
        self.src_path = None
        self.dst_path = None
        self.started = True

    def update(self, line: str) -> None:
        """Update state from a single non-``diff --git`` header line."""
        if line.startswith("new file mode"):
            self.is_new = True
        elif line.startswith("deleted file mode"):
            self.is_deleted = True
        elif line.startswith("--- "):
            self.src_path = _path_after(line, "--- ", _SRC_PREFIX) or self.src_path
        elif line.startswith("+++ "):
            self.dst_path = _path_after(line, "+++ ", _DST_PREFIX) or self.dst_path

    def entry(self) -> tuple[str, bool, bool] | None:
        """Return the ``(rel_path, is_new, is_deleted)`` entry for this block, if a path was captured."""
        rel = self.src_path if self.is_deleted else self.dst_path
        return (rel, self.is_new, self.is_deleted) if rel else None


class DiffMixin(GitContextBase):
    """Compute and parse diffs between template snapshot trees."""

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
        """Parse a unified diff produced by :func:`DiffMixin.get_diff` into file entries.

        Each entry is ``(rel_path, is_new, is_deleted)`` where *rel_path* is the
        path relative to both snapshot directories.

        Args:
            diff: Unified diff string from :func:`DiffMixin.get_diff`.

        Returns:
            List of ``(rel_path, is_new, is_deleted)`` tuples, one per changed file.
        """
        results: list[tuple[str, bool, bool]] = []
        state = _DiffFileState()

        def _flush() -> None:
            """Emit the current file entry into results if a path was captured."""
            entry = state.entry()
            if entry:
                results.append(entry)

        for line in diff.splitlines():
            if line.startswith("diff --git "):
                if state.started:
                    _flush()
                state.reset()
            else:
                state.update(line)

        if state.started:
            _flush()

        return results
