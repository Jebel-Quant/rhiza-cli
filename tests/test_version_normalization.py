"""Tests for PEP 440 version normalization used in the release pipeline.

The release workflow compares the project version (from `uv version --short`,
which returns PEP 440 normalized versions) with the git tag. Pre-release
tags like "v0.11.1-beta.1" must be normalized to PEP 440 format ("0.11.1b1")
before comparison.

This module validates that the normalization logic works correctly for
all pre-release version formats we support.
"""

import pytest
from packaging.version import Version


class TestPEP440Normalization:
    """Tests for PEP 440 version normalization of git tag versions."""

    @pytest.mark.parametrize(
        ("tag_version", "expected"),
        [
            # Beta pre-releases
            ("0.11.1-beta.1", "0.11.1b1"),
            ("1.0.0-beta.2", "1.0.0b2"),
            # Alpha pre-releases
            ("1.0.0-alpha.1", "1.0.0a1"),
            ("2.0.0-alpha.3", "2.0.0a3"),
            # Release candidates
            ("1.0.0-rc.1", "1.0.0rc1"),
            ("3.2.1-rc.2", "3.2.1rc2"),
            # Stable releases (no change expected)
            ("1.0.0", "1.0.0"),
            ("0.11.1", "0.11.1"),
            # Dev releases
            ("1.2.3.dev4", "1.2.3.dev4"),
            # Post releases
            ("1.2.3.post1", "1.2.3.post1"),
        ],
    )
    def test_tag_version_normalizes_to_pep440(self, tag_version: str, expected: str):
        """Verify that tag versions normalize to expected PEP 440 format.

        This mirrors the normalization done in .github/workflows/rhiza_release.yml:
            python3 -c "from packaging.version import Version; print(Version('$TAG_VERSION'))"
        """
        assert str(Version(tag_version)) == expected
