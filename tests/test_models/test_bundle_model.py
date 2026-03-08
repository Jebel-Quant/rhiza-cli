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

    def test_config_includes_files_and_workflows(self):
        """Files and workflows are included when present."""
        bundles = RhizaBundles.from_config(
            {
                "bundles": {
                    "ci": {
                        "description": "CI",
                        "files": ["Makefile"],
                        "workflows": [".github/workflows/ci.yml"],
                    }
                }
            }
        )
        entry = bundles.config["bundles"]["ci"]
        assert entry["files"] == ["Makefile"]
        assert entry["workflows"] == [".github/workflows/ci.yml"]

    def test_config_omits_empty_files_and_workflows(self):
        """Files and workflows keys are omitted when empty."""
        bundles = RhizaBundles.from_config({"bundles": {"core": {"description": "Core"}}})
        entry = bundles.config["bundles"]["core"]
        assert "files" not in entry
        assert "workflows" not in entry

    def test_config_includes_depends_on(self):
        """depends-on is included when present."""
        bundles = RhizaBundles.from_config(
            {
                "bundles": {
                    "extended": {
                        "description": "Extended",
                        "depends-on": ["core"],
                    }
                }
            }
        )
        assert bundles.config["bundles"]["extended"]["depends-on"] == ["core"]

    def test_config_omits_empty_depends_on(self):
        """depends-on key is omitted when the list is empty."""
        bundles = RhizaBundles.from_config({"bundles": {"core": {"description": "Core"}}})
        assert "depends-on" not in bundles.config["bundles"]["core"]

    def test_config_round_trips_through_from_config(self):
        """Config output can be fed back into from_config producing an equal object."""
        original = RhizaBundles.from_config(
            {
                "version": "1",
                "bundles": {
                    "core": {"description": "Core", "files": ["Makefile"]},
                    "ci": {"description": "CI", "workflows": [".github/workflows/ci.yml"], "depends-on": ["core"]},
                },
            }
        )
        restored = RhizaBundles.from_config(original.config)
        assert restored.version == original.version
        assert restored.bundles["core"].files == original.bundles["core"].files
        assert restored.bundles["ci"].depends_on == original.bundles["ci"].depends_on


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

    def test_resolves_single_bundle_no_deps(self):
        """Single bundle with no dependencies returns just that bundle."""
        bundles = self._make_bundles()
        assert bundles.resolve_dependencies(["core"]) == ["core"]

    def test_resolves_dependencies_in_order(self):
        """Dependencies appear before the bundle that requires them."""
        bundles = self._make_bundles()
        result = bundles.resolve_dependencies(["tests"])
        assert result.index("core") < result.index("tests")

    def test_deduplicates_shared_dependencies(self):
        """A shared dependency is not repeated when multiple bundles require it."""
        bundles = self._make_bundles()
        result = bundles.resolve_dependencies(["tests", "ci"])
        assert result.count("core") == 1

    def test_unknown_bundle_raises_value_error(self):
        """ValueError raised when a requested bundle does not exist."""
        import pytest

        bundles = self._make_bundles()
        with pytest.raises(ValueError, match="Bundle 'missing' not found"):
            bundles.resolve_dependencies(["missing"])

    def test_circular_dependency_raises_value_error(self):
        """ValueError raised when a circular dependency is detected."""
        import pytest

        bundles = RhizaBundles.from_config(
            {
                "bundles": {
                    "a": {"description": "A", "depends-on": ["b"]},
                    "b": {"description": "B", "depends-on": ["a"]},
                }
            }
        )
        with pytest.raises(ValueError, match="Circular dependency detected"):
            bundles.resolve_dependencies(["a"])

    def test_unknown_dependency_raises_value_error(self):
        """ValueError raised when a bundle depends on an unknown bundle."""
        import pytest

        bundles = RhizaBundles.from_config(
            {
                "bundles": {
                    "a": {"description": "A", "depends-on": ["nonexistent"]},
                }
            }
        )
        with pytest.raises(ValueError, match="depends on unknown bundle 'nonexistent'"):
            bundles.resolve_dependencies(["a"])


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
                        "workflows": [".github/workflows/ci.yml"],
                        "files": ["Makefile"],
                        "depends-on": ["core"],
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

    def test_includes_workflow_paths(self):
        """Workflow paths are included in the result."""
        bundles = self._make_bundles()
        result = bundles.resolve_to_paths(["ci"])
        assert ".github/workflows/ci.yml" in result
