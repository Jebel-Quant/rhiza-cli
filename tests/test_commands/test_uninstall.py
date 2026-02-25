"""Tests for the `uninstall` command.

This module tests the uninstall command functionality, including:
- Reading .rhiza/template.lock file
- Removing files listed in .rhiza/template.lock
- Handling empty directories
- Confirmation prompts
- CLI integration
"""

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import yaml
from typer.testing import CliRunner

from rhiza.cli import app
from rhiza.commands.uninstall import uninstall


def _write_lock_file(lock_dir: Path, files: list[str]) -> Path:
    """Helper: write a template.lock YAML file with the given file list."""
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_file = lock_dir / "template.lock"
    lock_file.write_text(
        yaml.dump(
            {
                "sha": "abc123",
                "repo": "owner/repo",
                "host": "github",
                "ref": "main",
                "include": [],
                "exclude": [],
                "templates": [],
                "files": files,
            }
        )
    )
    return lock_file


class TestUninstallCommand:
    """Tests for the uninstall command implementation."""

    def test_uninstall_removes_files_listed_in_lock(self, tmp_path):
        """Test that uninstall removes all files listed in .rhiza/template.lock."""
        # Create some files
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "subdir" / "file2.txt"
        file3 = tmp_path / "another" / "deep" / "file3.txt"

        file1.parent.mkdir(parents=True, exist_ok=True)
        file2.parent.mkdir(parents=True, exist_ok=True)
        file3.parent.mkdir(parents=True, exist_ok=True)

        file1.write_text("content1")
        file2.write_text("content2")
        file3.write_text("content3")

        # Create .rhiza/template.lock
        lock_file = _write_lock_file(
            tmp_path / ".rhiza",
            ["file1.txt", "subdir/file2.txt", "another/deep/file3.txt"],
        )

        # Run uninstall with force=True to skip confirmation
        uninstall(tmp_path, force=True)

        # Verify files are removed
        assert not file1.exists()
        assert not file2.exists()
        assert not file3.exists()
        assert not lock_file.exists()

    def test_uninstall_removes_empty_directories(self, tmp_path):
        """Test that uninstall removes empty directories after deleting files."""
        # Create nested directory structure
        file1 = tmp_path / "dir1" / "dir2" / "file.txt"
        file1.parent.mkdir(parents=True, exist_ok=True)
        file1.write_text("content")

        # Create .rhiza/template.lock
        lock_file = _write_lock_file(tmp_path / ".rhiza", ["dir1/dir2/file.txt"])

        # Run uninstall
        uninstall(tmp_path, force=True)

        # Verify file and empty directories are removed
        assert not file1.exists()
        assert not (tmp_path / "dir1" / "dir2").exists()
        assert not (tmp_path / "dir1").exists()
        assert not lock_file.exists()

    def test_uninstall_preserves_non_empty_directories(self, tmp_path):
        """Test that uninstall preserves directories that still contain files."""
        # Create files, some managed by Rhiza, some not
        managed_file = tmp_path / "shared" / "managed.txt"
        unmanaged_file = tmp_path / "shared" / "unmanaged.txt"

        managed_file.parent.mkdir(parents=True, exist_ok=True)
        managed_file.write_text("managed")
        unmanaged_file.write_text("unmanaged")

        # Create .rhiza/template.lock with only one file
        lock_file = _write_lock_file(tmp_path / ".rhiza", ["shared/managed.txt"])

        # Run uninstall
        uninstall(tmp_path, force=True)

        # Verify managed file is removed but directory and unmanaged file remain
        assert not managed_file.exists()
        assert unmanaged_file.exists()
        assert (tmp_path / "shared").exists()
        assert not lock_file.exists()

    def test_uninstall_handles_missing_lock_file(self, tmp_path):
        """Test that uninstall handles gracefully when .rhiza/template.lock doesn't exist."""
        # Don't create any lock or history file
        uninstall(tmp_path, force=True)

        # Should complete without error
        assert True

    def test_uninstall_handles_empty_lock_file(self, tmp_path):
        """Test that uninstall handles template.lock with an empty files list."""
        # Create .rhiza/template.lock with files: []
        _write_lock_file(tmp_path / ".rhiza", [])

        # Run uninstall
        uninstall(tmp_path, force=True)

        # Should complete without error; lock file still exists (nothing to do)
        assert True

    def test_uninstall_handles_already_deleted_files(self, tmp_path):
        """Test that uninstall handles files that are already deleted."""
        # Create .rhiza/template.lock with files that don't exist
        lock_file = _write_lock_file(tmp_path / ".rhiza", ["nonexistent1.txt", "nonexistent2.txt"])

        # Run uninstall - should not raise an exception
        uninstall(tmp_path, force=True)

        # Lock file should be deleted
        assert not lock_file.exists()

    def test_uninstall_skips_confirmation_with_force(self, tmp_path):
        """Test that uninstall skips confirmation when force=True."""
        # Create a file
        file1 = tmp_path / "file.txt"
        file1.write_text("content")

        # Create .rhiza/template.lock
        _write_lock_file(tmp_path / ".rhiza", ["file.txt"])

        # Run uninstall with force=True (should not prompt)
        with patch("builtins.input") as mock_input:
            uninstall(tmp_path, force=True)
            # Verify input was never called
            mock_input.assert_not_called()

        # File should be removed
        assert not file1.exists()

    def test_uninstall_prompts_for_confirmation_without_force(self, tmp_path):
        """Test that uninstall prompts for confirmation when force=False."""
        # Create a file
        file1 = tmp_path / "file.txt"
        file1.write_text("content")

        # Create .rhiza/template.lock
        lock_file = _write_lock_file(tmp_path / ".rhiza", ["file.txt"])

        # Mock user input to confirm
        with patch("builtins.input", return_value="y"):
            uninstall(tmp_path, force=False)

        # File should be removed
        assert not file1.exists()
        assert not lock_file.exists()

    def test_uninstall_cancels_on_no_confirmation(self, tmp_path):
        """Test that uninstall cancels when user declines confirmation."""
        # Create a file
        file1 = tmp_path / "file.txt"
        file1.write_text("content")

        # Create .rhiza/template.lock
        lock_file = _write_lock_file(tmp_path / ".rhiza", ["file.txt"])

        # Mock user input to decline
        with patch("builtins.input", return_value="n"):
            uninstall(tmp_path, force=False)

        # Files should NOT be removed
        assert file1.exists()
        assert lock_file.exists()

    def test_uninstall_cancels_on_keyboard_interrupt(self, tmp_path):
        """Test that uninstall handles KeyboardInterrupt gracefully."""
        # Create a file
        file1 = tmp_path / "file.txt"
        file1.write_text("content")

        # Create .rhiza/template.lock
        lock_file = _write_lock_file(tmp_path / ".rhiza", ["file.txt"])

        # Mock user pressing Ctrl+C
        with patch("builtins.input", side_effect=KeyboardInterrupt):
            uninstall(tmp_path, force=False)

        # Files should NOT be removed
        assert file1.exists()
        assert lock_file.exists()

    def test_uninstall_legacy_history_fallback(self, tmp_path):
        """Test legacy fallback: uninstall reads .rhiza/history when no template.lock exists.

        When only .rhiza/history exists, files are removed but the history file
        is NOT deleted (uninstall only deletes template.lock).
        """
        # Create some files
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "subdir" / "file2.txt"

        file1.write_text("content1")
        file2.parent.mkdir(parents=True, exist_ok=True)
        file2.write_text("content2")

        # Create only .rhiza/history (no template.lock)
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True, exist_ok=True)
        history_file = rhiza_dir / "history"
        history_file.write_text(
            "# Rhiza Template History\n"
            "# This file lists all files managed by the Rhiza template.\n"
            "#\n"
            "file1.txt\n"
            "subdir/file2.txt\n"
        )

        # Run uninstall with force=True to skip confirmation
        uninstall(tmp_path, force=True)

        # Verify files are removed
        assert not file1.exists()
        assert not file2.exists()
        # history file is NOT deleted (uninstall only deletes template.lock)
        assert history_file.exists()


class TestUninstallCLI:
    """Tests for the uninstall CLI command."""

    def test_uninstall_cli_help(self):
        """Test that uninstall command has help text."""
        result = subprocess.run(
            [sys.executable, "-m", "rhiza", "uninstall", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "uninstall" in result.stdout.lower()
        assert "Remove all Rhiza-managed files" in result.stdout

    def test_uninstall_cli_with_force_flag(self, tmp_path):
        """Test uninstall CLI with --force flag."""
        # Create a file
        file1 = tmp_path / "file.txt"
        file1.write_text("content")

        # Create .rhiza/template.lock
        lock_file = _write_lock_file(tmp_path / ".rhiza", ["file.txt"])

        # Run CLI command with --force
        runner = CliRunner()
        result = runner.invoke(app, ["uninstall", str(tmp_path), "--force"])

        # Should succeed
        assert result.exit_code == 0
        assert not file1.exists()
        assert not lock_file.exists()

    def test_uninstall_cli_with_short_force_flag(self, tmp_path):
        """Test uninstall CLI with -y flag."""
        # Create a file
        file1 = tmp_path / "file.txt"
        file1.write_text("content")

        # Create .rhiza/template.lock
        lock_file = _write_lock_file(tmp_path / ".rhiza", ["file.txt"])

        # Run CLI command with -y
        runner = CliRunner()
        result = runner.invoke(app, ["uninstall", str(tmp_path), "-y"])

        # Should succeed
        assert result.exit_code == 0
        assert not file1.exists()
        assert not lock_file.exists()

    def test_uninstall_cli_defaults_to_current_directory(self, tmp_path, monkeypatch):
        """Test that uninstall defaults to current directory."""
        # Change to tmp_path
        monkeypatch.chdir(tmp_path)

        # Create a file
        file1 = tmp_path / "file.txt"
        file1.write_text("content")

        # Create .rhiza/template.lock
        lock_file = _write_lock_file(tmp_path / ".rhiza", ["file.txt"])

        # Run CLI command without target argument
        runner = CliRunner()
        result = runner.invoke(app, ["uninstall", "--force"])

        # Should succeed
        assert result.exit_code == 0
        assert not file1.exists()
        assert not lock_file.exists()

    def test_uninstall_cli_with_confirmation_yes(self, tmp_path):
        """Test uninstall CLI with interactive confirmation (yes)."""
        # Create a file
        file1 = tmp_path / "file.txt"
        file1.write_text("content")

        # Create .rhiza/template.lock
        lock_file = _write_lock_file(tmp_path / ".rhiza", ["file.txt"])

        # Run CLI command and simulate 'y' input
        runner = CliRunner()
        result = runner.invoke(app, ["uninstall", str(tmp_path)], input="y\n")

        # Should succeed
        assert result.exit_code == 0
        assert not file1.exists()
        assert not lock_file.exists()

    def test_uninstall_cli_with_confirmation_no(self, tmp_path):
        """Test uninstall CLI with interactive confirmation (no)."""
        # Create a file
        file1 = tmp_path / "file.txt"
        file1.write_text("content")

        # Create .rhiza/template.lock
        lock_file = _write_lock_file(tmp_path / ".rhiza", ["file.txt"])

        # Run CLI command and simulate 'n' input
        runner = CliRunner()
        result = runner.invoke(app, ["uninstall", str(tmp_path)], input="n\n")

        # Should succeed (but files not removed)
        assert result.exit_code == 0
        assert file1.exists()
        assert lock_file.exists()

    def test_uninstall_cli_integration_with_subprocess(self, tmp_path):
        """Test uninstall command via subprocess."""
        # Create a file
        file1 = tmp_path / "file.txt"
        file1.write_text("content")

        # Create .rhiza/template.lock
        lock_file = _write_lock_file(tmp_path / ".rhiza", ["file.txt"])

        # Run via subprocess with --force
        result = subprocess.run(
            [sys.executable, "-m", "rhiza", "uninstall", str(tmp_path), "--force"],
            capture_output=True,
            text=True,
        )

        # Should succeed
        assert result.returncode == 0
        assert not file1.exists()
        assert not lock_file.exists()


class TestUninstallEdgeCases:
    """Tests for edge cases in uninstall functionality."""

    def test_uninstall_with_special_characters_in_filename(self, tmp_path):
        """Test uninstall with files that have special characters."""
        # Create files with special characters
        file1 = tmp_path / "file with spaces.txt"
        file2 = tmp_path / "file-with-dashes.txt"
        file3 = tmp_path / "file_with_underscores.txt"

        file1.write_text("content1")
        file2.write_text("content2")
        file3.write_text("content3")

        # Create .rhiza/template.lock
        lock_file = _write_lock_file(
            tmp_path / ".rhiza",
            ["file with spaces.txt", "file-with-dashes.txt", "file_with_underscores.txt"],
        )

        # Run uninstall
        uninstall(tmp_path, force=True)

        # Verify all files are removed
        assert not file1.exists()
        assert not file2.exists()
        assert not file3.exists()
        assert not lock_file.exists()

    def test_uninstall_with_deeply_nested_paths(self, tmp_path):
        """Test uninstall with deeply nested directory structures."""
        # Create deeply nested file
        deep_file = tmp_path / "a" / "b" / "c" / "d" / "e" / "file.txt"
        deep_file.parent.mkdir(parents=True, exist_ok=True)
        deep_file.write_text("content")

        # Create .rhiza/template.lock
        lock_file = _write_lock_file(tmp_path / ".rhiza", ["a/b/c/d/e/file.txt"])

        # Run uninstall
        uninstall(tmp_path, force=True)

        # Verify file and all empty parent directories are removed
        assert not deep_file.exists()
        assert not (tmp_path / "a").exists()
        assert not lock_file.exists()

    def test_uninstall_preserves_dot_files(self, tmp_path):
        """Test that uninstall correctly handles dot files."""
        # Create dot files
        dotfile = tmp_path / ".hidden"
        dotfile.write_text("hidden content")

        # Create .rhiza/template.lock
        lock_file = _write_lock_file(tmp_path / ".rhiza", [".hidden"])

        # Run uninstall
        uninstall(tmp_path, force=True)

        # Verify dotfile is removed
        assert not dotfile.exists()
        assert not lock_file.exists()

    def test_uninstall_with_read_only_file(self, tmp_path):
        """Test uninstall behavior with read-only files.

        Note: On Unix, file permissions don't prevent deletion if you have
        write permission on the parent directory. This test verifies that
        read-only files are successfully deleted, which is the expected behavior.
        """
        # Create a file and make it read-only
        file1 = tmp_path / "readonly.txt"
        file1.write_text("content")
        file1.chmod(0o444)  # Read-only

        # Create .rhiza/template.lock
        lock_file = _write_lock_file(tmp_path / ".rhiza", ["readonly.txt"])

        # Run uninstall - should succeed even with read-only file
        uninstall(tmp_path, force=True)

        # Verify files are deleted (Unix allows deleting read-only files
        # if you have write permission on the directory)
        assert not file1.exists()
        assert not lock_file.exists()

    def test_uninstall_shows_missing_files_in_warning(self, tmp_path):
        """Test that uninstall shows debug message for missing files in warning phase."""
        # Create .rhiza/template.lock with files that don't exist
        lock_file = _write_lock_file(tmp_path / ".rhiza", ["nonexistent1.txt", "nonexistent2.txt"])

        # Run uninstall without force to trigger warning phase
        # Mock user input to decline
        with patch("builtins.input", return_value="n"):
            uninstall(tmp_path, force=False)

        # Lock file should still exist since user declined
        assert lock_file.exists()

    def test_uninstall_handles_file_deletion_error(self, tmp_path):
        """Test that uninstall handles file deletion errors gracefully."""
        import pytest

        # Create a file
        file1 = tmp_path / "file.txt"
        file1.write_text("content")

        # Create .rhiza/template.lock
        _write_lock_file(tmp_path / ".rhiza", ["file.txt"])

        # Mock Path.unlink to raise an exception for the file (but not lock)
        original_unlink = Path.unlink

        def mock_unlink(self):
            if self.name == "file.txt":
                raise PermissionError("Cannot delete file")  # noqa: TRY003
            return original_unlink(self)

        with patch.object(Path, "unlink", mock_unlink):
            # Run uninstall - should exit with error code
            with pytest.raises(SystemExit) as excinfo:
                uninstall(tmp_path, force=True)
            assert excinfo.value.code == 1

    def test_uninstall_handles_lock_file_deletion_error(self, tmp_path):
        """Test that uninstall handles .rhiza/template.lock deletion error."""
        import pytest

        # Create a file
        file1 = tmp_path / "file.txt"
        file1.write_text("content")

        # Create .rhiza/template.lock
        _write_lock_file(tmp_path / ".rhiza", ["file.txt"])

        # Mock Path.unlink to raise exception only for template.lock
        original_unlink = Path.unlink

        def mock_unlink(self):
            if self.name == "template.lock":
                raise PermissionError("Cannot delete .rhiza/template.lock")  # noqa: TRY003
            return original_unlink(self)

        with patch.object(Path, "unlink", mock_unlink):
            # Run uninstall - should exit with error code
            with pytest.raises(SystemExit) as excinfo:
                uninstall(tmp_path, force=True)
            assert excinfo.value.code == 1

    def test_uninstall_handles_directory_removal_error(self, tmp_path):
        """Test that uninstall handles directory removal errors gracefully."""
        # Create nested directory with a file
        file1 = tmp_path / "dir1" / "file.txt"
        file1.parent.mkdir(parents=True, exist_ok=True)
        file1.write_text("content")

        # Create .rhiza/template.lock
        lock_file = _write_lock_file(tmp_path / ".rhiza", ["dir1/file.txt"])

        # Mock Path.rmdir to raise exception
        original_rmdir = Path.rmdir

        def mock_rmdir(self):
            if self.name == "dir1":
                raise PermissionError("Cannot remove directory")  # noqa: TRY003
            return original_rmdir(self)

        with patch.object(Path, "rmdir", mock_rmdir):
            # Run uninstall - should complete without crashing
            # (directory removal errors are caught and ignored)
            uninstall(tmp_path, force=True)

        # File should be deleted, lock file should be deleted
        # Directory might remain due to mock error
        assert not file1.exists()
        assert not lock_file.exists()
