"""Bundle models for Rhiza configuration."""

from dataclasses import dataclass, field
from typing import Any

from rhiza.models._base import YamlSerializable
from rhiza.models._git_utils import _normalize_to_list


@dataclass(frozen=True)
class BundleFileEntry:
    """A file entry in a bundle, with optional source→destination path remapping.

    When ``source`` and ``dest`` differ, the file is read from ``source`` in the
    template repository but written to ``dest`` in the downstream project.

    Attributes:
        source: Path of the file in the template repository.
        dest: Path where the file should be placed in the downstream project.
    """

    source: str
    dest: str

    @property
    def is_remapped(self) -> bool:
        """True when the destination path differs from the source path."""
        return self.source != self.dest

    @classmethod
    def from_config_entry(cls, entry: "str | dict[str, str]") -> "BundleFileEntry":
        """Parse a file entry from a YAML config value (string or dict).

        Args:
            entry: Either a plain path string or a ``{source, dest}`` dict.

        Returns:
            A :class:`BundleFileEntry` instance.

        Raises:
            TypeError: If the entry is a dict without a ``source`` key.
        """
        if isinstance(entry, str):
            return cls(source=entry, dest=entry)
        if not isinstance(entry, dict) or "source" not in entry:
            raise TypeError(  # noqa: TRY003
                f"File entry must be a string or a dict with a 'source' key, got: {entry!r}"
            )
        source = entry["source"]
        dest = entry.get("dest", source)
        return cls(source=source, dest=dest)

    def to_config_entry(self) -> "str | dict[str, str]":
        """Serialize back to the YAML config representation."""
        if not self.is_remapped:
            return self.source
        return {"source": self.source, "dest": self.dest}

    def remap_expanded_path(self, expanded_source: str) -> str:
        """Map an expanded source path to its destination path.

        Handles both exact file matches and directory-prefix matches.

        Args:
            expanded_source: A source path produced by expanding this entry.

        Returns:
            The corresponding destination path.
        """
        if not self.is_remapped:
            return expanded_source
        if expanded_source == self.source:
            return self.dest
        src_prefix = self.source.rstrip("/") + "/"
        if expanded_source.startswith(src_prefix):
            dest_prefix = self.dest.rstrip("/") + "/"
            return dest_prefix + expanded_source[len(src_prefix) :]
        return expanded_source


@dataclass(frozen=True, kw_only=True)
class ProfileDefinition:
    """Represents a single profile from template-bundles.yml.

    Attributes:
        description: Human-readable description of the profile.
        bundles: List of bundle names included in this profile.
    """

    description: str = ""
    bundles: list[str] = field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class BundleDefinition:
    """Represents a single bundle from template-bundles.yml.

    Attributes:
        description: Human-readable description of the bundle.
        files: Explicit file entries (legacy format only — new bundles own files via
            their ``bundles/<name>/`` directory in the template repository).
        requires: List of bundle names that this bundle requires.
        recommends: List of bundle names that this bundle recommends (soft deps).
        standalone: Whether this bundle is standalone (no dependencies).
        required: Whether this bundle is mandatory (always included).
        notes: Free-form notes for maintainers (not synced to downstream projects).
    """

    description: str
    standalone: bool = True
    required: bool = False
    files: list[BundleFileEntry] = field(default_factory=list)
    requires: list[str] = field(default_factory=list)
    recommends: list[str] = field(default_factory=list)
    notes: str = ""


@dataclass(frozen=True, kw_only=True)
class RhizaBundles(YamlSerializable):
    """Represents the structure of template-bundles.yml.

    Attributes:
        version: Optional version string of the bundles configuration format.
        bundles: Dictionary mapping bundle names to their definitions.
    """

    version: str | None = None
    bundles: dict[str, BundleDefinition] = field(default_factory=dict)
    profiles: dict[str, ProfileDefinition] = field(default_factory=dict)

    @property
    def config(self) -> dict[str, Any]:
        """Return the bundles' current state as a configuration dictionary."""
        config: dict[str, Any] = {}

        if self.version is not None:
            config["version"] = self.version

        bundles_dict: dict[str, Any] = {}
        for name, bundle in self.bundles.items():
            bundle_entry: dict[str, Any] = {"description": bundle.description}
            if bundle.required:
                bundle_entry["required"] = bundle.required
            if bundle.standalone:
                bundle_entry["standalone"] = bundle.standalone
            if bundle.requires:
                bundle_entry["requires"] = bundle.requires
            if bundle.recommends:
                bundle_entry["recommends"] = bundle.recommends
            if bundle.files:
                bundle_entry["files"] = [f.to_config_entry() for f in bundle.files]
            if bundle.notes:
                bundle_entry["notes"] = bundle.notes
            bundles_dict[name] = bundle_entry

        config["bundles"] = bundles_dict

        if self.profiles:
            profiles_dict: dict[str, Any] = {}
            for name, profile in self.profiles.items():
                profile_entry: dict[str, Any] = {}
                if profile.description:
                    profile_entry["description"] = profile.description
                profile_entry["bundles"] = profile.bundles
                profiles_dict[name] = profile_entry
            config["profiles"] = profiles_dict

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
            if isinstance(raw_files, list):
                files = [BundleFileEntry.from_config_entry(e) for e in raw_files]
            elif isinstance(raw_files, str):
                files = [BundleFileEntry.from_config_entry(e) for e in _normalize_to_list(raw_files)]
            else:
                files = []
            requires = _normalize_to_list(bundle_data.get("requires"))

            bundles[bundle_name] = BundleDefinition(
                description=bundle_data.get("description", ""),
                files=files,
                requires=requires,
                recommends=_normalize_to_list(bundle_data.get("recommends")),
                standalone=bundle_data.get("standalone", True),
                required=bool(bundle_data.get("required", False)),
                notes=bundle_data.get("notes") or "",
            )

        profiles_config = config.get("profiles", {})
        if profiles_config is None:
            profiles_config = {}
        elif not isinstance(profiles_config, dict):
            msg = "Profiles must be a dictionary"
            raise TypeError(msg)

        profiles: dict[str, ProfileDefinition] = {}
        for profile_name, profile_data in profiles_config.items():
            if not isinstance(profile_data, dict):
                msg = f"Profile '{profile_name}' must be a dictionary"
                raise TypeError(msg)
            profiles[profile_name] = ProfileDefinition(
                description=profile_data.get("description", ""),
                bundles=_normalize_to_list(profile_data.get("bundles")),
            )

        return cls(version=version, bundles=bundles, profiles=profiles)

    def resolve_to_paths(self, bundle_names: list[str]) -> list[str]:
        """Convert bundle names to deduplicated file paths.

        Args:
            bundle_names: List of bundle names to resolve.

        Returns:
            Deduplicated list of file paths from all bundles and their dependencies.

        Raises:
            ValueError: If a bundle doesn't exist or circular dependency detected.
        """
        bundles: list[str] = []
        resolved: set[str] = set()
        resolving: set[str] = set()
        paths: list[str] = []
        seen: set[str] = set()

        def _collect(bundle_name: str) -> None:
            if bundle_name not in self.bundles:
                msg = f"Bundle '{bundle_name}' does not exist"
                raise ValueError(msg)
            if bundle_name in resolving:
                msg = f"Circular dependency detected for bundle '{bundle_name}'"
                raise ValueError(msg)
            if bundle_name in resolved:
                return

            resolving.add(bundle_name)
            for dependency in self.bundles[bundle_name].requires:
                _collect(dependency)
            resolving.remove(bundle_name)
            resolved.add(bundle_name)
            bundles.append(bundle_name)

        for bundle_name in bundle_names:
            _collect(bundle_name)

        for bundle_name in bundles:
            bundle = self.bundles[bundle_name]
            if bundle.files:
                for entry in bundle.files:
                    if entry.source not in seen:
                        paths.append(entry.source)
                        seen.add(entry.source)
            else:
                dir_path = f"bundles/{bundle_name}/"
                if dir_path not in seen:
                    paths.append(dir_path)
                    seen.add(dir_path)

        return paths

    def resolve_to_path_map(self, bundle_names: list[str]) -> dict[str, str]:
        """Return a source→destination mapping for all remapped file entries.

        Plain (non-remapped) entries are excluded — callers can assume an
        absent key means ``dest == source``.

        Args:
            bundle_names: List of bundle names to resolve (dependencies included).

        Returns:
            Dict mapping source path → destination path for remapped entries only.
        """
        path_map: dict[str, str] = {}
        resolved = self.resolve_to_paths(bundle_names)
        resolved_set = set(resolved)

        seen: set[str] = set()
        bundle_order: list[str] = []
        resolving: set[str] = set()

        def _collect(name: str) -> None:
            if name not in self.bundles or name in resolving or name in seen:
                return
            resolving.add(name)
            for dep in self.bundles[name].requires:
                _collect(dep)
            resolving.remove(name)
            seen.add(name)
            bundle_order.append(name)

        for name in bundle_names:
            _collect(name)

        for bundle_name in bundle_order:
            bundle = self.bundles[bundle_name]
            if bundle.files:
                for entry in bundle.files:
                    if entry.source in resolved_set and entry.is_remapped:
                        path_map[entry.source] = entry.dest
            else:
                path_map[f"bundles/{bundle_name}/"] = ""

        return path_map

    def resolve_profile_to_paths(self, profile_name: str) -> list[str]:
        """Resolve a profile name to deduplicated file paths.

        Args:
            profile_name: Name of the profile to resolve.

        Returns:
            Deduplicated list of file paths from all bundles in the profile.

        Raises:
            ValueError: If the profile doesn't exist or a referenced bundle doesn't exist.
        """
        if profile_name not in self.profiles:
            msg = f"Profile '{profile_name}' does not exist"
            raise ValueError(msg)
        return self.resolve_to_paths(self.profiles[profile_name].bundles)
