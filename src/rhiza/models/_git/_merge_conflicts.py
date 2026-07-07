"""Conflict-artifact scanning and reporting for the 3-way merge.

Split out of :mod:`rhiza.models._git.merge` (as a mixin, so the methods stay
on ``GitContext`` unchanged) to keep the merge module within the size budget.
"""

from pathlib import Path

from loguru import logger


class ConflictArtifactMixin:
    """Scan the working tree for merge leftovers (``.rej`` files / conflict markers) and report them."""

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
