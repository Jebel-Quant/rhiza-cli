"""Command for uninstalling Rhiza template files from a repository.

This module implements the `uninstall` command. It reads the
`.rhiza/template.lock` file and removes all files that were previously
materialized by Rhiza templates. This provides a clean way to remove all
template-managed files from a project.
"""

from pathlib import Path

from loguru import logger


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
    if not force:
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

    # Remove tracking file
    if lock_file.exists():
        try:
            lock_file.unlink()
            logger.success(f"[DEL] {lock_file.relative_to(target)}")
            removed_count += 1
        except Exception as e:
            logger.error(f"Failed to delete {lock_file.relative_to(target)}: {e}")
            error_count += 1

    # Print summary
    logger.info("\nUninstall summary:")
    logger.info(f"  Files removed: {removed_count}")
    if skipped_count > 0:
        logger.info(f"  Files skipped (already deleted): {skipped_count}")
    if empty_dirs_removed > 0:
        logger.info(f"  Empty directories removed: {empty_dirs_removed}")
    if error_count > 0:
        logger.error(f"  Errors encountered: {error_count}")
        raise RuntimeError(f"Uninstall completed with {error_count} error(s)")  # noqa: TRY003

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
