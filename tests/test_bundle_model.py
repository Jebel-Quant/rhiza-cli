"""Tests for the RhizaBundles dataclass.

This module verifies that RhizaBundles correctly serialises and deserialises
template-bundles.yml files, and satisfies the YamlSerializable protocol.
"""

from rhiza.models._base import YamlSerializable, load_model
from rhiza.models.bundle import RhizaBundles

# ---------------------------------------------------------------------------
# YamlSerializable Protocol — bundle-related check
# ---------------------------------------------------------------------------


class TestYamlSerializableProtocol:
    """Tests for the YamlSerializable Protocol as it applies to RhizaBundles."""

    def test_rhiza_bundles_satisfies_protocol(self, write_yaml):
        """RhizaBundles is a runtime-checkable instance of YamlSerializable."""
        bundles_file = write_yaml(
            "template-bundles.yml",
            {"bundles": {"core": {"description": "Core"}}},
        )
        bundles = RhizaBundles.from_yaml(bundles_file)
        assert isinstance(bundles, YamlSerializable)


# ---------------------------------------------------------------------------
# load_model helper — bundle-related checks
# ---------------------------------------------------------------------------


class TestLoadModel:
    """Tests for the load_model generic helper as it applies to RhizaBundles."""

    def test_load_model_returns_rhiza_bundles(self, write_yaml):
        """load_model loads a RhizaBundles and returns the correct type/values."""
        bundles_file = write_yaml(
            "template-bundles.yml",
            {
                "version": "1",
                "bundles": {"core": {"description": "Core bundle", "files": ["Makefile"]}},
            },
        )

        result = load_model(RhizaBundles, bundles_file)

        assert isinstance(result, RhizaBundles)
        assert result.version == "1"
        assert "core" in result.bundles

    def test_rhiza_bundles_to_yaml_round_trip(self, tmp_path):
        """RhizaBundles.to_yaml followed by from_yaml preserves bundle data."""
        from rhiza.models.bundle import BundleDefinition

        original = RhizaBundles(
            version="2",
            bundles={
                "core": BundleDefinition(
                    name="core",
                    description="Core files",
                    files=["Makefile", "pyproject.toml"],
                    workflows=[".github/workflows/ci.yml"],
                    depends_on=[],
                )
            },
        )
        out_path = tmp_path / "template-bundles.yml"
        original.to_yaml(out_path)
        loaded = RhizaBundles.from_yaml(out_path)

        assert loaded.version == "2"
        assert "core" in loaded.bundles
        assert loaded.bundles["core"].description == "Core files"
        assert loaded.bundles["core"].files == ["Makefile", "pyproject.toml"]
        assert loaded.bundles["core"].workflows == [".github/workflows/ci.yml"]
