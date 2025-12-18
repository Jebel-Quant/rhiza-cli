"""Tests for rhiza CLI commands and entry points.

This module tests:
- The __main__.py entry point
- The cli.py Typer app and command wrappers
- The inject/materialize commands
"""

import subprocess
import sys

import pytest
import typer

from rhiza import __version__
from rhiza.cli import version_callback
from rhiza.commands.materialize import __expand_paths


class TestCliApp:
    """Tests for the CLI Typer app."""

    def test_version_flag(self):
        """Test that --version flag shows version information."""
        result = subprocess.run(
            [sys.executable, "-m", "rhiza", "--version"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "rhiza version" in result.stdout
        assert __version__ in result.stdout

    def test_version_short_flag(self):
        """Test that -v flag shows version information."""
        result = subprocess.run(
            [sys.executable, "-m", "rhiza", "-v"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "rhiza version" in result.stdout
        assert __version__ in result.stdout

    def test_version_callback_with_true(self, capsys):
        """Test that version_callback prints version and exits when value is True."""
        # When version_callback is called with True, it should print version and exit
        with pytest.raises(typer.Exit):
            version_callback(True)

        # Capture the output
        captured = capsys.readouterr()
        assert f"rhiza version {__version__}" in captured.out

    def test_version_callback_with_false(self):
        """Test that version_callback does nothing when value is False."""
        # When version_callback is called with False, it should do nothing
        # and not raise an exception
        version_callback(False)  # Should not raise


class TestMainEntry:
    """Tests for the __main__.py entry point."""

    def test_main_entry_point(self):
        """Test that the module can be run with python -m rhiza."""
        # Test that the module is executable
        result = subprocess.run([sys.executable, "-m", "rhiza", "--help"], capture_output=True, text=True)
        assert result.returncode == 0
        assert "rhiza" in result.stdout.lower()

    def test_main_block_coverage(self, capsys):
        """Test the __main__ block to achieve coverage."""
        # Execute the __main__ module code directly to get coverage
        # This simulates what happens when python -m rhiza is run
        import runpy

        original_argv = sys.argv[:]
        try:
            # Set up argv for help command
            sys.argv = ["rhiza", "--help"]

            # Execute the module as __main__ to trigger the if __name__ == "__main__": block
            try:
                runpy.run_module("rhiza.__main__", run_name="__main__")
            except SystemExit as e:
                # Typer may call sys.exit(0) on success
                assert e.code == 0 or e.code is None

            # Verify we get help output
            captured = capsys.readouterr()
            assert "rhiza" in captured.out.lower()
        finally:
            sys.argv = original_argv
