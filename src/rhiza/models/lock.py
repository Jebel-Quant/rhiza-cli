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

    Represents ``None`` leaf values as bare empty scalars (``key:`` with no
    trailing value).  The :func:`_bare_keys_to_explicit` post-processor then
    converts these to YAML explicit-key notation (``? key``) so that no colon
    appears after file names in the final on-disk format.
    """


_LockDumper.add_representer(
    type(None),
    lambda dumper, _: dumper.represent_scalar("tag:yaml.org,2002:null", ""),
)


def _bare_keys_to_explicit(yaml_str: str) -> str:
    """Convert bare mapping-key lines inside the ``files:`` tree to YAML explicit-key notation.

    After :class:`_LockDumper` serialises ``None`` values, file leaf nodes in the
    ``files`` tree appear as ``key:`` with no trailing content.  This
    post-processor replaces those lines with ``? key`` — valid YAML explicit-key
    syntax that carries no colon after the file name — while leaving all other
    fields (``include:``, ``sha:``, etc.) completely unchanged.

    Only lines that are more deeply indented than the ``files:`` key itself are
    considered, which avoids accidentally converting unrelated top-level keys.

    ``yaml.safe_load`` reads ``? key`` back as ``{key: None}``, which
    :func:`_flatten_tree` handles correctly.

    Args:
        yaml_str: YAML text produced by :class:`_LockDumper`.

    Returns:
        YAML text with file-leaf lines inside ``files:`` rewritten as ``? key``.
    """
    lines = yaml_str.splitlines(keepends=True)
    n = len(lines)
    result = []

    # Locate the 'files:' key so we only touch lines inside its block.
    files_indent: int | None = None
    in_files = False

    for i, line in enumerate(lines):
        rstripped = line.rstrip("\n\r").rstrip()

        # Detect the start of the files: block.
        if not in_files:
            if rstripped == "files:" or rstripped.startswith("files: "):
                files_indent = len(rstripped) - len(rstripped.lstrip())
                in_files = True
            result.append(line)
            continue

        # If we encounter a non-empty line at the same depth as 'files:' (or
        # shallower), the files block has ended.
        if line.strip() and (len(line) - len(line.lstrip())) <= files_indent:  # type: ignore[operator]
            in_files = False
            result.append(line)
            continue

        # Only convert non-empty lines ending with ':' and no inline value.
        if rstripped.endswith(":") and ": " not in rstripped and rstripped.strip():
            current_indent = len(rstripped) - len(rstripped.lstrip())
            # A line is a leaf if no following non-empty line is more indented.
            is_leaf = True
            for j in range(i + 1, n):
                next_line = lines[j].rstrip("\n\r")
                if next_line.strip():
                    if len(next_line) - len(next_line.lstrip()) > current_indent:
                        is_leaf = False
                    break
            if is_leaf:
                key = rstripped.lstrip().rstrip(":")
                result.append(" " * current_indent + "? " + key + "\n")
                continue

        result.append(line)

    return "".join(result)


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
        """Save the lock to a YAML file.

        File leaf nodes in the ``files`` tree are written using YAML explicit-key
        notation (``? filename``) so that no colon or value appears after the file
        name on disk.  Directory nodes keep the standard ``dirname:`` form.

        ``yaml.safe_load`` reads ``? filename`` back as ``{filename: None}``,
        which :func:`_flatten_tree` handles correctly.

        Args:
            file_path: Destination path.  Parent directories are created
                automatically if they do not exist.
        """
        file_path.parent.mkdir(parents=True, exist_ok=True)
        raw = yaml.dump(self.config, Dumper=_LockDumper, default_flow_style=False, sort_keys=False)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(_bare_keys_to_explicit(raw))
