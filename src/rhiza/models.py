"""Data models for Rhiza configuration.

This module defines dataclasses that represent the structure of Rhiza
configuration files, making it easier to work with them without frequent
YAML parsing.
"""

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class RhizaTemplate:
    """Represents the structure of .github/rhiza/template.yml.

    Attributes:
        template_repository: The GitHub or GitLab repository containing templates (e.g., "jebel-quant/rhiza").
            Can be None if not specified in the template file.
        template_branch: The branch to use from the template repository.
            Can be None if not specified in the template file (defaults to "main" when creating).
        template_host: The git hosting platform ("github" or "gitlab").
            Defaults to "github" if not specified in the template file.
        include: List of paths to include from the template repository.
            If empty and exclude is provided, all files will be included except those in exclude.
        exclude: List of paths to exclude from the template repository (default: empty list).
    """

    template_repository: str | None = None
    template_branch: str | None = None
    template_host: str = "github"
    include: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)

    @property
    def include_all(self) -> bool:
        """Check if this template should include all files from the repository.

        Returns True when include list is empty, meaning all files should be
        included (subject to exclude filters).

        Returns:
            True if all files should be included, False if specific paths are listed.
        """
        return len(self.include) == 0

    @classmethod
    def from_yaml(cls, file_path: Path) -> "RhizaTemplate":
        """Load RhizaTemplate from a YAML file.

        Args:
            file_path: Path to the template.yml file.

        Returns:
            The loaded template configuration.

        Raises:
            FileNotFoundError: If the file does not exist.
            yaml.YAMLError: If the YAML is malformed.
            ValueError: If the file is empty.
        """
        with open(file_path) as f:
            config = yaml.safe_load(f)

        if not config:
            raise ValueError("Template file is empty")

        return cls(
            template_repository=config.get("template-repository"),
            template_branch=config.get("template-branch"),
            template_host=config.get("template-host", "github"),
            include=config.get("include", []),
            exclude=config.get("exclude", []),
        )

    def to_yaml(self, file_path: Path) -> None:
        """Save RhizaTemplate to a YAML file.

        Args:
            file_path: Path where the template.yml file should be saved.
        """
        # Ensure parent directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert to dictionary with YAML-compatible keys
        config = {}

        # Only include template-repository if it's not None
        if self.template_repository:
            config["template-repository"] = self.template_repository

        # Only include template-branch if it's not None
        if self.template_branch:
            config["template-branch"] = self.template_branch

        # Only include template-host if it's not the default "github"
        if self.template_host and self.template_host != "github":
            config["template-host"] = self.template_host

        # Only include 'include' if it's not empty (empty means include-all mode)
        if self.include:
            config["include"] = self.include

        # Only include exclude if it's not empty
        if self.exclude:
            config["exclude"] = self.exclude

        with open(file_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
