"""Bundle models for Rhiza configuration."""

from dataclasses import dataclass, field
from typing import Any

from rhiza.models._base import YamlSerializable
from rhiza.models._git_utils import _normalize_to_list


def _flatten_files(value: Any, prefix: str = "") -> list[str]:
    """Flatten a nested dict/list file structure into a list of path strings.

    When a dict is encountered, its keys become path components (folder names).
    When a list is encountered, each item is treated as a filename, optionally
    prefixed by the current path.

    Args:
        value: A list of filenames, a nested dict mapping folder names to
            further nested structures, or a single filename string.
        prefix: Path prefix to prepend to each resolved filename.

    Returns:
        A flat list of file path strings.

    Examples:
        >>> _flatten_files(["aapl.parquet", "msft.parquet"])
        ['aapl.parquet', 'msft.parquet']
        >>> _flatten_files({"data": {"prices": ["aapl.parquet"]}})
        ['data/prices/aapl.parquet']
        >>> _flatten_files({"config": ["model.yaml"]})
        ['config/model.yaml']
    """
    if value is None:
        return []
    if isinstance(value, list):
        return [f"{prefix}/{item}" if prefix else str(item) for item in value if item]
    if isinstance(value, dict):
        paths: list[str] = []
        for key, subvalue in value.items():
            new_prefix = f"{prefix}/{key}" if prefix else str(key)
            paths.extend(_flatten_files(subvalue, new_prefix))
        return paths
    if isinstance(value, str) and value:
        return [f"{prefix}/{value}" if prefix else value]
    return []


@dataclass(frozen=True, kw_only=True)
class BundleDefinition:
    """Represents a single bundle from template-bundles.yml.

    Attributes:
        description: Human-readable description of the bundle.
        files: List of file paths included in this bundle.
        requires: List of bundle names that this bundle requires.
        standalone: Whether this bundle is standalone (no dependencies).
    """

    # name: str
    description: str
    standalone: bool = True
    files: list[str] = field(default_factory=list)
    requires: list[str] = field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
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
            if bundle.requires:
                bundle_entry["requires"] = bundle.requires
            if bundle.standalone:
                bundle_entry["standalone"] = bundle.standalone
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

            raw_files = bundle_data.get("files")
            files = _flatten_files(raw_files) if isinstance(raw_files, dict) else _normalize_to_list(raw_files)
            requires = _normalize_to_list(bundle_data.get("requires"))

            bundles[bundle_name] = BundleDefinition(
                description=bundle_data.get("description", ""),
                files=files,
                requires=requires,
                standalone=bundle_data.get("standalone", True),
            )

        return cls(version=version, bundles=bundles)

    def resolve_to_paths(self, bundle_names: list[str]) -> list[str]:
        """Convert bundle names to deduplicated file paths.

        Args:
            bundle_names: List of bundle names to resolve.

        Returns:
            Deduplicated list of file paths from all bundles and their dependencies.

        Raises:
            ValueError: If a bundle doesn't exist or circular dependency detected.
        """
        bundles: set[str] = set()
        paths: list[str] = []
        seen: set[str] = set()

        for bundle_name in bundle_names:
            bundles.add(bundle_name)
            for bundle in self.bundles[bundle_name].requires:
                bundles.add(bundle)

        for bundle_name in bundles:
            bundle = self.bundles[bundle_name]
            for path in bundle.files:
                if path not in seen:
                    paths.append(path)
                    seen.add(path)

        return paths
