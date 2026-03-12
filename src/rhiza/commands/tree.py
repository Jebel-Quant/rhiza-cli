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

    Each path component is a key.  File leaves end up as empty dicts (``{}``)
    because no children are ever added after the final path component.
    Directory nodes always have at least one child (a non-empty dict) because
    they are populated by the paths that pass through them.  This means the
    truthiness of a node's value reliably distinguishes files (``{}`` — falsy)
    from directories (non-empty dict — truthy) when traversing the tree.

    Args:
        paths: List of file path strings.

    Returns:
        A nested dictionary where keys are path components, directory nodes
        are non-empty dicts, and file leaf nodes are empty dicts.
    """
    root: dict = {}
    for path in sorted(paths):
        parts = Path(path).parts
        node = root
        for part in parts:
            node = node.setdefault(part, {})
    return root


def _count_directories(tree: dict) -> int:
    """Count directory nodes (nodes with non-empty children) in a tree.

    Args:
        tree: Nested dict as returned by _build_tree.

    Returns:
        Integer count of directory nodes.
    """
    count = 0
    for children in tree.values():
        if children:
            count += 1 + _count_directories(children)
    return count


def _print_tree(node: dict, indent: int = 0) -> None:
    """Print a nested directory tree as indented text.

    Directory entries are printed with a trailing ``/`` and their children
    are indented by two spaces per level.  File entries (leaf nodes with an
    empty dict value) are printed as plain names.

    Args:
        node: Nested dict as returned by :func:`_build_tree`.
        indent: Current indentation level (two spaces per level).
    """
    for name, children in node.items():
        if children:
            print("  " * indent + name + "/")
            _print_tree(children, indent + 1)
        else:
            print("  " * indent + name)


def tree(target: Path) -> None:
    """Display files managed by Rhiza in a tree-style view.

    Reads .rhiza/template.lock and prints the list of managed files as an
    indented directory tree.  Directories are shown with a trailing ``/``.

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

    print(header)
    print()
    _print_tree(built_tree)
    print()
    print(footer)
