"""Bundle models for Rhiza configuration."""

from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any

from rhiza.models._base import YamlSerializable
from rhiza.models._git.helpers import _normalize_to_list


def _ensure_safe_bundle_path(value: str) -> None:
    """Reject a bundle path that could escape the project directory.

    ``template.yml`` is effectively untrusted input (it is fetched from the
    template repository), and a remapped ``dest`` is joined onto the target
    directory to decide where a file is written.  An absolute path, a Windows
    drive letter, or a ``..`` traversal component could therefore write outside
    the project.  This validates both ``source`` and ``dest`` at the trust
    boundary so no such path can reach the materialize step.

    Args:
        value: A ``source`` or ``dest`` path from bundle config.

    Raises:
        ValueError: If *value* is absolute, uses a drive letter, or contains a
            ``..`` traversal component.
    """
    # Normalise separators so a Windows-style path cannot slip past the checks.
    normalized = value.replace("\\", "/")
    pure = PurePosixPath(normalized)
    has_drive = len(normalized) >= 2 and normalized[0].isalpha() and normalized[1] == ":"
    if pure.is_absolute() or has_drive or ".." in pure.parts:
        raise ValueError(  # noqa: TRY003
            f"Unsafe bundle path {value!r}: paths must be relative to the project "
            "root (no absolute paths, drive letters, or '..' traversal)."
        )


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

    def __post_init__(self) -> None:
        """Validate that both paths stay within the project (no escape)."""
        _ensure_safe_bundle_path(self.source)
        _ensure_safe_bundle_path(self.dest)

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

    @staticmethod
    def _bundle_to_entry(bundle: BundleDefinition) -> dict[str, Any]:
        """Serialise a single bundle definition into its config dict, omitting falsy fields."""
        entry: dict[str, Any] = {"description": bundle.description}
        if bundle.required:
            entry["required"] = bundle.required
        if bundle.standalone:
            entry["standalone"] = bundle.standalone
        if bundle.requires:
            entry["requires"] = bundle.requires
        if bundle.recommends:
            entry["recommends"] = bundle.recommends
        if bundle.files:
            entry["files"] = [f.to_config_entry() for f in bundle.files]
        if bundle.notes:
            entry["notes"] = bundle.notes
        return entry

    @staticmethod
    def _profile_to_entry(profile: ProfileDefinition) -> dict[str, Any]:
        """Serialise a single profile definition into its config dict."""
        entry: dict[str, Any] = {}
        if profile.description:
            entry["description"] = profile.description
        entry["bundles"] = profile.bundles
        return entry

    @property
    def config(self) -> dict[str, Any]:
        """Return the bundles' current state as a configuration dictionary."""
        config: dict[str, Any] = {}

        if self.version is not None:
            config["version"] = self.version

        config["bundles"] = {name: self._bundle_to_entry(bundle) for name, bundle in self.bundles.items()}

        if self.profiles:
            config["profiles"] = {name: self._profile_to_entry(profile) for name, profile in self.profiles.items()}

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

    def _resolve_bundle_order(self, bundle_names: list[str], *, strict: bool) -> list[str]:
        """Return *bundle_names* and their ``requires`` dependencies in topological order.

        Args:
            bundle_names: Bundle names to resolve.
            strict: When True, raise ``ValueError`` for unknown bundles or
                circular dependencies; when False, silently skip them.

        Returns:
            Dependency-first ordering of the resolved bundle names.

        Raises:
            ValueError: If ``strict`` and a bundle is missing or forms a cycle.
        """
        order: list[str] = []
        resolved: set[str] = set()
        resolving: set[str] = set()

        def _collect(name: str) -> None:
            """Recursively resolve a single bundle's dependencies in topological order."""
            if name not in self.bundles:
                if strict:
                    msg = f"Bundle '{name}' does not exist"
                    raise ValueError(msg)
                return
            if name in resolving:
                if strict:
                    msg = f"Circular dependency detected for bundle '{name}'"
                    raise ValueError(msg)
                return
            if name in resolved:
                return

            resolving.add(name)
            for dependency in self.bundles[name].requires:
                _collect(dependency)
            resolving.remove(name)
            resolved.add(name)
            order.append(name)

        for name in bundle_names:
            _collect(name)
        return order

    def resolve_to_paths(self, bundle_names: list[str]) -> list[str]:
        """Convert bundle names to deduplicated file paths.

        Args:
            bundle_names: List of bundle names to resolve.

        Returns:
            Deduplicated list of file paths from all bundles and their dependencies.

        Raises:
            ValueError: If a bundle doesn't exist or circular dependency detected.
        """
        paths: list[str] = []
        seen: set[str] = set()

        def _add(path: str) -> None:
            """Append a path once, tracking it in the dedup set."""
            if path not in seen:
                paths.append(path)
                seen.add(path)

        for bundle_name in self._resolve_bundle_order(bundle_names, strict=True):
            bundle = self.bundles[bundle_name]
            if bundle.files:
                for entry in bundle.files:
                    _add(entry.source)
            else:
                _add(f"bundles/{bundle_name}/")

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

        for bundle_name in self._resolve_bundle_order(bundle_names, strict=False):
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
