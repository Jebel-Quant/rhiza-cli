"""Lock model for Rhiza configuration."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from loguru import logger

from rhiza.models._base import read_yaml
from rhiza.models._git_utils import _normalize_to_list
from rhiza.models.template import GitHost

try:
    import fcntl

    _FCNTL_AVAILABLE = True
except ImportError:  # pragma: no cover - Windows
    _FCNTL_AVAILABLE = False


@dataclass
class TemplateLock:
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

    @classmethod
    def read_sha(cls, target: Path) -> str | None:
        """Read the last-synced commit SHA from the lock file in *target*.

        Handles both the structured YAML format and the legacy plain-SHA format.
        Uses an exclusive advisory lock (via ``fcntl.flock``) when available so
        that two concurrent ``rhiza sync`` processes cannot read a partially-written
        file.  Falls back silently on platforms without ``fcntl`` (e.g. Windows).

        Args:
            target: Path to the target repository.

        Returns:
            The commit SHA string or ``None`` when no lock exists.
        """
        lock_path = target / ".rhiza" / "template.lock"
        if not lock_path.exists():
            return None
        with lock_path.open(encoding="utf-8") as fh:
            if _FCNTL_AVAILABLE:
                fcntl.flock(fh, fcntl.LOCK_EX)
            else:
                logger.debug("fcntl not available - skipping advisory lock on read")
            content = fh.read().strip()
        data = yaml.safe_load(content)
        if isinstance(data, dict) and "sha" in data:
            return str(data["sha"])
        return None

    @classmethod
    def from_yaml(cls, file_path: Path) -> "TemplateLock":
        """Load TemplateLock from a YAML file.

        Supports both the structured YAML format and the legacy plain-SHA format.

        Args:
            file_path: Path to the template.lock file.

        Returns:
            The loaded lock data.

        Raises:
            FileNotFoundError: If the file does not exist.
            yaml.YAMLError: If the YAML is malformed.
            ValueError: If the file format is not recognised.
        """
        return cls.from_config(read_yaml(file_path))

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "TemplateLock":
        """Create a TemplateLock instance from a configuration dictionary.

        Args:
            config: Dictionary containing lock configuration.

        Returns:
            A new TemplateLock instance.
        """
        return cls(
            sha=config.get("sha", ""),
            repo=config.get("repo", ""),
            host=config.get("host", GitHost.GITHUB),
            ref=config.get("ref", "main"),
            include=_normalize_to_list(config.get("include")),
            exclude=_normalize_to_list(config.get("exclude")),
            templates=_normalize_to_list(config.get("templates")),
            files=_normalize_to_list(config.get("files")),
            synced_at=config.get("synced_at", ""),
            strategy=config.get("strategy", ""),
        )

    def to_yaml(self, file_path: Path) -> None:
        """Save TemplateLock to a YAML file.

        Args:
            file_path: Path where the template.lock file should be saved.
        """
        file_path.parent.mkdir(parents=True, exist_ok=True)

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

        class _IndentedDumper(yaml.Dumper):
            def increase_indent(self, flow: bool = False, indentless: bool = False) -> None:
                # Always use indented style for sequences regardless of context.
                return super().increase_indent(flow, indentless=False)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write("# This file is automatically generated by rhiza. Do not edit it manually.\n")
            yaml.dump(
                config,
                f,
                Dumper=_IndentedDumper,
                default_flow_style=False,
                sort_keys=False,
                explicit_start=True,
            )
