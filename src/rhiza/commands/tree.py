# This file is part of the jebel-quant/rhiza repository
# (https://github.com/jebel-quant/rhiza).
#
"""Command for listing files managed by Rhiza in tree style.

This module provides functionality to read .rhiza/template.lock and display
the managed files in a tree-style view.
"""

from pathlib import Path

from loguru import logger
from rich.console import Console
from rich.tree import Tree

from rhiza.commands._sync_helpers import _load_lock_or_warn


def _build_rich_tree(paths: list[str]) -> Tree:
    """Build a Rich Tree from a list of file paths.

    Args:
        paths: List of file path strings.

    Returns:
        A Rich Tree rooted at ".".
    """
    rich_tree = Tree(".")
    node_cache: dict = {}
    for path in sorted(paths):
        parts = Path(path).parts
        parent: Tree = rich_tree
        current_path: tuple = ()
        for part in parts:
            key = (*current_path, part)
            if key not in node_cache:
                node_cache[key] = parent.add(part)
            parent = node_cache[key]
            current_path = key
    return rich_tree


def tree(target: Path) -> None:
    """Display files managed by Rhiza in a tree-style view.

    Reads .rhiza/template.lock and prints the list of managed files as a
    directory tree, similar to the Unix ``tree`` command.

    Args:
        target: Path to the target repository root.
    """
    lock = _load_lock_or_warn(target)
    if lock is None:
        return

    if not lock.files:
        logger.info("No files are tracked in template.lock")
        return

    rich_tree = _build_rich_tree(lock.files)
    console = Console()
    console.print(rich_tree)

    file_count = len(lock.files)
    console.print(f"\n{file_count} file{'s' if file_count != 1 else ''} managed by Rhiza")
