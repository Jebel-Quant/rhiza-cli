"""Snapshot preparation helpers: expand, exclude, remap, and copy files."""

import os
import shutil
from pathlib import Path

from loguru import logger


def _expand_paths(base_dir: Path, paths: list[str]) -> list[Path]:
    """Expand file/directory paths relative to *base_dir* into individual files.

    Args:
        base_dir: Root directory to resolve against.
        paths: Relative path strings.

    Returns:
        Flat list of file paths.
    """
    all_files: list[Path] = []
    for p in paths:
        full = base_dir / p
        if full.is_file():
            all_files.append(full)
        elif full.is_dir():
            all_files.extend(
                Path(dirpath) / fname
                for dirpath, _, filenames in os.walk(full, followlinks=True)
                for fname in filenames
            )
        else:
            logger.debug(f"Path not found in template repository: {p}")
    return all_files


def _excluded_set(base_dir: Path, excluded_paths: list[str]) -> set[str]:
    """Build a set of relative path strings that should be excluded.

    Args:
        base_dir: Root of the template clone.
        excluded_paths: User-configured exclude list.

    Returns:
        Set of relative path strings (always includes rhiza internals).
    """
    result: set[str] = set()
    for f in _expand_paths(base_dir, excluded_paths):
        result.add(str(f.relative_to(base_dir)))
    result.add(".rhiza/template.yml")
    return result


def _remap_path(source: str, path_map: dict[str, str]) -> str:
    """Translate *source* to its destination path using *path_map*.

    Supports both exact file matches and directory-prefix matches.  A prefix
    match is triggered when a key ends with ``/`` or when *source* starts with
    ``<key>/``.

    Args:
        source: Source-relative path from the template clone.
        path_map: Mapping of source path → destination path.

    Returns:
        The destination path, or *source* unchanged when no mapping applies.
    """
    if source in path_map:
        return path_map[source]
    for src, dest in path_map.items():
        src_prefix = src.rstrip("/") + "/"
        if source.startswith(src_prefix):
            suffix = source[len(src_prefix) :]
            if dest.rstrip("/"):
                return dest.rstrip("/") + "/" + suffix
            return suffix
    return source


def _prepare_snapshot(
    clone_dir: Path,
    include_paths: list[str],
    excludes: set[str],
    snapshot_dir: Path,
    path_map: dict[str, str] | None = None,
) -> list[Path]:
    """Copy included (non-excluded) files from a clone into a snapshot directory.

    When *path_map* is provided, files are written at their destination paths
    (rather than their source paths) so that downstream diffs and merges operate
    on the correct target locations.

    Args:
        clone_dir: Root of the template clone.
        include_paths: Source paths to include.
        excludes: Set of relative source paths to exclude.
        snapshot_dir: Destination directory for the snapshot.
        path_map: Optional source→destination path mapping.  Keys may be exact
            file paths or directory prefixes.

    Returns:
        List of relative destination file paths that were copied.
    """
    effective_map = path_map or {}
    template_files: list[Path] = []
    for f in _expand_paths(clone_dir, include_paths):
        rel_source = str(f.relative_to(clone_dir))
        if rel_source not in excludes:
            rel_dest = _remap_path(rel_source, effective_map)
            dst = snapshot_dir / rel_dest
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dst)
            template_files.append(Path(rel_dest))
    return template_files
