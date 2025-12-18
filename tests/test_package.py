"""Tests for the rhiza package initialization.

This module tests:
- Version detection from package metadata
- Fallback version when package is not installed
"""

import sys
from importlib.metadata import PackageNotFoundError
from unittest.mock import patch


class TestPackageInit:
    """Tests for package initialization and version handling."""

    def test_version_is_available(self):
        """Test that __version__ is available when package is installed."""
        # Import rhiza to get the version
        import rhiza

        assert hasattr(rhiza, "__version__")
        assert isinstance(rhiza.__version__, str)
        # Version should follow semantic versioning (e.g., "0.5.3" or "0.0.0+dev")
        assert rhiza.__version__.count(".") >= 2

    def test_version_fallback_when_not_installed(self):
        """Test that __version__ falls back to 0.0.0+dev when package is not found."""
        # We need to test the exception handling in __init__.py
        # To do this, we patch the version function at import time
        # Remove rhiza from sys.modules to force reimport
        if "rhiza" in sys.modules:
            del sys.modules["rhiza"]

        try:
            # Patch version to raise PackageNotFoundError
            with patch("importlib.metadata.version", side_effect=PackageNotFoundError):
                # Import rhiza - this should trigger the fallback
                import rhiza as test_rhiza

                # The version should be the fallback
                assert test_rhiza.__version__ == "0.0.0+dev"
        finally:
            # Clean up and re-import normally for other tests
            if "rhiza" in sys.modules:
                del sys.modules["rhiza"]

    def test_all_exports(self):
        """Test that __all__ contains expected exports."""
        import rhiza

        assert hasattr(rhiza, "__all__")
        assert "commands" in rhiza.__all__
        assert "models" in rhiza.__all__
