"""Command for displaying Rhiza sync status from template.lock.

This module provides functionality to read and display the current sync
state stored in .rhiza/template.lock.
"""

from pathlib import Path

from loguru import logger

from rhiza.commands._sync_helpers import _load_lock_or_warn


def status(target: Path) -> None:
    """Display the current sync status from template.lock.

    Reads .rhiza/template.lock and prints the repository, ref, SHA,
    sync timestamp, strategy, and included templates/paths.

    Args:
        target: Path to the target repository root.
    """
    lock = _load_lock_or_warn(target)
    if lock is None:
        return
    logger.info(f"Repository : {lock.host}/{lock.repo}")
    logger.info(f"Ref        : {lock.ref}")
    logger.info(f"SHA        : {lock.sha[:12]}")
    logger.info(f"Synced at  : {lock.synced_at}")
    logger.info(f"Strategy   : {lock.strategy}")
    if lock.templates:
        logger.info(f"Templates  : {', '.join(lock.templates)}")
    elif lock.include:
        logger.info(f"Include    : {', '.join(lock.include)}")
    logger.info("---")
    logger.info(f"Files      : {len(lock.files)}")
