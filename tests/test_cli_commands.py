"""Tests for rhiza CLI commands and entry points.

This module tests:
- The __main__.py entry point
- The cli.py Typer app and command wrappers
- The inject/materialize commands
"""

import subprocess
import sys

from rhiza.commands.materialize import expand_paths


class TestCliApp:
    """Tests for the CLI Typer app."""


class TestExpandPaths:
    """Tests for the expand_paths utility function."""

    def test_expand_single_file(self, tmp_path):
        """Test expanding a single file path."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        result = expand_paths(tmp_path, ["test.txt"])
        assert result == [test_file]

    def test_expand_directory(self, tmp_path):
        """Test expanding a directory into all its files."""
        test_dir = tmp_path / "dir"
        test_dir.mkdir()
        file1 = test_dir / "file1.txt"
        file2 = test_dir / "file2.txt"
        file1.write_text("content1")
        file2.write_text("content2")

        result = expand_paths(tmp_path, ["dir"])
        assert len(result) == 2
        assert file1 in result
        assert file2 in result

    def test_expand_nested_directory(self, tmp_path):
        """Test expanding a directory with nested subdirectories."""
        test_dir = tmp_path / "dir"
        sub_dir = test_dir / "subdir"
        sub_dir.mkdir(parents=True)
        file1 = test_dir / "file1.txt"
        file2 = sub_dir / "file2.txt"
        file1.write_text("content1")
        file2.write_text("content2")

        result = expand_paths(tmp_path, ["dir"])
        assert len(result) == 2
        assert file1 in result
        assert file2 in result

    def test_expand_nonexistent_path(self, tmp_path):
        """Test that nonexistent paths are skipped."""
        result = expand_paths(tmp_path, ["nonexistent.txt"])
        assert result == []

    def test_expand_mixed_paths(self, tmp_path):
        """Test expanding a mix of files and directories."""
        file1 = tmp_path / "file1.txt"
        file1.write_text("content1")

        test_dir = tmp_path / "dir"
        test_dir.mkdir()
        file2 = test_dir / "file2.txt"
        file2.write_text("content2")

        result = expand_paths(tmp_path, ["file1.txt", "dir"])
        assert len(result) == 2
        assert file1 in result
        assert file2 in result


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
