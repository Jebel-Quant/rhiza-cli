"""Tests for rhiza CLI commands and entry points.

This module tests:
- The __main__.py entry point
- The cli.py Typer app and command wrappers
- The inject/materialize commands
"""

import shutil
import subprocess
import sys

import pytest
import typer

from rhiza import __version__
from rhiza.cli import version_callback


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
                assert e.code == 0 or e.code is None  # noqa: PT017

            # Verify we get help output
            captured = capsys.readouterr()
            assert "rhiza" in captured.out.lower()
        finally:
            sys.argv = original_argv

    def test_load_plugins_with_error(self, capsys, monkeypatch):
        """Test plugin loading handles exceptions gracefully."""
        from unittest.mock import MagicMock

        import typer

        # Create a mock entry point that raises an exception
        mock_entry = MagicMock()
        mock_entry.name = "bad_plugin"
        mock_entry.load.side_effect = RuntimeError("Plugin load failed")

        # Create a mock entry_points function that returns our failing entry
        def mock_entry_points(group):
            if group == "rhiza.plugins":
                return [mock_entry]
            return []

        # Patch the entry_points function in the __main__ module
        monkeypatch.setattr("rhiza.__main__.entry_points", mock_entry_points)

        # Create a test app
        test_app = typer.Typer()

        # Import and call load_plugins directly
        from rhiza.__main__ import load_plugins

        load_plugins(test_app)

        # Verify the error message was printed
        captured = capsys.readouterr()
        assert "Failed to load plugin bad_plugin" in captured.out

    def test_load_plugins_successfully(self, monkeypatch):
        """Test plugin loading works with a valid plugin."""
        from unittest.mock import MagicMock

        import typer

        # Create a mock plugin app
        mock_plugin_app = typer.Typer()

        # Create a mock entry point that loads successfully
        mock_entry = MagicMock()
        mock_entry.name = "good_plugin"
        mock_entry.load.return_value = mock_plugin_app

        # Create a mock entry_points function that returns our successful entry
        def mock_entry_points(group):
            if group == "rhiza.plugins":
                return [mock_entry]
            return []

        # Patch the entry_points function in the __main__ module
        monkeypatch.setattr("rhiza.__main__.entry_points", mock_entry_points)

        # Create a test app with a mock add_typer method
        test_app = typer.Typer()
        add_typer_mock = MagicMock()
        test_app.add_typer = add_typer_mock

        # Import and call load_plugins directly
        from rhiza.__main__ import load_plugins

        load_plugins(test_app)

        # Verify add_typer was called with the plugin app
        add_typer_mock.assert_called_once_with(mock_plugin_app, name="good_plugin")


class TestWelcomeCommand:
    """Tests for the welcome command."""

    def test_welcome_command(self, capsys):
        """Test that the welcome command displays welcome message."""
        result = subprocess.run(
            [sys.executable, "-m", "rhiza", "welcome"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        output = result.stdout

        # Check for key elements of the welcome message
        assert "Welcome to Rhiza" in output
        assert __version__ in output
        assert "What Rhiza can do" in output
        assert "Getting started" in output
        assert "rhiza init" in output
        assert "rhiza materialize" in output

    def test_welcome_command_function_coverage(self, capsys):
        """Test the welcome command function directly for coverage."""
        from rhiza.commands.welcome import welcome

        welcome()

        captured = capsys.readouterr()
        assert "Welcome to Rhiza" in captured.out
        assert __version__ in captured.out

    def test_welcome_cli_wrapper_coverage(self, capsys):
        """Test the CLI welcome command wrapper directly for coverage."""
        from typer.testing import CliRunner

        from rhiza.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["welcome"])

        assert result.exit_code == 0
        assert "Welcome to Rhiza" in result.stdout
        assert __version__ in result.stdout


class TestSummariseCommand:
    """Tests for the summarise command."""

    def test_summarise_help(self):
        """Test that summarise command help is available."""
        result = subprocess.run(
            [sys.executable, "-m", "rhiza", "summarise", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "Generate a summary of staged changes" in result.stdout
        assert "output" in result.stdout.lower()

    def test_summarise_cli_wrapper_coverage(self, tmp_path):
        """Test the CLI summarise command wrapper directly for coverage."""
        from typer.testing import CliRunner

        from rhiza.cli import app

        # Create a temporary git repo
        repo = tmp_path / "test_repo"
        repo.mkdir()
        git_cmd = shutil.which("git") or "git"
        subprocess.run([git_cmd, "init"], cwd=repo, check=True)
        subprocess.run([git_cmd, "config", "user.email", "test@test.com"], cwd=repo, check=True)
        subprocess.run([git_cmd, "config", "user.name", "Test"], cwd=repo, check=True)

        # Create template.yml
        template_dir = repo / ".rhiza"
        template_dir.mkdir()
        template_file = template_dir / "template.yml"
        template_file.write_text('template-repository: "test/repo"\ntemplate-branch: "custom-branch"\n')

        # Create and stage a test file
        test_file = repo / "test.txt"
        test_file.write_text("test")
        subprocess.run([git_cmd, "add", "."], cwd=repo, check=True)

        runner = CliRunner()
        result = runner.invoke(app, ["summarise", str(repo)])

        assert result.exit_code == 0
        assert "Template Synchronization" in result.stdout
        assert "test/repo" in result.stdout
        assert "custom-branch" in result.stdout
        assert "files added" in result.stdout
