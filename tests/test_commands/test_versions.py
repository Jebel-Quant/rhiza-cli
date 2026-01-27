"""Tests for the versions command and CLI wiring.

This module verifies that the versions command correctly extracts supported
Python versions from pyproject.toml files.
"""

import tomllib

import pytest
from typer.testing import CliRunner

from rhiza import cli
from rhiza.commands.versions import (
    parse_version,
    satisfies,
    supported_versions,
    versions,
)

runner = CliRunner()


class TestParseVersion:
    """Tests for parse_version function."""

    def test_simple_version(self):
        """Parse simple version strings."""
        assert parse_version("3.11") == (3, 11)
        assert parse_version("3.12") == (3, 12)
        assert parse_version("3.14") == (3, 14)

    def test_three_part_version(self):
        """Parse three-part version strings."""
        assert parse_version("3.11.0") == (3, 11, 0)
        assert parse_version("3.12.5") == (3, 12, 5)

    def test_version_with_rc_suffix(self):
        """Parse version with release candidate suffix."""
        assert parse_version("3.11.0rc1") == (3, 11, 0)
        assert parse_version("3.14.0a1") == (3, 14, 0)
        assert parse_version("3.13.0b2") == (3, 13, 0)

    def test_malformed_version(self):
        """Raise ValueError for malformed version."""
        with pytest.raises(ValueError, match="Invalid version component"):
            parse_version("abc.11")


class TestSatisfies:
    """Tests for satisfies function."""

    def test_greater_than_or_equal(self):
        """Test >= operator."""
        assert satisfies("3.11", ">=3.11") is True
        assert satisfies("3.12", ">=3.11") is True
        assert satisfies("3.10", ">=3.11") is False

    def test_less_than(self):
        """Test < operator."""
        assert satisfies("3.10", "<3.11") is True
        assert satisfies("3.11", "<3.11") is False
        assert satisfies("3.12", "<3.11") is False

    def test_less_than_or_equal(self):
        """Test <= operator."""
        assert satisfies("3.10", "<=3.11") is True
        assert satisfies("3.11", "<=3.11") is True
        assert satisfies("3.12", "<=3.11") is False

    def test_greater_than(self):
        """Test > operator."""
        assert satisfies("3.12", ">3.11") is True
        assert satisfies("3.11", ">3.11") is False
        assert satisfies("3.10", ">3.11") is False

    def test_equal(self):
        """Test == operator."""
        assert satisfies("3.11", "==3.11") is True
        assert satisfies("3.12", "==3.11") is False
        assert satisfies("3.10", "==3.11") is False

    def test_not_equal(self):
        """Test != operator."""
        assert satisfies("3.12", "!=3.11") is True
        assert satisfies("3.10", "!=3.11") is True
        assert satisfies("3.11", "!=3.11") is False

    def test_compound_specifier(self):
        """Test comma-separated specifiers."""
        assert satisfies("3.11", ">=3.11,<3.14") is True
        assert satisfies("3.12", ">=3.11,<3.14") is True
        assert satisfies("3.14", ">=3.11,<3.14") is False
        assert satisfies("3.10", ">=3.11,<3.14") is False

    def test_invalid_specifier(self):
        """Raise ValueError for invalid specifier."""
        with pytest.raises(ValueError, match="Invalid specifier"):
            satisfies("3.11", "~=3.11")


class TestSupportedVersions:
    """Tests for supported_versions function."""

    def test_supported_versions_with_valid_pyproject(self, tmp_path):
        """Test supported_versions with valid pyproject.toml."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nrequires-python = ">=3.11"\n')

        versions = supported_versions(pyproject)
        assert isinstance(versions, list)
        assert "3.11" in versions
        assert "3.12" in versions
        assert "3.13" in versions
        assert "3.14" in versions

    def test_supported_versions_with_upper_bound(self, tmp_path):
        """Test supported_versions with upper bound constraint."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nrequires-python = ">=3.12,<3.14"\n')

        versions = supported_versions(pyproject)
        assert "3.11" not in versions
        assert "3.12" in versions
        assert "3.13" in versions
        assert "3.14" not in versions

    def test_supported_versions_missing_requires_python(self, tmp_path):
        """Test supported_versions raises error when requires-python is missing."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\n')

        with pytest.raises(RuntimeError) as exc_info:
            supported_versions(pyproject)
        assert "missing 'project.requires-python'" in str(exc_info.value)

    def test_supported_versions_no_matching_versions(self, tmp_path):
        """Test supported_versions raises error when no candidates match."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nrequires-python = ">=2.7,<3.0"\n')

        with pytest.raises(RuntimeError) as exc_info:
            supported_versions(pyproject)
        assert "no supported Python versions match" in str(exc_info.value)

    def test_supported_versions_file_not_found(self, tmp_path):
        """Test supported_versions raises error when file doesn't exist."""
        pyproject = tmp_path / "nonexistent.toml"

        with pytest.raises(FileNotFoundError):
            supported_versions(pyproject)

    def test_supported_versions_malformed_toml(self, tmp_path):
        """Test supported_versions raises error for malformed TOML syntax."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project\nname = "test"')  # Missing closing bracket

        with pytest.raises(tomllib.TOMLDecodeError):
            supported_versions(pyproject)


class TestVersionsCommand:
    """Tests for the versions command."""

    def test_versions_with_directory(self, tmp_path):
        """Test versions command with directory argument."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nrequires-python = ">=3.11"\n')

        # Should not raise an error
        versions(tmp_path)

    def test_versions_with_pyproject_file(self, tmp_path):
        """Test versions command with pyproject.toml file argument."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nrequires-python = ">=3.11"\n')

        # Should not raise an error
        versions(pyproject)

    def test_versions_missing_pyproject(self, tmp_path):
        """Test versions command fails when pyproject.toml doesn't exist."""
        with pytest.raises(FileNotFoundError):
            versions(tmp_path)

    def test_versions_invalid_target(self, tmp_path):
        """Test versions command fails with invalid target."""
        invalid_file = tmp_path / "invalid.txt"
        invalid_file.write_text("content")

        with pytest.raises(ValueError, match="Invalid target"):
            versions(invalid_file)


class TestVersionsCLI:
    """Tests for the versions CLI command."""

    def test_versions_cli_success(self, tmp_path):
        """Test versions CLI command with valid pyproject.toml."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nrequires-python = ">=3.11"\n')

        result = runner.invoke(cli.app, ["versions", str(tmp_path)])
        assert result.exit_code == 0
        assert "3.11" in result.stdout or '"3.11"' in result.stdout

    def test_versions_cli_with_file_path(self, tmp_path):
        """Test versions CLI command with direct file path."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nrequires-python = ">=3.12"\n')

        result = runner.invoke(cli.app, ["versions", str(pyproject)])
        assert result.exit_code == 0
        assert "3.12" in result.stdout or '"3.12"' in result.stdout

    def test_versions_cli_default_directory(self):
        """Test versions CLI command with default directory (current)."""
        # This test assumes the test is run from a directory with a valid pyproject.toml
        result = runner.invoke(cli.app, ["versions"])
        # Should succeed if run from rhiza-cli root
        assert result.exit_code == 0

    def test_versions_cli_missing_pyproject(self, tmp_path):
        """Test versions CLI command fails when pyproject.toml is missing."""
        result = runner.invoke(cli.app, ["versions", str(tmp_path)])
        assert result.exit_code != 0

    def test_versions_cli_help(self):
        """Test versions CLI command help."""
        result = runner.invoke(cli.app, ["versions", "--help"])
        assert result.exit_code == 0
        assert "pyproject.toml" in result.stdout.lower()
        assert "versions" in result.stdout.lower()
