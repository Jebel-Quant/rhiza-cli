"""Command for uninstalling Rhiza template files from a repository.

This module implements the `uninstall` command. It reads the `.rhiza/history`
file and removes all files that were previously materialized by Rhiza templates.
This provides a clean way to remove all template-managed files from a project.
"""

import sys
from pathlib import Path

from loguru import logger


def uninstall(target: Path, force: bool) -> None:
    """Uninstall Rhiza templates from the target repository.

    Reads the `.rhiza/history` file and removes all files listed in it.
    This effectively removes all files that were materialized by Rhiza.

    Args:
        target (Path): Path to the target repository.
        force (bool): If True, skip confirmation prompt and proceed with deletion.
    """
    # Resolve to absolute path to avoid any ambiguity
    target = target.resolve()

    logger.info(f"Target repository: {target}")

    # Check for history file in new location only
    history_file = target / ".rhiza" / "history"

    if not history_file.exists():
        logger.warning(f"No history file found at: {history_file.relative_to(target)}")
        logger.info("Nothing to uninstall. This repository may not have Rhiza templates materialized.")
        logger.info("If you haven't migrated yet, run 'rhiza migrate' first.")
        return

    # Read the history file
    logger.debug(f"Reading history file: {history_file.relative_to(target)}")
    files_to_remove: list[Path] = []

    with history_file.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if line and not line.startswith("#"):
                file_path = Path(line)
                files_to_remove.append(file_path)

    if not files_to_remove:
        logger.warning("History file is empty (only contains comments)")
        logger.info("Nothing to uninstall.")
        return

    logger.info(f"Found {len(files_to_remove)} file(s) to remove")

    # Show confirmation prompt unless --force is used
    if not force:
        logger.warning("This will remove the following files from your repository:")
        for file_path in sorted(files_to_remove):
            full_path = target / file_path
            if full_path.exists():
                logger.warning(f"  - {file_path}")
            else:
                logger.debug(f"  - {file_path} (already deleted)")

        # Prompt for confirmation
        try:
            response = input("\nAre you sure you want to proceed? [y/N]: ").strip().lower()
            if response not in ("y", "yes"):
                logger.info("Uninstall cancelled by user")
                return
        except (KeyboardInterrupt, EOFError):
            logger.info("\nUninstall cancelled by user")
            return

    # Remove files
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

    # Clean up empty directories
    logger.debug("Cleaning up empty directories...")
    empty_dirs_removed = 0
    for file_path in sorted(files_to_remove, reverse=True):
        full_path = target / file_path
        parent = full_path.parent

        # Try to remove parent directories if they're empty
        # Walk up the directory tree
        while parent != target and parent.exists():
            try:
                # Only remove if directory is empty
                if parent.is_dir() and not any(parent.iterdir()):
                    parent.rmdir()
                    logger.debug(f"[DEL] {parent.relative_to(target)}/ (empty directory)")
                    empty_dirs_removed += 1
                    parent = parent.parent
                else:
                    break
            except Exception:
                # Directory not empty or other error, stop walking up
                break

    # Remove history file itself
    try:
        history_file.unlink()
        logger.success(f"[DEL] {history_file.relative_to(target)}")
        removed_count += 1
    except Exception as e:
        logger.error(f"Failed to delete {history_file.relative_to(target)}: {e}")
        error_count += 1

    # Summary
    logger.info("\nUninstall summary:")
    logger.info(f"  Files removed: {removed_count}")
    if skipped_count > 0:
        logger.info(f"  Files skipped (already deleted): {skipped_count}")
    if empty_dirs_removed > 0:
        logger.info(f"  Empty directories removed: {empty_dirs_removed}")
    if error_count > 0:
        logger.error(f"  Errors encountered: {error_count}")
        sys.exit(1)

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
