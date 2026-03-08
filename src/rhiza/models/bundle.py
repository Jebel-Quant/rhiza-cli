"""Bundle models for Rhiza configuration."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rhiza.models._base import YamlSerializable
from rhiza.models._git_utils import _normalize_to_list


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
class RhizaBundles(YamlSerializable):
    """Represents the structure of template-bundles.yml.

    Attributes:
        version: Optional version string of the bundles configuration format.
        bundles: Dictionary mapping bundle names to their definitions.
    """

    version: str | None = None
    bundles: dict[str, BundleDefinition] = field(default_factory=dict)

    @property
    def config(self) -> dict[str, Any]:
        """Return the bundles' current state as a configuration dictionary."""
        config: dict[str, Any] = {}

        if self.version is not None:
            config["version"] = self.version

        bundles_dict: dict[str, Any] = {}
        for name, bundle in self.bundles.items():
            bundle_entry: dict[str, Any] = {"description": bundle.description}
            if bundle.files:
                bundle_entry["files"] = bundle.files
            if bundle.workflows:
                bundle_entry["workflows"] = bundle.workflows
            if bundle.depends_on:
                bundle_entry["depends-on"] = bundle.depends_on
            bundles_dict[name] = bundle_entry

        config["bundles"] = bundles_dict
        return config

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "RhizaBundles":
        """Create a RhizaBundles instance from a configuration dictionary.

        Args:
            config: Dictionary containing bundles configuration.

        Returns:
            A new RhizaBundles instance.

        Raises:
            TypeError: If bundle data has invalid types.
        """
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

    @classmethod
    def from_clone(cls, tmp_dir: Path) -> "RhizaBundles | None":
        """Load .rhiza/template-bundles.yml from a cloned template repo.

        Args:
            tmp_dir: Path to the cloned template repository.

        Returns:
            RhizaBundles if template-bundles.yml exists, None otherwise.

        Raises:
            yaml.YAMLError: If template-bundles.yml is malformed.
            ValueError: If template-bundles.yml is invalid.
        """
        bundles_file = tmp_dir / ".rhiza" / "template-bundles.yml"
        if not bundles_file.exists():
            return None
        return cls.from_yaml(bundles_file)
