"""Lock model for Rhiza configuration."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from rhiza.models._base import YamlSerializable
from rhiza.models._git_utils import _normalize_to_list
from rhiza.models.template import GitHost


class _LockDumper(yaml.Dumper):
    """Custom YAML dumper for ``template.lock``.

    Represents ``None`` leaf values as bare empty scalars so that file nodes
    in the ``files`` tree are written without any trailing value:

    .. code-block:: yaml

        files:
          .github:
            workflows:
              ci.yml:
          Makefile:

    rather than ``ci.yml: {}`` or ``ci.yml: null``.
    """


_LockDumper.add_representer(
    type(None),
    lambda dumper, _: dumper.represent_scalar("tag:yaml.org,2002:null", ""),
)


def _build_tree(paths: list[str]) -> dict:
    """Build a nested dict representing the directory tree.

    Args:
        paths: List of file path strings.

    Returns:
        A nested dictionary where keys are path components.  Directory nodes
        are non-empty dicts; file (leaf) nodes have the value ``None``.
    """
    root: dict = {}
    for path in sorted(paths):
        parts = Path(path).parts
        node = root
        for i, part in enumerate(parts):
            if i == len(parts) - 1:
                node[part] = None  # file leaf
            else:
                node = node.setdefault(part, {})
    return root


def _flatten_tree(tree: dict, prefix: str = "") -> list[str]:
    """Flatten a nested tree dict back to a sorted, deduplicated list of file paths.

    A node is treated as a **directory** when its value is a non-empty dict;
    everything else (``None``, ``{}``, a string, …) is treated as a **file**
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
            ``template.lock`` as a nested directory tree under the
            ``files:`` key; see :func:`_build_tree` and :func:`_flatten_tree`.
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

        ``files`` may be stored as a nested tree dict (current format) or as a
        flat list (legacy format).  Both are accepted so that old lock files
        continue to load correctly.

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

        ``files`` is serialised as a nested directory tree dict so that
        ``template.lock`` is human-readable and self-describing.
        """
        config: dict[str, Any] = {
            "sha": self.sha,
            "repo": self.repo,
            "host": str(self.host),
            "ref": self.ref,
            "include": self.include,
            "exclude": self.exclude,
            "templates": self.templates,
            "files": _build_tree(self.files),
        }
        if self.synced_at:
            config["synced_at"] = self.synced_at
        if self.strategy:
            config["strategy"] = self.strategy
        return config

    def to_yaml(self, file_path: Path) -> None:
        """Save the lock to a YAML file using :class:`_LockDumper`.

        File leaf nodes in the ``files`` tree are written as bare keys with no
        trailing value (e.g. ``Makefile:`` rather than ``Makefile: {}`` or
        ``Makefile: null``).

        Args:
            file_path: Destination path.  Parent directories are created
                automatically if they do not exist.
        """
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            yaml.dump(self.config, f, Dumper=_LockDumper, default_flow_style=False, sort_keys=False)
