"""Diff computation and parsing for the sync engine."""

import subprocess  # nosec B404
from pathlib import Path

from loguru import logger

from rhiza.models._git._base import GitContextBase


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
        src_prefix = "upstream-template-old/"
        dst_prefix = "upstream-template-new/"

        results: list[tuple[str, bool, bool]] = []
        is_new = False
        is_deleted = False
        src_path: str | None = None
        dst_path: str | None = None
        in_diff = False

        def _flush() -> None:
            """Emit the current file entry into results if a path was captured."""
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
