# This file is part of the jebel-quant/rhiza repository
# (https://github.com/jebel-quant/rhiza).
#
"""Command for listing files managed by Rhiza in tree style.

This module provides functionality to read .rhiza/template.lock and display
the managed files in a tree-style view.
"""

from pathlib import Path

from loguru import logger

from rhiza.commands._sync_helpers import _load_lock_or_warn


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


def _render_tree(tree: dict, prefix: str = "") -> list[str]:
    """Render a nested directory tree as lines of text.

    Args:
        tree: Nested dict as returned by _build_tree.
        prefix: The current indentation prefix.

    Returns:
        List of formatted strings for display.
    """
    lines: list[str] = []
    entries = list(tree.items())
    for index, (name, subtree) in enumerate(entries):
        is_last = index == len(entries) - 1
        connector = "└── " if is_last else "├── "
        lines.append(f"{prefix}{connector}{name}")
        if subtree:
            extension = "    " if is_last else "│   "
            lines.extend(_render_tree(subtree, prefix + extension))
    return lines


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

    tree = _build_tree(lock.files)
    lines = _render_tree(tree)

    print(".")
    for line in lines:
        print(line)

    file_count = len(lock.files)
    print(f"\n{file_count} file{'s' if file_count != 1 else ''} managed by Rhiza")
