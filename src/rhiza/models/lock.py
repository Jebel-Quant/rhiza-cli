"""Lock model for Rhiza configuration."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rhiza.models._base import YamlSerializable
from rhiza.models._git_utils import _normalize_to_list
from rhiza.models.template import GitHost


def _build_tree(paths: list[str]) -> dict:
    """Build a nested dict representing the directory tree (used for display only).

    Args:
        paths: List of file path strings.

    Returns:
        A nested dictionary where keys are path components and leaf nodes
        are empty dicts ``{}``.
    """
    root: dict = {}
    for path in sorted(paths):
        parts = Path(path).parts
        node = root
        for part in parts:
            node = node.setdefault(part, {})
    return root


def _flatten_tree(tree: dict, prefix: str = "") -> list[str]:
    """Flatten a nested tree dict back to a sorted, deduplicated list of file paths.

    A node is treated as a **directory** when its value is a non-empty dict;
    everything else (``{}``, ``None``, a string, …) is treated as a **file**
    leaf.  This makes loading backward-compatible with any leaf value that
    may have been written by an older version.

    Args:
        tree: Nested dict as returned by _build_tree.
        prefix: Path prefix accumulated during recursion.

    Returns:
        Sorted, deduplicated list of file path strings.
    """
    paths: list[str] = []
    for name, children in tree.items():
        full = str(Path(prefix) / name) if prefix else name
        if isinstance(children, dict) and children:
            paths.extend(_flatten_tree(children, full))
        else:
            paths.append(full)
    return sorted(set(paths)) if not prefix else paths


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
        files: List of file paths that were synced.  Persisted in
            ``template.lock`` as a sorted flat list under the ``files:`` key.
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
        """Normalise ``files`` to a deduplicated, sorted list on construction."""
        object.__setattr__(self, "files", sorted(set(self.files)))

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "TemplateLock":
        """Create a TemplateLock instance from a configuration dictionary.

        ``files`` may be stored as a flat list (current format) or as a nested
        tree dict (legacy format from an older version).  Both are accepted so
        that old lock files continue to load correctly.

        Args:
            config: Dictionary containing lock configuration.

        Returns:
            A new TemplateLock instance.
        """
        raw_files = config.get("files")
        files = _flatten_tree(raw_files) if isinstance(raw_files, dict) else _normalize_to_list(raw_files)

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

        ``files`` is serialised as a sorted flat list.
        """
        config: dict[str, Any] = {
            "sha": self.sha,
            "repo": self.repo,
            "host": str(self.host),
            "ref": self.ref,
            "include": self.include,
            "exclude": self.exclude,
            "templates": self.templates,
            "files": self.files,
        }
        if self.synced_at:
            config["synced_at"] = self.synced_at
        if self.strategy:
            config["strategy"] = self.strategy
        return config
