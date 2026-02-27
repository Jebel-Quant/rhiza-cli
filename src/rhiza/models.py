"""Data models for Rhiza configuration.

This module defines dataclasses that represent the structure of Rhiza
configuration files, making it easier to work with them without frequent
YAML parsing.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

__all__ = [
    "BundleDefinition",
    "RhizaBundles",
    "RhizaTemplate",
    "TemplateLock",
]


def _normalize_to_list(value: str | list[str] | None) -> list[str]:
    r"""Convert a value to a list of strings.

    Handles the case where YAML multi-line strings (using |) are parsed as
    a single string instead of a list. Splits the string by newlines and
    strips whitespace from each item.

    Args:
        value: A string, list of strings, or None.

    Returns:
        A list of strings. Empty list if value is None or empty.

    Examples:
        >>> _normalize_to_list(None)
        []
        >>> _normalize_to_list([])
        []
        >>> _normalize_to_list(['a', 'b', 'c'])
        ['a', 'b', 'c']
        >>> _normalize_to_list('single line')
        ['single line']
        >>> _normalize_to_list('line1\\n' + 'line2\\n' + 'line3')
        ['line1', 'line2', 'line3']
        >>> _normalize_to_list('  item1  \\n' + '  item2  ')
        ['item1', 'item2']
    """
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        # Split by newlines and filter out empty strings
        # Handle both actual newlines (\n) and literal backslash-n (\\n)
        items = value.split("\\n") if "\\n" in value and "\n" not in value else value.split("\n")
        return [item.strip() for item in items if item.strip()]
    return []


@dataclass
class BundleDefinition:
    """Represents a single bundle from template-bundles.yml.

    Attributes:
        name: The bundle identifier (e.g., "core", "tests", "github").
        description: Human-readable description of the bundle.
        files: List of file paths included in this bundle.
        workflows: List of workflow file paths included in this bundle.
        depends_on: List of bundle names that this bundle depends on.
    """

    name: str
    description: str
    files: list[str] = field(default_factory=list)
    workflows: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)

    def all_paths(self) -> list[str]:
        """Return combined files and workflows."""
        return self.files + self.workflows


@dataclass
class RhizaBundles:
    """Represents the structure of template-bundles.yml.

    Attributes:
        version: Optional version string of the bundles configuration format.
        bundles: Dictionary mapping bundle names to their definitions.
    """

    version: str | None = None
    bundles: dict[str, BundleDefinition] = field(default_factory=dict)

    @classmethod
    def from_yaml(cls, file_path: Path) -> "RhizaBundles":
        """Load RhizaBundles from a YAML file.

        Args:
            file_path: Path to the template-bundles.yml file.

        Returns:
            The loaded bundles configuration.

        Raises:
            FileNotFoundError: If the file does not exist.
            yaml.YAMLError: If the YAML is malformed.
            ValueError: If the file is empty or invalid.
            TypeError: If bundle data has invalid types.
        """
        with open(file_path) as f:
            config = yaml.safe_load(f)

        if not config:
            raise ValueError("Bundles file is empty")  # noqa: TRY003

        version = config.get("version")

        bundles_config = config.get("bundles", {})
        if not isinstance(bundles_config, dict):
            msg = "Bundles must be a dictionary"
            raise TypeError(msg)

        bundles: dict[str, BundleDefinition] = {}
        for bundle_name, bundle_data in bundles_config.items():
            if not isinstance(bundle_data, dict):
                msg = f"Bundle '{bundle_name}' must be a dictionary"
                raise TypeError(msg)

            files = _normalize_to_list(bundle_data.get("files"))
            workflows = _normalize_to_list(bundle_data.get("workflows"))
            depends_on = _normalize_to_list(bundle_data.get("depends-on"))

            bundles[bundle_name] = BundleDefinition(
                name=bundle_name,
                description=bundle_data.get("description", ""),
                files=files,
                workflows=workflows,
                depends_on=depends_on,
            )

        return cls(version=version, bundles=bundles)

    def resolve_dependencies(self, bundle_names: list[str]) -> list[str]:
        """Resolve bundle dependencies using topological sort.

        Args:
            bundle_names: List of bundle names to resolve.

        Returns:
            Ordered list of bundle names with dependencies first, no duplicates.

        Raises:
            ValueError: If a bundle doesn't exist or circular dependency detected.
        """
        # Validate all bundles exist
        for name in bundle_names:
            if name not in self.bundles:
                raise ValueError(f"Bundle '{name}' not found in template-bundles.yml")  # noqa: TRY003

        resolved: list[str] = []
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(bundle_name: str) -> None:
            if bundle_name in visited:
                return
            if bundle_name in visiting:
                raise ValueError(f"Circular dependency detected involving '{bundle_name}'")  # noqa: TRY003

            visiting.add(bundle_name)
            bundle = self.bundles[bundle_name]

            for dep in bundle.depends_on:
                if dep not in self.bundles:
                    raise ValueError(f"Bundle '{bundle_name}' depends on unknown bundle '{dep}'")  # noqa: TRY003
                visit(dep)

            visiting.remove(bundle_name)
            visited.add(bundle_name)
            resolved.append(bundle_name)

        for name in bundle_names:
            visit(name)

        return resolved

    def resolve_to_paths(self, bundle_names: list[str]) -> list[str]:
        """Convert bundle names to deduplicated file paths.

        Args:
            bundle_names: List of bundle names to resolve.

        Returns:
            Deduplicated list of file paths from all bundles and their dependencies.

        Raises:
            ValueError: If a bundle doesn't exist or circular dependency detected.
        """
        resolved_bundles = self.resolve_dependencies(bundle_names)
        paths: list[str] = []
        seen: set[str] = set()

        for bundle_name in resolved_bundles:
            bundle = self.bundles[bundle_name]
            for path in bundle.all_paths():
                if path not in seen:
                    paths.append(path)
                    seen.add(path)

        return paths


@dataclass
class RhizaTemplate:
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

    template_repository: str | None = None
    template_branch: str | None = None
    template_host: str = "github"
    language: str = "python"
    include: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)
    templates: list[str] = field(default_factory=list)

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
            raise ValueError("Template file is empty")  # noqa: TRY003

        # Support both 'repository' and 'template-repository' (repository takes precedence)
        # Empty or None values fall back to the alternative field
        template_repository = config.get("repository") or config.get("template-repository")

        # Support both 'ref' and 'template-branch' (ref takes precedence)
        # Empty or None values fall back to the alternative field
        template_branch = config.get("ref") or config.get("template-branch")

        return cls(
            template_repository=template_repository,
            template_branch=template_branch,
            template_host=config.get("template-host", "github"),
            language=config.get("language", "python"),
            include=_normalize_to_list(config.get("include")),
            exclude=_normalize_to_list(config.get("exclude")),
            templates=_normalize_to_list(config.get("templates")),
        )

    def to_yaml(self, file_path: Path) -> None:
        """Save RhizaTemplate to a YAML file.

        Args:
            file_path: Path where the template.yml file should be saved.
        """
        # Ensure parent directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert to dictionary with YAML-compatible keys
        config: dict[str, Any] = {}

        # Only include repository if it's not None
        if self.template_repository:
            config["repository"] = self.template_repository

        # Only include ref if it's not None
        if self.template_branch:
            config["ref"] = self.template_branch

        # Only include template-host if it's not the default "github"
        if self.template_host and self.template_host != "github":
            config["template-host"] = self.template_host

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

        with open(file_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)


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
    host: str = "github"
    ref: str = "main"
    include: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)
    templates: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)
    synced_at: str = ""
    strategy: str = ""

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
        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        data = yaml.safe_load(content)

        # Legacy plain-SHA format: yaml.safe_load returns the SHA string directly.
        if isinstance(data, str):
            return cls(sha=data.strip())

        if not isinstance(data, dict):
            raise TypeError("Invalid template.lock format")  # noqa: TRY003

        return cls(
            sha=data.get("sha", ""),
            repo=data.get("repo", ""),
            host=data.get("host", "github"),
            ref=data.get("ref", "main"),
            include=_normalize_to_list(data.get("include")),
            exclude=_normalize_to_list(data.get("exclude")),
            templates=_normalize_to_list(data.get("templates")),
            files=_normalize_to_list(data.get("files")),
            synced_at=data.get("synced_at", ""),
            strategy=data.get("strategy", ""),
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
            "host": self.host,
            "ref": self.ref,
            "include": self.include,
            "exclude": self.exclude,
            "templates": self.templates,
        }

        if self.files:
            config["files"] = self.files
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
