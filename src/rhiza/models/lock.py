"""Lock model for Rhiza configuration."""

from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

from rhiza.models._base import YamlSerializable
from rhiza.models._git_utils import _normalize_to_list
from rhiza.models.template import GitHost


def _paths_to_tree(paths: list[str]) -> dict:
    """Convert a flat list of file paths to a nested dict tree structure.

    Directories become nested dicts; files become ``None`` leaf values.

    If a path and one of its ancestors both appear in *paths* (a file/directory
    conflict), the deeper path is silently skipped — the ancestor file wins.

    Args:
        paths: Sorted or unsorted list of POSIX-style file path strings.

    Returns:
        A nested dictionary representing the directory tree, where every
        leaf (file) maps to ``None``.

    Examples:
        >>> _paths_to_tree([])
        {}
        >>> _paths_to_tree(["Makefile"])
        {'Makefile': None}
        >>> _paths_to_tree(["src/a.py", "src/b.py"])
        {'src': {'a.py': None, 'b.py': None}}
    """
    root: dict = {}
    for path in sorted(paths):
        parts = Path(path).parts
        node = root
        conflict = False
        for part in parts[:-1]:
            if part in node and node[part] is None:  # already a leaf — cannot descend
                conflict = True
                break
            node = node.setdefault(part, {})
        if not conflict and not isinstance(node.get(parts[-1]), dict):
            node[parts[-1]] = None
    return root


def _tree_to_paths(tree: dict, prefix: str = "") -> list[str]:
    """Reconstruct a flat list of file paths from a nested dict tree.

    Handles both ``None`` leaf values (written by :func:`_paths_to_tree`)
    and empty-dict leaf values (written by legacy code).

    Args:
        tree: Nested dictionary as produced by :func:`_paths_to_tree`.
        prefix: Path prefix accumulated during recursion; leave empty
            for the root call.

    Returns:
        A sorted list of POSIX-style file path strings.

    Examples:
        >>> _tree_to_paths({})
        []
        >>> _tree_to_paths({'Makefile': None})
        ['Makefile']
        >>> _tree_to_paths({'src': {'a.py': None, 'b.py': None}})
        ['src/a.py', 'src/b.py']
    """
    paths: list[str] = []
    for name, subtree in tree.items():
        full = str(PurePosixPath(prefix) / name) if prefix else name
        if not subtree:  # None or empty dict → leaf file
            paths.append(full)
        else:
            paths.extend(_tree_to_paths(subtree, full))
    return sorted(paths)


class _EmptyNullDumper(yaml.Dumper):
    """YAML Dumper that serialises ``None`` as an empty scalar.

    This produces cleaner output for the ``files`` tree section,
    rendering leaf-file entries as ``filename:`` rather than
    ``filename: null``.
    """


def _null_representer(dumper: yaml.Dumper, _: None) -> yaml.ScalarNode:
    return dumper.represent_scalar("tag:yaml.org,2002:null", "")


_EmptyNullDumper.add_representer(type(None), _null_representer)


@dataclass(frozen=True, kw_only=True)
class TemplateLock(YamlSerializable):
    """Represents the structure of .rhiza/template.lock.

    Attributes:
        sha: The commit SHA of the last-synced template.
        repo: The template repository (e.g., "jebel-quant/rhiza").
        host: The git hosting platform (e.g., "github", "gitlab").
        ref: The branch or ref that was synced (e.g., "main").
        include: List of paths included from the template.
        exclude: List of paths excluded from the template.
        templates: List of template bundle names.
        files: List of file paths that were synced.
        synced_at: ISO 8601 UTC timestamp of when the sync was performed.
        strategy: The sync strategy used (e.g., "merge", "diff", "materialize").
    """

    sha: str
    repo: str = ""
    host: GitHost | str = GitHost.GITHUB
    ref: str = "main"
    include: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)
    templates: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)
    synced_at: str = ""
    strategy: str = ""

    def __post_init__(self) -> None:
        """Normalise *files*: deduplicate, canonicalise paths, and sort.

        Also removes paths whose ancestor is already tracked as a file
        (a path cannot simultaneously be both a file and a directory).
        """
        canonical: set[str] = {str(Path(f)) for f in self.files if f}
        result: list[str] = []
        for path in sorted(canonical):
            parts = Path(path).parts
            if not any(str(Path(*parts[:k])) in canonical for k in range(1, len(parts))):
                result.append(path)
        object.__setattr__(self, "files", result)

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "TemplateLock":
        """Create a TemplateLock instance from a configuration dictionary.

        Accepts ``files`` as either a flat list (legacy format) or a nested
        dict tree (current format produced by :meth:`config`).

        Args:
            config: Dictionary containing lock configuration.

        Returns:
            A new TemplateLock instance.
        """
        files_raw = config.get("files")
        files = _tree_to_paths(files_raw) if isinstance(files_raw, dict) else _normalize_to_list(files_raw)

        return cls(
            sha=config.get("sha", ""),
            repo=config.get("repo", ""),
            host=config.get("host", GitHost.GITHUB),
            ref=config.get("ref", "main"),
            include=_normalize_to_list(config.get("include")),
            exclude=_normalize_to_list(config.get("exclude")),
            templates=_normalize_to_list(config.get("templates")),
            files=files,
            synced_at=config.get("synced_at", ""),
            strategy=config.get("strategy", ""),
        )

    @property
    def config(self) -> dict[str, Any]:
        """Return the lock's current state as a configuration dictionary.

        The ``files`` field is serialised as a nested dict tree (see
        :func:`_paths_to_tree`) so that the lock file is human-readable.
        An empty files list is kept as ``[]`` for clarity.
        """
        config: dict[str, Any] = {
            "sha": self.sha,
            "repo": self.repo,
            "host": str(self.host),
            "ref": self.ref,
            "include": self.include,
            "exclude": self.exclude,
            "templates": self.templates,
            "files": _paths_to_tree(self.files) if self.files else [],
        }
        if self.synced_at:
            config["synced_at"] = self.synced_at
        if self.strategy:
            config["strategy"] = self.strategy
        return config

    def to_yaml(self, file_path: Path) -> None:
        """Save the lock to a YAML file using tree-style file listing.

        Overrides the base implementation to use :class:`_EmptyNullDumper`
        so that leaf-file entries in the ``files`` tree are rendered as
        ``filename:`` rather than ``filename: null``.

        Args:
            file_path: Destination path.  Parent directories are created
                automatically if they do not exist.
        """
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            yaml.dump(self.config, f, Dumper=_EmptyNullDumper, default_flow_style=False, sort_keys=False)
