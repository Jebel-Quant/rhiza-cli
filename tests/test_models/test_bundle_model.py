"""Tests for the RhizaBundles dataclass.

This module verifies that RhizaBundles correctly deserialises
template-bundles.yml files, and satisfies the YamlSerializable protocol.
"""

from rhiza.models._base import YamlSerializable, load_model
from rhiza.models.bundle import RhizaBundles

# ---------------------------------------------------------------------------
# YamlSerializable Protocol — bundle-related check
# ---------------------------------------------------------------------------


class TestYamlSerializableProtocol:
    """Tests for the YamlSerializable Protocol as it applies to RhizaBundles."""

    def test_rhiza_bundles_satisfies_protocol(self):
        """RhizaBundles is a runtime-checkable instance of YamlSerializable."""
        bundles = RhizaBundles.from_config({"bundles": {"core": {"description": "Core"}}})
        assert isinstance(bundles, YamlSerializable)


# ---------------------------------------------------------------------------
# load_model helper — bundle-related checks
# ---------------------------------------------------------------------------


class TestLoadModel:
    """Tests for the load_model generic helper as it applies to RhizaBundles."""

    def test_load_model_returns_rhiza_bundles(self, tmp_path):
        """load_model loads a RhizaBundles and returns the correct type/values."""
        import yaml

        bundles_file = tmp_path / "template-bundles.yml"
        bundles_file.write_text(
            yaml.dump({"version": "1", "bundles": {"core": {"description": "Core bundle", "files": ["Makefile"]}}})
        )

        result = load_model(RhizaBundles, bundles_file)

        assert isinstance(result, RhizaBundles)
        assert result.version == "1"
        assert "core" in result.bundles


# ---------------------------------------------------------------------------
# config property
# ---------------------------------------------------------------------------


class TestRhizaBundlesConfig:
    """Tests for the RhizaBundles.config property."""

    def test_config_without_version(self):
        """When version is None it is omitted from config."""
        bundles = RhizaBundles.from_config({"bundles": {"core": {"description": "Core"}}})
        cfg = bundles.config
        assert "version" not in cfg
        assert cfg["bundles"]["core"]["description"] == "Core"

    def test_config_with_version(self):
        """When version is set it appears in config."""
        bundles = RhizaBundles.from_config({"version": "2", "bundles": {"core": {"description": "Core"}}})
        assert bundles.config["version"] == "2"

    def test_config_omits_empty_files_and_workflows(self):
        """Files, workflows, and new optional fields are omitted when empty/default."""
        bundles = RhizaBundles.from_config({"bundles": {"core": {"description": "Core"}}})
        entry = bundles.config["bundles"]["core"]
        assert "files" not in entry
        assert "workflows" not in entry
        assert "recommends" not in entry
        assert "notes" not in entry
        assert "required" not in entry

    def test_config_round_trips_through_from_config(self):
        """Config output can be fed back into from_config producing an equal object."""
        original = RhizaBundles.from_config(
            {
                "version": "1",
                "bundles": {
                    "core": {"description": "Core", "files": ["Makefile"]},
                    "ci": {"description": "CI", "requires": ["core"]},
                },
            }
        )
        restored = RhizaBundles.from_config(original.config)
        assert restored.version == original.version
        assert restored.bundles["core"].files == original.bundles["core"].files
        assert restored.bundles["ci"].requires == original.bundles["ci"].requires

    def test_files_as_string_normalised_to_list(self):
        """A bundle's files field accepts a plain string and normalises it to a list."""
        from rhiza.models.bundle import BundleFileEntry

        b = RhizaBundles.from_config({"bundles": {"core": {"files": "Makefile"}}})
        assert b.bundles["core"].files == [BundleFileEntry(source="Makefile", dest="Makefile")]


# ---------------------------------------------------------------------------
# from_config error paths
# ---------------------------------------------------------------------------


class TestFromConfigErrors:
    """Tests for TypeError raised by invalid from_config inputs."""

    def test_bundles_not_a_dict_raises_type_error(self):
        """TypeError raised when bundles value is not a dict."""
        import pytest

        with pytest.raises(TypeError, match="Bundles must be a dictionary"):
            RhizaBundles.from_config({"bundles": ["not", "a", "dict"]})

    def test_bundle_entry_not_a_dict_raises_type_error(self):
        """TypeError raised when an individual bundle entry is not a dict."""
        import pytest

        with pytest.raises(TypeError, match="Bundle 'core' must be a dictionary"):
            RhizaBundles.from_config({"bundles": {"core": "not-a-dict"}})


# ---------------------------------------------------------------------------
# resolve_dependencies
# ---------------------------------------------------------------------------


class TestResolveDependencies:
    """Tests for RhizaBundles.resolve_dependencies."""

    def _make_bundles(self):
        return RhizaBundles.from_config(
            {
                "bundles": {
                    "core": {"description": "Core", "files": ["Makefile"]},
                    "tests": {"description": "Tests", "files": ["pytest.ini"], "depends-on": ["core"]},
                    "ci": {
                        "description": "CI",
                        "workflows": [".github/workflows/ci.yml"],
                        "depends-on": ["core", "tests"],
                    },
                }
            }
        )


# ---------------------------------------------------------------------------
# resolve_to_paths
# ---------------------------------------------------------------------------


class TestResolveToPaths:
    """Tests for RhizaBundles.resolve_to_paths."""

    def _make_bundles(self):
        return RhizaBundles.from_config(
            {
                "bundles": {
                    "core": {"description": "Core", "files": ["Makefile", "pyproject.toml"]},
                    "ci": {
                        "description": "CI",
                        "files": ["Makefile"],
                        "requires": ["core"],
                    },
                }
            }
        )

    def test_returns_paths_for_single_bundle(self):
        """Paths from a single bundle are returned correctly."""
        bundles = self._make_bundles()
        assert bundles.resolve_to_paths(["core"]) == ["Makefile", "pyproject.toml"]

    def test_deduplicates_paths_across_bundles(self):
        """A path shared by multiple bundles appears only once."""
        bundles = self._make_bundles()
        result = bundles.resolve_to_paths(["ci"])
        # Makefile comes from core (dependency) and ci — should appear once
        assert result.count("Makefile") == 1

    def test_resolves_transitive_bundle_dependencies(self):
        """Nested requires are resolved transitively."""
        bundles = RhizaBundles.from_config(
            {
                "bundles": {
                    "core": {"description": "Core", "files": ["pyproject.toml"]},
                    "github": {"description": "GitHub", "files": [".github/workflows/ci.yml"], "requires": ["core"]},
                    "github-tests": {"description": "GitHub tests", "files": ["tests/"], "requires": ["github"]},
                }
            }
        )

        result = bundles.resolve_to_paths(["github-tests"])
        assert "tests/" in result
        assert ".github/workflows/ci.yml" in result
        assert "pyproject.toml" in result

    def test_resolve_to_paths_raises_for_nonexistent_bundle(self):
        """ValueError raised when a requested bundle does not exist."""
        import pytest

        bundles = self._make_bundles()
        with pytest.raises(ValueError, match="does not exist"):
            bundles.resolve_to_paths(["nonexistent-bundle"])

    def test_resolve_to_paths_raises_for_circular_dependency(self):
        """ValueError raised when bundles form a circular dependency chain."""
        import pytest

        bundles = RhizaBundles.from_config(
            {
                "bundles": {
                    "a": {"description": "A", "files": ["a.txt"], "requires": ["b"]},
                    "b": {"description": "B", "files": ["b.txt"], "requires": ["a"]},
                }
            }
        )
        with pytest.raises(ValueError, match=r"[Cc]ircular"):
            bundles.resolve_to_paths(["a"])

    def test_resolve_to_paths_already_resolved_bundle_skipped(self):
        """A bundle that is a dependency of the first request is skipped when requested again."""
        bundles = self._make_bundles()
        # 'core' is a dependency of 'ci'; requesting both should not raise or duplicate.
        result = bundles.resolve_to_paths(["ci", "core"])
        assert result.count("Makefile") == 1
        assert result.count("pyproject.toml") == 1


# ---------------------------------------------------------------------------
# ProfileDefinition and profiles support
# ---------------------------------------------------------------------------


class TestProfileDefinition:
    """Tests for ProfileDefinition parsing and RhizaBundles.profiles."""

    def _make_bundles_with_profiles(self):
        return RhizaBundles.from_config(
            {
                "bundles": {
                    "core": {"description": "Core", "files": ["Makefile", "pyproject.toml"]},
                    "book": {"description": "Book", "files": ["docs/"]},
                    "tests": {"description": "Tests", "files": ["pytest.ini"], "requires": ["core"]},
                    "github": {"description": "GitHub", "files": [".github/workflows/ci.yml"], "requires": ["core"]},
                },
                "profiles": {
                    "local": {
                        "description": "Local-first development",
                        "bundles": ["core", "book", "tests"],
                    },
                    "github-project": {
                        "description": "Standard GitHub project",
                        "bundles": ["core", "github", "book", "tests"],
                    },
                },
            }
        )

    def test_profiles_parsed_from_config(self):
        """Profiles section is parsed into ProfileDefinition instances."""
        bundles = self._make_bundles_with_profiles()
        assert "local" in bundles.profiles
        assert "github-project" in bundles.profiles
        assert bundles.profiles["local"].description == "Local-first development"
        assert bundles.profiles["local"].bundles == ["core", "book", "tests"]

    def test_profiles_absent_gives_empty_dict(self):
        """When no profiles key is present, profiles is an empty dict."""
        bundles = RhizaBundles.from_config({"bundles": {"core": {"description": "Core"}}})
        assert bundles.profiles == {}

    def test_profile_entry_not_a_dict_raises_type_error(self):
        """TypeError raised when a profile entry is not a dict."""
        import pytest

        with pytest.raises(TypeError, match="Profile 'local' must be a dictionary"):
            RhizaBundles.from_config(
                {
                    "bundles": {},
                    "profiles": {"local": "not-a-dict"},
                }
            )

    def test_profiles_null_in_yaml_treated_as_empty(self):
        """profiles: null in YAML (None in Python) is coerced to an empty dict."""
        bundles = RhizaBundles.from_config({"bundles": {}, "profiles": None})
        assert bundles.profiles == {}

    def test_profiles_not_a_dict_raises_type_error(self):
        """TypeError raised when profiles value is not a dict."""
        import pytest

        with pytest.raises(TypeError, match="Profiles must be a dictionary"):
            RhizaBundles.from_config({"bundles": {}, "profiles": ["not", "a", "dict"]})

    def test_config_round_trips_profiles(self):
        """Profiles survive a config round-trip."""
        original = self._make_bundles_with_profiles()
        restored = RhizaBundles.from_config(original.config)
        assert restored.profiles["local"].bundles == original.profiles["local"].bundles
        assert restored.profiles["github-project"].description == original.profiles["github-project"].description

    def test_config_omits_profiles_when_empty(self):
        """Profiles key is absent from config output when there are no profiles."""
        bundles = RhizaBundles.from_config({"bundles": {"core": {"description": "Core"}}})
        assert "profiles" not in bundles.config

    def test_config_omits_description_when_empty(self):
        """Description is omitted from a profile entry when it is the empty string."""
        bundles = RhizaBundles.from_config(
            {
                "bundles": {"core": {"description": "Core", "files": ["Makefile"]}},
                "profiles": {"minimal": {"bundles": ["core"]}},
            }
        )
        assert "description" not in bundles.config["profiles"]["minimal"]


class TestBundleDefinitionNewFields:
    """Tests for the new BundleDefinition fields: required, recommends, notes."""

    def test_required_field_parsed(self):
        """required: true is parsed from config."""
        b = RhizaBundles.from_config({"bundles": {"core": {"description": "Core", "required": True}}})
        assert b.bundles["core"].required is True

    def test_required_defaults_to_false(self):
        """Required defaults to False when absent."""
        b = RhizaBundles.from_config({"bundles": {"core": {"description": "Core"}}})
        assert b.bundles["core"].required is False

    def test_recommends_parsed(self):
        """Recommends list is parsed from config."""
        b = RhizaBundles.from_config({"bundles": {"book": {"description": "Book", "recommends": ["tests", "marimo"]}}})
        assert b.bundles["book"].recommends == ["tests", "marimo"]

    def test_recommends_defaults_to_empty(self):
        """Recommends defaults to [] when absent."""
        b = RhizaBundles.from_config({"bundles": {"core": {"description": "Core"}}})
        assert b.bundles["core"].recommends == []

    def test_notes_parsed(self):
        """Notes string is parsed from config."""
        b = RhizaBundles.from_config({"bundles": {"core": {"description": "Core", "notes": "See readme"}}})
        assert b.bundles["core"].notes == "See readme"

    def test_notes_defaults_to_empty(self):
        """Notes defaults to empty string when absent."""
        b = RhizaBundles.from_config({"bundles": {"core": {"description": "Core"}}})
        assert b.bundles["core"].notes == ""

    def test_required_serialised_when_true(self):
        """required: True appears in config output."""
        b = RhizaBundles.from_config({"bundles": {"core": {"description": "Core", "required": True}}})
        assert b.config["bundles"]["core"]["required"] is True

    def test_recommends_serialised_when_present(self):
        """Recommends list appears in config output when non-empty."""
        b = RhizaBundles.from_config({"bundles": {"book": {"description": "Book", "recommends": ["tests"]}}})
        assert b.config["bundles"]["book"]["recommends"] == ["tests"]

    def test_notes_serialised_when_present(self):
        """Notes appears in config output when non-empty."""
        b = RhizaBundles.from_config({"bundles": {"core": {"description": "Core", "notes": "See readme"}}})
        assert b.config["bundles"]["core"]["notes"] == "See readme"

    def test_new_fields_round_trip(self):
        """New fields survive a config round-trip."""
        original = RhizaBundles.from_config(
            {
                "bundles": {
                    "core": {"description": "Core", "required": True},
                    "book": {"description": "Book", "recommends": ["tests"], "notes": "Needs marimo"},
                }
            }
        )
        restored = RhizaBundles.from_config(original.config)
        assert restored.bundles["core"].required is True
        assert restored.bundles["book"].recommends == ["tests"]
        assert restored.bundles["book"].notes == "Needs marimo"


class TestDirectoryBasedResolution:
    """Tests for bundles without explicit files resolved via bundles/<name>/ directories."""

    def _make_dir_bundles(self):
        return RhizaBundles.from_config(
            {
                "bundles": {
                    "core": {"description": "Core", "required": True, "standalone": True},
                    "tests": {"description": "Tests", "standalone": True, "requires": ["core"]},
                    "github-tests": {"description": "GitHub Tests", "standalone": True, "requires": ["tests"]},
                }
            }
        )

    def test_resolve_to_paths_returns_bundle_dirs(self):
        """Bundles without files resolve to bundles/<name>/ directory paths."""
        b = self._make_dir_bundles()
        result = b.resolve_to_paths(["core"])
        assert result == ["bundles/core/"]

    def test_resolve_to_paths_includes_transitive_deps(self):
        """Transitive requires are resolved to bundle directory paths."""
        b = self._make_dir_bundles()
        result = b.resolve_to_paths(["tests"])
        assert "bundles/core/" in result
        assert "bundles/tests/" in result

    def test_resolve_to_paths_deduplicates_dirs(self):
        """Each bundle directory appears only once even when shared across deps."""
        b = self._make_dir_bundles()
        result = b.resolve_to_paths(["github-tests", "tests"])
        assert result.count("bundles/core/") == 1
        assert result.count("bundles/tests/") == 1

    def test_resolve_to_path_map_returns_dir_prefix_to_root(self):
        """resolve_to_path_map maps bundles/<name>/ → '' for directory-based bundles."""
        b = self._make_dir_bundles()
        path_map = b.resolve_to_path_map(["core"])
        assert path_map == {"bundles/core/": ""}

    def test_resolve_to_path_map_covers_all_resolved_bundles(self):
        """path_map includes an entry for every bundle in the resolved set."""
        b = self._make_dir_bundles()
        path_map = b.resolve_to_path_map(["tests"])
        assert "bundles/core/" in path_map
        assert "bundles/tests/" in path_map
        assert all(v == "" for v in path_map.values())

    def test_mixed_format_explicit_files_bundle_uses_paths(self):
        """A bundle with explicit files still uses the old path-based resolution."""
        b = RhizaBundles.from_config(
            {
                "bundles": {
                    "core": {"description": "Core", "files": ["Makefile", "pyproject.toml"]},
                    "tests": {"description": "Tests", "requires": ["core"]},
                }
            }
        )
        result = b.resolve_to_paths(["tests"])
        assert "Makefile" in result
        assert "pyproject.toml" in result
        assert "bundles/tests/" in result

    def test_mixed_format_path_map_blends_old_and_new(self):
        """path_map mixes explicit remaps (old) with dir prefix (new)."""
        b = RhizaBundles.from_config(
            {
                "bundles": {
                    "core": {
                        "description": "Core",
                        "files": [{"source": ".rhiza/stubs/ci.yml", "dest": ".github/workflows/ci.yml"}],
                    },
                    "tests": {"description": "Tests", "requires": ["core"]},
                }
            }
        )
        path_map = b.resolve_to_path_map(["tests"])
        assert path_map[".rhiza/stubs/ci.yml"] == ".github/workflows/ci.yml"
        assert path_map["bundles/tests/"] == ""


class TestBundleFileEntry:
    """Tests for BundleFileEntry parsing and path remapping."""

    def test_string_entry_source_equals_dest(self):
        """A plain string entry has source == dest."""
        from rhiza.models.bundle import BundleFileEntry

        entry = BundleFileEntry.from_config_entry("Makefile")
        assert entry.source == "Makefile"
        assert entry.dest == "Makefile"
        assert not entry.is_remapped

    def test_dict_entry_with_dest(self):
        """A dict entry with source and dest is parsed correctly."""
        from rhiza.models.bundle import BundleFileEntry

        entry = BundleFileEntry.from_config_entry(
            {"source": ".rhiza/stubs/workflows/ci.yml", "dest": ".github/workflows/ci.yml"}
        )
        assert entry.source == ".rhiza/stubs/workflows/ci.yml"
        assert entry.dest == ".github/workflows/ci.yml"
        assert entry.is_remapped

    def test_dict_entry_without_dest_falls_back_to_source(self):
        """A dict entry with only source defaults dest to source."""
        from rhiza.models.bundle import BundleFileEntry

        entry = BundleFileEntry.from_config_entry({"source": "Makefile"})
        assert entry.dest == "Makefile"
        assert not entry.is_remapped

    def test_dict_entry_missing_source_raises(self):
        """TypeError raised when dict entry has no source key."""
        import pytest

        from rhiza.models.bundle import BundleFileEntry

        with pytest.raises(TypeError, match="source"):
            BundleFileEntry.from_config_entry({"dest": "Makefile"})

    def test_to_config_entry_plain_string_roundtrip(self):
        """Non-remapped entry serialises back to a plain string."""
        from rhiza.models.bundle import BundleFileEntry

        entry = BundleFileEntry.from_config_entry("Makefile")
        assert entry.to_config_entry() == "Makefile"

    def test_to_config_entry_remapped_roundtrip(self):
        """Remapped entry serialises back to a dict."""
        from rhiza.models.bundle import BundleFileEntry

        raw = {"source": ".rhiza/stubs/workflows/ci.yml", "dest": ".github/workflows/ci.yml"}
        entry = BundleFileEntry.from_config_entry(raw)
        assert entry.to_config_entry() == raw

    def test_remap_exact_file(self):
        """remap_expanded_path maps an exact file path."""
        from rhiza.models.bundle import BundleFileEntry

        entry = BundleFileEntry.from_config_entry({"source": ".rhiza/stubs/ci.yml", "dest": ".github/workflows/ci.yml"})
        assert entry.remap_expanded_path(".rhiza/stubs/ci.yml") == ".github/workflows/ci.yml"

    def test_remap_directory_prefix(self):
        """remap_expanded_path applies prefix substitution for directory entries."""
        from rhiza.models.bundle import BundleFileEntry

        entry = BundleFileEntry.from_config_entry({"source": ".rhiza/stubs/workflows", "dest": ".github/workflows"})
        assert entry.remap_expanded_path(".rhiza/stubs/workflows/ci.yml") == ".github/workflows/ci.yml"

    def test_remap_non_matching_path_unchanged(self):
        """remap_expanded_path returns the source unchanged when it doesn't match."""
        from rhiza.models.bundle import BundleFileEntry

        entry = BundleFileEntry.from_config_entry({"source": ".rhiza/stubs/ci.yml", "dest": ".github/workflows/ci.yml"})
        assert entry.remap_expanded_path("other/file.yml") == "other/file.yml"

    def test_remap_non_remapped_entry_returns_expanded_source(self):
        """remap_expanded_path returns expanded_source unchanged for non-remapped entries."""
        from rhiza.models.bundle import BundleFileEntry

        entry = BundleFileEntry.from_config_entry("Makefile")
        assert entry.remap_expanded_path("Makefile") == "Makefile"


class TestResolveToPathsWithRemappedEntries:
    """Tests for resolve_to_paths and resolve_to_path_map with remapped files."""

    def _make_bundles(self):
        return RhizaBundles.from_config(
            {
                "bundles": {
                    "core": {"description": "Core", "files": ["Makefile"]},
                    "github-ci": {
                        "description": "CI workflows",
                        "requires": ["core"],
                        "files": [
                            {
                                "source": ".rhiza/stubs/workflows/rhiza_ci.yml",
                                "dest": ".github/workflows/rhiza_ci.yml",
                            }
                        ],
                    },
                }
            }
        )

    def test_resolve_to_paths_returns_source_paths(self):
        """resolve_to_paths returns source paths (used for sparse checkout)."""
        bundles = self._make_bundles()
        result = bundles.resolve_to_paths(["github-ci"])
        assert ".rhiza/stubs/workflows/rhiza_ci.yml" in result
        assert ".github/workflows/rhiza_ci.yml" not in result

    def test_resolve_to_path_map_returns_remapped_entries_only(self):
        """resolve_to_path_map only includes entries where source != dest."""
        bundles = self._make_bundles()
        path_map = bundles.resolve_to_path_map(["github-ci"])
        assert path_map == {".rhiza/stubs/workflows/rhiza_ci.yml": ".github/workflows/rhiza_ci.yml"}
        assert "Makefile" not in path_map

    def test_resolve_to_path_map_empty_when_no_remapping(self):
        """resolve_to_path_map is empty when no entries are remapped."""
        bundles = self._make_bundles()
        assert bundles.resolve_to_path_map(["core"]) == {}

    def test_config_round_trips_remapped_files(self):
        """Remapped file entries survive a config round-trip."""
        bundles = self._make_bundles()
        restored = RhizaBundles.from_config(bundles.config)
        entry = restored.bundles["github-ci"].files[0]
        assert entry.source == ".rhiza/stubs/workflows/rhiza_ci.yml"
        assert entry.dest == ".github/workflows/rhiza_ci.yml"

    def test_resolve_to_path_map_with_shared_dependency(self):
        """resolve_to_path_map deduplicates bundles that share a common dependency."""
        bundles = RhizaBundles.from_config(
            {
                "bundles": {
                    "core": {"description": "Core", "files": ["Makefile"]},
                    "tests": {"description": "Tests", "requires": ["core"], "files": ["pytest.ini"]},
                    "ci": {
                        "description": "CI",
                        "requires": ["core"],
                        "files": [{"source": ".rhiza/stubs/ci.yml", "dest": ".github/workflows/ci.yml"}],
                    },
                }
            }
        )
        # Both tests and ci require core; the shared-dep guard (name in seen) is exercised.
        path_map = bundles.resolve_to_path_map(["tests", "ci"])
        assert path_map == {".rhiza/stubs/ci.yml": ".github/workflows/ci.yml"}


class TestResolveProfileToPaths:
    """Tests for RhizaBundles.resolve_profile_to_paths."""

    def _make_bundles(self):
        return RhizaBundles.from_config(
            {
                "bundles": {
                    "core": {"description": "Core", "files": ["Makefile", "pyproject.toml"]},
                    "book": {"description": "Book", "files": ["docs/"]},
                    "tests": {"description": "Tests", "files": ["pytest.ini"], "requires": ["core"]},
                    "github": {"description": "GitHub", "files": [".github/workflows/ci.yml"], "requires": ["core"]},
                },
                "profiles": {
                    "local": {"description": "Local", "bundles": ["core", "book", "tests"]},
                    "github-project": {"bundles": ["core", "github", "book", "tests"]},
                },
            }
        )

    def test_resolve_profile_returns_correct_paths(self):
        """resolve_profile_to_paths returns all paths for bundles in the profile."""
        bundles = self._make_bundles()
        result = bundles.resolve_profile_to_paths("local")
        assert "Makefile" in result
        assert "pyproject.toml" in result
        assert "docs/" in result
        assert "pytest.ini" in result
        assert ".github/workflows/ci.yml" not in result

    def test_resolve_profile_deduplicates_paths(self):
        """Paths shared across bundles appear only once."""
        bundles = self._make_bundles()
        result = bundles.resolve_profile_to_paths("github-project")
        assert result.count("Makefile") == 1
        assert result.count("pyproject.toml") == 1

    def test_resolve_profile_raises_for_nonexistent_profile(self):
        """ValueError raised when the requested profile does not exist."""
        import pytest

        bundles = self._make_bundles()
        with pytest.raises(ValueError, match="Profile 'unknown' does not exist"):
            bundles.resolve_profile_to_paths("unknown")

    def test_resolve_profile_resolves_bundle_dependencies(self):
        """Bundles in a profile have their requires resolved transitively."""
        bundles = self._make_bundles()
        result = bundles.resolve_profile_to_paths("github-project")
        # github requires core; core files must appear
        assert "pyproject.toml" in result
        assert ".github/workflows/ci.yml" in result
