"""Command for uninstalling Rhiza template files from a repository.

This module implements the `uninstall` command. It reads the
`.rhiza/template.lock` file and removes all files that were previously
materialized by Rhiza templates. This provides a clean way to remove all
template-managed files from a project.
"""

from pathlib import Path

import questionary
from loguru import logger

from rhiza.commands.init import _RHIZA_STYLE


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
        confirmed = questionary.confirm(
            "Are you sure you want to proceed?",
            default=False,
            style=_RHIZA_STYLE,
        ).ask()
        if not confirmed:
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
        except PermissionError:
            # On Windows, read-only files must be made writable before deletion
            try:
                import stat

                full_path.chmod(full_path.stat().st_mode | stat.S_IWRITE)
                full_path.unlink()
                logger.success(f"[DEL] {file_path}")
                removed_count += 1
            except Exception as e:
                logger.error(f"Failed to delete {file_path}: {e}")
                error_count += 1
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
        raise RuntimeError(f"Uninstall completed with {error_count} error(s)")  # noqa: TRY003


def uninstall(target: Path, force: bool) -> None:
    """Uninstall Rhiza templates from the target repository.

    Reads `.rhiza/template.lock` and removes all files listed in it.
    This effectively removes all files that were materialized by Rhiza.

    Args:
        target (Path): Path to the target repository.
        force (bool): If True, skip confirmation prompt and proceed with deletion.
    """
    target = target.resolve()
    logger.info(f"Target repository: {target}")

    lock_file = target / ".rhiza" / "template.lock"

    if not lock_file.exists():
        logger.warning(f"No lock file found at: {(target / '.rhiza' / 'template.lock').relative_to(target)}")
        logger.info("Nothing to uninstall. This repository may not have Rhiza templates materialized.")
        return

    try:
        from rhiza.models import TemplateLock

        lock = TemplateLock.from_yaml(lock_file)
        files_to_remove = [Path(f) for f in lock.files] if lock.files else []
        logger.debug(f"Reading file list from template.lock ({len(files_to_remove)} files)")
    except Exception as e:
        logger.error(f"Failed to read template.lock: {e}")
        return

    if not files_to_remove:
        logger.warning("No files found to uninstall")
        logger.info("Nothing to uninstall.")
        return

    logger.info(f"Found {len(files_to_remove)} file(s) to remove")

    # Confirm uninstall unless force is used
    if not force and not _confirm_uninstall(files_to_remove, target):
        return

    # Remove files
    removed_count, skipped_count, error_count = _remove_files(files_to_remove, target)

    # Clean up empty directories
    empty_dirs_removed = _cleanup_empty_directories(files_to_remove, target)

    # Remove tracking file
    if lock_file.exists():
        r, e = _remove_history_file(lock_file, target)
        removed_count += r
        error_count += e

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
