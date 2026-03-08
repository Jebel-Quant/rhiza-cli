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
