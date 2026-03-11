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
from rich.tree import Tree as RichTree

from rhiza.commands._sync_helpers import _load_lock_or_warn


def _count_directories(tree: dict) -> int:
    """Count nodes with non-empty children (i.e. directories) in a tree.

    Args:
        tree: Nested dict as returned by _build_tree.

    Returns:
        Integer count of directory nodes (nodes that have children).
    """
    count = 0
    for subtree in tree.values():
        if subtree:
            count += 1 + _count_directories(subtree)
    return count


def _build_tree(paths: list[str]) -> dict:
    """Build a nested dict representing the directory tree.

    Args:
        paths: List of file path strings.

    Returns:
        A nested dictionary where keys are path components and leaf nodes
        are empty dicts.
    """
    root: dict = {}
    for path in sorted(paths):
        parts = Path(path).parts
        node = root
        for part in parts:
            node = node.setdefault(part, {})
    return root


def _populate_rich_tree(node: RichTree, subtree: dict) -> None:
    """Recursively populate a Rich Tree node from a nested dict.

    Args:
        node: The parent Rich Tree node to add children to.
        subtree: Nested dict as returned by _build_tree.
    """
    for name, children in subtree.items():
        child = node.add(name)
        if children:
            _populate_rich_tree(child, children)


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

    header = f"{lock.repo} @ {lock.sha[:12]}"
    if lock.ref:
        header = f"{header} ({lock.ref})"

    built_tree = _build_tree(lock.files)
    file_count = len(lock.files)
    dir_count = _count_directories(built_tree)
    dir_label = "director" + ("ies" if dir_count != 1 else "y")
    footer = f"{file_count} file{'s' if file_count != 1 else ''}, {dir_count} {dir_label} managed by Rhiza"

    console = Console()
    console.print(header)
    console.print()

    rich_tree = RichTree(".")
    _populate_rich_tree(rich_tree, built_tree)
    console.print(rich_tree)
    console.print()
    console.print(footer)
