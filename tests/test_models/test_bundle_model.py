"""Tests for the RhizaBundles dataclass.

This module verifies that RhizaBundles correctly deserialises
template-bundles.yml files, and satisfies the YamlSerializable protocol.
"""

from rhiza.models._base import YamlSerializable, load_model
from rhiza.models.bundle import RhizaBundles, _flatten_files

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
        """Files and workflows keys are omitted when empty."""
        bundles = RhizaBundles.from_config({"bundles": {"core": {"description": "Core"}}})
        entry = bundles.config["bundles"]["core"]
        assert "files" not in entry
        assert "workflows" not in entry

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


# ---------------------------------------------------------------------------
# _flatten_files helper
# ---------------------------------------------------------------------------


class TestFlattenFiles:
    """Tests for the _flatten_files helper function."""

    def test_none_returns_empty_list(self):
        """None returns an empty list."""
        assert _flatten_files(None) == []

    def test_flat_list_unchanged(self):
        """A plain list of filenames is returned as-is."""
        assert _flatten_files(["aapl.parquet", "msft.parquet"]) == ["aapl.parquet", "msft.parquet"]

    def test_single_level_dict(self):
        """A single-level dict maps keys to folder prefixes."""
        result = _flatten_files({"config": ["model.yaml"]})
        assert result == ["config/model.yaml"]

    def test_two_level_nested_dict(self):
        """Two-level nesting produces concatenated path components."""
        result = _flatten_files({"data": {"prices": ["aapl.parquet", "msft.parquet"]}})
        assert result == ["data/prices/aapl.parquet", "data/prices/msft.parquet"]

    def test_multiple_top_level_keys(self):
        """Multiple top-level dict keys each produce their own path prefix."""
        result = _flatten_files(
            {
                "data": {
                    "prices": ["aapl.parquet", "msft.parquet"],
                    "futures": ["es.parquet", "nq.parquet"],
                },
                "config": ["model.yaml"],
            }
        )
        assert "data/prices/aapl.parquet" in result
        assert "data/prices/msft.parquet" in result
        assert "data/futures/es.parquet" in result
        assert "data/futures/nq.parquet" in result
        assert "config/model.yaml" in result
        assert len(result) == 5

    def test_string_value_treated_as_filename(self):
        """A bare string value under a dict key is treated as a single file."""
        result = _flatten_files({"config": "model.yaml"})
        assert result == ["config/model.yaml"]

    def test_empty_dict_returns_empty_list(self):
        """An empty dict produces no paths."""
        assert _flatten_files({}) == []

    def test_empty_list_returns_empty_list(self):
        """An empty list produces no paths."""
        assert _flatten_files([]) == []

    def test_unknown_type_returns_empty_list(self):
        """An unrecognized value type returns an empty list."""
        assert _flatten_files(42) == []


# ---------------------------------------------------------------------------
# Nested files format in from_config
# ---------------------------------------------------------------------------


class TestNestedFilesInFromConfig:
    """Tests for nested dict files format in RhizaBundles.from_config."""

    def test_nested_files_are_flattened(self):
        """Nested files dict is flattened to a list of paths."""
        bundles = RhizaBundles.from_config(
            {
                "bundles": {
                    "data": {
                        "description": "Data bundle",
                        "files": {
                            "data": {
                                "prices": ["aapl.parquet", "msft.parquet"],
                                "futures": ["es.parquet", "nq.parquet"],
                            },
                            "config": ["model.yaml"],
                        },
                    }
                }
            }
        )
        files = bundles.bundles["data"].files
        assert "data/prices/aapl.parquet" in files
        assert "data/prices/msft.parquet" in files
        assert "data/futures/es.parquet" in files
        assert "data/futures/nq.parquet" in files
        assert "config/model.yaml" in files
        assert len(files) == 5

    def test_flat_list_still_works(self):
        """Existing flat list format continues to work unchanged."""
        bundles = RhizaBundles.from_config(
            {"bundles": {"core": {"description": "Core", "files": ["Makefile", "pyproject.toml"]}}}
        )
        assert bundles.bundles["core"].files == ["Makefile", "pyproject.toml"]

    def test_nested_files_resolve_to_paths(self):
        """resolve_to_paths works correctly with paths flattened from nested format."""
        bundles = RhizaBundles.from_config(
            {
                "bundles": {
                    "quant": {
                        "description": "Quant bundle",
                        "files": {
                            "data": {"prices": ["aapl.parquet"]},
                        },
                    }
                }
            }
        )
        paths = bundles.resolve_to_paths(["quant"])
        assert paths == ["data/prices/aapl.parquet"]

    def test_nested_files_round_trip_via_config(self):
        """After flattening, round-trip through config preserves the flat paths."""
        original = RhizaBundles.from_config(
            {
                "bundles": {
                    "data": {
                        "description": "Data bundle",
                        "files": {"data": {"prices": ["aapl.parquet"]}},
                    }
                }
            }
        )
        # Serialise and re-parse: flat list is stored and emitted as flat list
        restored = RhizaBundles.from_config(original.config)
        assert restored.bundles["data"].files == ["data/prices/aapl.parquet"]
