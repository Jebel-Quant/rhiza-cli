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
    """Represents the structure of .github/template.yml.

    Attributes:
    ----------
    template_repository : str | None
        The GitHub repository containing templates (e.g., "jebel-quant/rhiza").
        Can be None if not specified in the template file.
    template_branch : str | None
        The branch to use from the template repository.
        Can be None if not specified in the template file (defaults to "main" when creating).
    include : list[str]
        List of paths to include from the template repository.
    exclude : list[str]
        List of paths to exclude from the template repository (default: empty list).
    """

    template_repository: str | None = None
    template_branch: str | None = None
    include: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)

    @classmethod
    def from_yaml(cls, file_path: Path) -> "RhizaTemplate":
        """Load RhizaTemplate from a YAML file.

        Parameters
        ----------
        file_path : Path
            Path to the template.yml file.

        Returns:
        -------
        RhizaTemplate
            The loaded template configuration.

        Raises:
        ------
        FileNotFoundError
            If the file does not exist.
        yaml.YAMLError
            If the YAML is malformed.
        ValueError
            If the file is empty.
        """
        with open(file_path) as f:
            config = yaml.safe_load(f)

        if not config:
            raise ValueError("Template file is empty")

        return cls(
            template_repository=config.get("template-repository"),
            template_branch=config.get("template-branch"),
            include=config.get("include", []),
            exclude=config.get("exclude", []),
        )

    def to_yaml(self, file_path: Path) -> None:
        """Save RhizaTemplate to a YAML file.

        Parameters
        ----------
        file_path : Path
            Path where the template.yml file should be saved.
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

        # Include is always present as it's a required field for the config to be useful
        config["include"] = self.include

        # Only include exclude if it's not empty
        if self.exclude:
            config["exclude"] = self.exclude

        with open(file_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
