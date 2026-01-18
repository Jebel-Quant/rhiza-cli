"""Command for uninstalling Rhiza template files from a repository.

This module implements the `uninstall` command. It reads the `.rhiza/history`
file and removes all files that were previously materialized by Rhiza templates.
This provides a clean way to remove all template-managed files from a project.
"""

import sys
from pathlib import Path

from loguru import logger


def _read_history_file(history_file: Path, target: Path) -> list[Path]:
    """Read history file and return list of files to remove.

    Args:
        history_file: Path to history file.
        target: Target repository path.

    Returns:
        List of file paths to remove.
    """
    logger.debug(f"Reading history file: {history_file.relative_to(target)}")
    files_to_remove: list[Path] = []

    with history_file.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                file_path = Path(line)
                files_to_remove.append(file_path)

    return files_to_remove


def _confirm_uninstall(files_to_remove: list[Path], target: Path) -> bool:
    """Show confirmation prompt and get user response.

    Args:
        files_to_remove: List of files to remove.
        target: Target repository path.

    Returns:
        True if user confirmed, False otherwise.
    """
    logger.warning("This will remove the following files from your repository:")
    for file_path in sorted(files_to_remove):
        full_path = target / file_path
        if full_path.exists():
            logger.warning(f"  - {file_path}")
        else:
            logger.debug(f"  - {file_path} (already deleted)")

    try:
        response = input("\nAre you sure you want to proceed? [y/N]: ").strip().lower()
        if response not in ("y", "yes"):
            logger.info("Uninstall cancelled by user")
            return False
    except (KeyboardInterrupt, EOFError):
        logger.info("\nUninstall cancelled by user")
        return False

    return True


def _remove_files(files_to_remove: list[Path], target: Path) -> tuple[int, int, int]:
    """Remove files from repository.

    Args:
        files_to_remove: List of files to remove.
        target: Target repository path.

    Returns:
        Tuple of (removed_count, skipped_count, error_count).
    """
    logger.info("Removing files...")
    removed_count = 0
    skipped_count = 0
    error_count = 0

    for file_path in sorted(files_to_remove):
        full_path = target / file_path

        if not full_path.exists():
            logger.debug(f"[SKIP] {file_path} (already deleted)")
            skipped_count += 1
            continue

        try:
            full_path.unlink()
            logger.success(f"[DEL] {file_path}")
            removed_count += 1
        except Exception as e:
            logger.error(f"Failed to delete {file_path}: {e}")
            error_count += 1

    return removed_count, skipped_count, error_count


def _cleanup_empty_directories(files_to_remove: list[Path], target: Path) -> int:
    """Clean up empty directories after file removal.

    Args:
        files_to_remove: List of files that were removed.
        target: Target repository path.

    Returns:
        Number of empty directories removed.
    """
    logger.debug("Cleaning up empty directories...")
    empty_dirs_removed = 0

    for file_path in sorted(files_to_remove, reverse=True):
        full_path = target / file_path
        parent = full_path.parent

        while parent != target and parent.exists():
            try:
                if parent.is_dir() and not any(parent.iterdir()):
                    parent.rmdir()
                    logger.debug(f"[DEL] {parent.relative_to(target)}/ (empty directory)")
                    empty_dirs_removed += 1
                    parent = parent.parent
                else:
                    break
            except Exception:
                break

    return empty_dirs_removed


def _remove_history_file(history_file: Path, target: Path) -> tuple[int, int]:
    """Remove the history file itself.

    Args:
        history_file: Path to history file.
        target: Target repository path.

    Returns:
        Tuple of (removed_count, error_count).
    """
    try:
        history_file.unlink()
        logger.success(f"[DEL] {history_file.relative_to(target)}")
    except Exception as e:
        logger.error(f"Failed to delete {history_file.relative_to(target)}: {e}")
        return 0, 1
    else:
        return 1, 0


def _print_summary(removed_count: int, skipped_count: int, empty_dirs_removed: int, error_count: int) -> None:
    """Print uninstall summary.

    Args:
        removed_count: Number of files removed.
        skipped_count: Number of files skipped.
        empty_dirs_removed: Number of empty directories removed.
        error_count: Number of errors encountered.
    """
    logger.info("\nUninstall summary:")
    logger.info(f"  Files removed: {removed_count}")
    if skipped_count > 0:
        logger.info(f"  Files skipped (already deleted): {skipped_count}")
    if empty_dirs_removed > 0:
        logger.info(f"  Empty directories removed: {empty_dirs_removed}")
    if error_count > 0:
        logger.error(f"  Errors encountered: {error_count}")
        sys.exit(1)


def uninstall(target: Path, force: bool) -> None:
    """Uninstall Rhiza templates from the target repository.

    Reads the `.rhiza/history` file and removes all files listed in it.
    This effectively removes all files that were materialized by Rhiza.

    Args:
        target (Path): Path to the target repository.
        force (bool): If True, skip confirmation prompt and proceed with deletion.
    """
    target = target.resolve()
    logger.info(f"Target repository: {target}")

    # Check for history file
    history_file = target / ".rhiza" / "history"
    if not history_file.exists():
        logger.warning(f"No history file found at: {history_file.relative_to(target)}")
        logger.info("Nothing to uninstall. This repository may not have Rhiza templates materialized.")
        logger.info("If you haven't migrated yet, run 'rhiza migrate' first.")
        return

    # Read history file
    files_to_remove = _read_history_file(history_file, target)
    if not files_to_remove:
        logger.warning("History file is empty (only contains comments)")
        logger.info("Nothing to uninstall.")
        return

    logger.info(f"Found {len(files_to_remove)} file(s) to remove")

    # Confirm uninstall unless force is used
    if not force:
        if not _confirm_uninstall(files_to_remove, target):
            return

    # Remove files
    removed_count, skipped_count, error_count = _remove_files(files_to_remove, target)

    # Clean up empty directories
    empty_dirs_removed = _cleanup_empty_directories(files_to_remove, target)

    # Remove history file
    history_removed, history_error = _remove_history_file(history_file, target)
    removed_count += history_removed
    error_count += history_error

    # Print summary
    _print_summary(removed_count, skipped_count, empty_dirs_removed, error_count)

    logger.success("Rhiza templates uninstalled successfully")
    logger.info(
        "Next steps:\n"
        "  Review changes:\n"
        "    git status\n"
        "    git diff\n\n"
        "  Commit:\n"
        "    git add .\n"
        '    git commit -m "chore: remove rhiza templates"'
    )
