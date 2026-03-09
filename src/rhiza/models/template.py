"""Template model for Rhiza configuration."""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from rhiza.models._base import YamlSerializable
from rhiza.models._git_utils import _normalize_to_list

if TYPE_CHECKING:
    from rhiza.models.bundle import RhizaBundles


class GitHost(StrEnum):
    """Supported git hosting platforms."""

    GITHUB = "github"
    GITLAB = "gitlab"


@dataclass(kw_only=True, frozen=True)
class RhizaTemplate(YamlSerializable):
    """Represents the structure of .rhiza/template.yml.

    Attributes:
        template_repository: The GitHub or GitLab repository containing templates (e.g., "jebel-quant/rhiza").
            Can be None if not specified in the template file.
        template_branch: The branch to use from the template repository.
            Can be None if not specified in the template file (defaults to "main" when creating).
        template_host: The git hosting platform ("github" or "gitlab").
            Defaults to "github" if not specified in the template file.
        language: The programming language of the project ("python", "go", etc.).
            Defaults to "python" if not specified in the template file.
        include: List of paths to include from the template repository (path-based mode).
        exclude: List of paths to exclude from the template repository (default: empty list).
        templates: List of template names to include (template-based mode).
            Can be used together with include to merge paths.
    """

    template_repository: str = ""
    template_branch: str = ""
    template_host: GitHost | str = GitHost.GITHUB
    language: str = "python"
    include: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)
    templates: list[str] = field(default_factory=list)

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "RhizaTemplate":
        """Create a RhizaTemplate instance from a configuration dictionary.

        Args:
            config: Dictionary containing template configuration.

        Returns:
            A new RhizaTemplate instance.
        """
        # Support both 'repository' and 'template-repository' (repository takes precedence)
        # Empty or None values fall back to the alternative field
        template_repository = config.get("repository") or config.get("template-repository")

        # Support both 'ref' and 'template-branch' (ref takes precedence)
        # Empty or None values fall back to the alternative field
        template_branch = config.get("ref") or config.get("template-branch")

        return cls(
            template_repository=template_repository or "",
            template_branch=template_branch or "",
            template_host=config.get("template-host", GitHost.GITHUB),
            language=config.get("language", "python"),
            include=_normalize_to_list(config.get("include")),
            exclude=_normalize_to_list(config.get("exclude")),
            templates=_normalize_to_list(config.get("templates")),
        )

    @property
    def config(self) -> dict[str, Any]:
        """Read template configuration from the template.yml file."""
        # Convert to dictionary with YAML-compatible keys
        config: dict[str, Any] = {}

        # Only include repository if it's not None
        if self.template_repository:
            config["repository"] = self.template_repository

        # Only include ref if it's not None
        if self.template_branch:
            config["ref"] = self.template_branch

        # Only include template-host if it's not the default "github"
        if self.template_host and self.template_host != GitHost.GITHUB:
            config["template-host"] = str(self.template_host)

        # Only include language if it's not the default "python"
        if self.language and self.language != "python":
            config["language"] = self.language

        # Write templates if present
        if self.templates:
            config["templates"] = self.templates

        # Write include if present (can coexist with templates)
        if self.include:
            config["include"] = self.include

        # Only include exclude if it's not empty
        if self.exclude:
            config["exclude"] = self.exclude

        return config

    @property
    def git_url(self) -> str:
        """Construct the HTTPS clone URL for this template repository.

        Returns:
            HTTPS clone URL derived from ``template_repository`` and
            ``template_host``.

        Raises:
            ValueError: If ``template_repository`` is not set or
                ``template_host`` is not ``"github"`` or ``"gitlab"``.
        """
        if not self.template_repository:
            raise ValueError("template_repository is not configured in template.yml")  # noqa: TRY003
        host = self.template_host or GitHost.GITHUB
        if host == GitHost.GITHUB:
            return f"https://github.com/{self.template_repository}.git"
        if host == GitHost.GITLAB:
            return f"https://gitlab.com/{self.template_repository}.git"
        raise ValueError(f"Unsupported template-host: {host}. Must be 'github' or 'gitlab'.")  # noqa: TRY003

    def resolve_include_paths(self, bundles: "RhizaBundles") -> list[str]:
        """Resolve template bundle names to concrete include paths.

        Args:
            bundles: The loaded bundle definitions.

        Returns:
            List of file paths resolved from ``self.templates``.
        """
        return bundles.resolve_to_paths(self.templates)
