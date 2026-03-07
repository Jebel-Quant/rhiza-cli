"""Tests for the `uninstall` command."""

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from rhiza.cli import app
from rhiza.commands.uninstall import uninstall

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_LOCK_HEADER = "sha: abc123def456\nrepo: owner/repo\nhost: github\nref: main\n"


def _make_lock(tmp_path: Path, files: list[str]) -> Path:
    """Write .rhiza/template.lock listing *files* and return its path."""
    rhiza_dir = tmp_path / ".rhiza"
    rhiza_dir.mkdir(parents=True, exist_ok=True)
    lock_file = rhiza_dir / "template.lock"
    file_list = "".join(f"  - {f}\n" for f in files)
    lock_file.write_text(_LOCK_HEADER + "files:\n" + file_list)
    return lock_file


# ---------------------------------------------------------------------------
# Core command tests
# ---------------------------------------------------------------------------


class TestUninstallCommand:
    """Tests for the uninstall command implementation."""

    def test_removes_files_listed_in_template_lock(self, tmp_path):
        """Uninstall removes every file listed in .rhiza/template.lock."""
        files = ["file1.txt", "subdir/file2.txt", "another/deep/file3.txt"]
        for rel in files:
            p = tmp_path / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("content")
        lock_file = _make_lock(tmp_path, files)

        uninstall(tmp_path, force=True)

        for rel in files:
            assert not (tmp_path / rel).exists()
        assert not lock_file.exists()

    def test_removes_empty_directories(self, tmp_path):
        """Empty parent directories are pruned after file removal."""
        file1 = tmp_path / "dir1" / "dir2" / "file.txt"
        file1.parent.mkdir(parents=True, exist_ok=True)
        file1.write_text("content")
        lock_file = _make_lock(tmp_path, ["dir1/dir2/file.txt"])

        uninstall(tmp_path, force=True)

        assert not file1.exists()
        assert not (tmp_path / "dir1").exists()
        assert not lock_file.exists()

    def test_preserves_non_empty_directories(self, tmp_path):
        """Directories that still contain non-managed files are kept."""
        managed = tmp_path / "shared" / "managed.txt"
        unmanaged = tmp_path / "shared" / "unmanaged.txt"
        managed.parent.mkdir(parents=True, exist_ok=True)
        managed.write_text("managed")
        unmanaged.write_text("unmanaged")
        lock_file = _make_lock(tmp_path, ["shared/managed.txt"])

        uninstall(tmp_path, force=True)

        assert not managed.exists()
        assert unmanaged.exists()
        assert (tmp_path / "shared").exists()
        assert not lock_file.exists()

    def test_handles_missing_lock_file(self, tmp_path):
        """No lock file → uninstall returns without error."""
        uninstall(tmp_path, force=True)  # must not raise

    def test_handles_already_deleted_files(self, tmp_path):
        """Files listed in the lock that no longer exist are skipped gracefully."""
        lock_file = _make_lock(tmp_path, ["nonexistent1.txt", "nonexistent2.txt"])

        uninstall(tmp_path, force=True)

        assert not lock_file.exists()

    def test_handles_invalid_template_lock(self, tmp_path):
        """Unparseable lock file → returns early, no files are touched."""
        file1 = tmp_path / "managed.txt"
        file1.write_text("content")
        lock_file = _make_lock(tmp_path, [])
        lock_file.write_text("not: valid: yaml: [\n")

        uninstall(tmp_path, force=True)

        assert file1.exists()

    def test_skips_confirmation_with_force(self, tmp_path):
        """force=True must not call input()."""
        file1 = tmp_path / "file.txt"
        file1.write_text("content")
        _make_lock(tmp_path, ["file.txt"])

        with patch("builtins.input") as mock_input:
            uninstall(tmp_path, force=True)
            mock_input.assert_not_called()

        assert not file1.exists()

    def test_prompts_for_confirmation_without_force(self, tmp_path):
        """force=False prompts the user; confirming with 'y' proceeds."""
        file1 = tmp_path / "file.txt"
        file1.write_text("content")
        lock_file = _make_lock(tmp_path, ["file.txt"])

        with patch("builtins.input", return_value="y"):
            uninstall(tmp_path, force=False)

        assert not file1.exists()
        assert not lock_file.exists()

    def test_cancels_on_no_answer(self, tmp_path):
        """Answering 'n' leaves files untouched."""
        file1 = tmp_path / "file.txt"
        file1.write_text("content")
        lock_file = _make_lock(tmp_path, ["file.txt"])

        with patch("builtins.input", return_value="n"):
            uninstall(tmp_path, force=False)

        assert file1.exists()
        assert lock_file.exists()

    def test_cancels_on_keyboard_interrupt(self, tmp_path):
        """Ctrl-C during the prompt leaves files untouched."""
        file1 = tmp_path / "file.txt"
        file1.write_text("content")
        lock_file = _make_lock(tmp_path, ["file.txt"])

        with patch("builtins.input", side_effect=KeyboardInterrupt):
            uninstall(tmp_path, force=False)

        assert file1.exists()
        assert lock_file.exists()


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------


class TestUninstallCLI:
    """Tests for the uninstall CLI command."""

    def test_help(self):
        """Uninstall --help exits 0 and mentions the command name."""
        result = subprocess.run(
            [sys.executable, "-m", "rhiza", "uninstall", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "uninstall" in result.stdout.lower()
        assert "Remove all Rhiza-managed files" in result.stdout

    @pytest.mark.parametrize("flag", ["--force", "-y"])
    def test_force_flags(self, tmp_path, flag):
        """Both --force and -y skip the confirmation prompt."""
        file1 = tmp_path / "file.txt"
        file1.write_text("content")
        lock_file = _make_lock(tmp_path, ["file.txt"])

        result = CliRunner().invoke(app, ["uninstall", str(tmp_path), flag])

        assert result.exit_code == 0
        assert not file1.exists()
        assert not lock_file.exists()

    def test_defaults_to_current_directory(self, tmp_path, monkeypatch):
        """Without a target argument, the current directory is used."""
        monkeypatch.chdir(tmp_path)
        file1 = tmp_path / "file.txt"
        file1.write_text("content")
        lock_file = _make_lock(tmp_path, ["file.txt"])

        result = CliRunner().invoke(app, ["uninstall", "--force"])

        assert result.exit_code == 0
        assert not file1.exists()
        assert not lock_file.exists()

    @pytest.mark.parametrize(
        ("user_input", "removed"),
        [("y\n", True), ("n\n", False)],
    )
    def test_interactive_confirmation(self, tmp_path, user_input, removed):
        """Typing y removes files; typing n keeps them."""
        file1 = tmp_path / "file.txt"
        file1.write_text("content")
        lock_file = _make_lock(tmp_path, ["file.txt"])

        result = CliRunner().invoke(app, ["uninstall", str(tmp_path)], input=user_input)

        assert result.exit_code == 0
        assert file1.exists() is not removed
        assert lock_file.exists() is not removed

    def test_subprocess_integration(self, tmp_path):
        """Uninstall works end-to-end when invoked as a subprocess."""
        file1 = tmp_path / "file.txt"
        file1.write_text("content")
        lock_file = _make_lock(tmp_path, ["file.txt"])

        result = subprocess.run(
            [sys.executable, "-m", "rhiza", "uninstall", str(tmp_path), "--force"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert not file1.exists()
        assert not lock_file.exists()


# ---------------------------------------------------------------------------
# Edge-case tests
# ---------------------------------------------------------------------------


class TestUninstallEdgeCases:
    """Tests for edge cases in uninstall functionality."""

    def test_special_characters_in_filename(self, tmp_path):
        """Files with spaces, dashes and underscores are removed correctly."""
        files = ["file with spaces.txt", "file-with-dashes.txt", "file_with_underscores.txt"]
        for name in files:
            (tmp_path / name).write_text("content")
        lock_file = _make_lock(tmp_path, files)

        uninstall(tmp_path, force=True)

        for name in files:
            assert not (tmp_path / name).exists()
        assert not lock_file.exists()

    def test_deeply_nested_paths(self, tmp_path):
        """All empty ancestor directories are pruned after a deeply nested file is deleted."""
        deep_file = tmp_path / "a" / "b" / "c" / "d" / "e" / "file.txt"
        deep_file.parent.mkdir(parents=True, exist_ok=True)
        deep_file.write_text("content")
        lock_file = _make_lock(tmp_path, ["a/b/c/d/e/file.txt"])

        uninstall(tmp_path, force=True)

        assert not deep_file.exists()
        assert not (tmp_path / "a").exists()
        assert not lock_file.exists()

    def test_dot_files(self, tmp_path):
        """Hidden dot-files listed in the lock are deleted."""
        dotfile = tmp_path / ".hidden"
        dotfile.write_text("hidden content")
        lock_file = _make_lock(tmp_path, [".hidden"])

        uninstall(tmp_path, force=True)

        assert not dotfile.exists()
        assert not lock_file.exists()

    def test_read_only_file(self, tmp_path):
        """Read-only files can be deleted when the parent dir is writable."""
        file1 = tmp_path / "readonly.txt"
        file1.write_text("content")
        file1.chmod(0o444)
        lock_file = _make_lock(tmp_path, ["readonly.txt"])

        uninstall(tmp_path, force=True)

        assert not file1.exists()
        assert not lock_file.exists()

    def test_handles_file_deletion_error(self, tmp_path):
        """A PermissionError during file deletion is surfaced as RuntimeError."""
        file1 = tmp_path / "file.txt"
        file1.write_text("content")
        _make_lock(tmp_path, ["file.txt"])

        original_unlink = Path.unlink

        def mock_unlink(self):
            if self.name == "file.txt":
                raise PermissionError("Cannot delete file")  # noqa: TRY003
            return original_unlink(self)

        with patch.object(Path, "unlink", mock_unlink), pytest.raises(RuntimeError):
            uninstall(tmp_path, force=True)

    def test_handles_lock_file_deletion_error(self, tmp_path):
        """A PermissionError deleting template.lock is surfaced as RuntimeError."""
        file1 = tmp_path / "file.txt"
        file1.write_text("content")
        _make_lock(tmp_path, ["file.txt"])

        original_unlink = Path.unlink

        def mock_unlink(self):
            if self.name == "template.lock" and ".rhiza" in str(self):
                raise PermissionError("Cannot delete .rhiza/template.lock")  # noqa: TRY003
            return original_unlink(self)

        with patch.object(Path, "unlink", mock_unlink), pytest.raises(RuntimeError):
            uninstall(tmp_path, force=True)

    def test_handles_directory_removal_error(self, tmp_path):
        """Directory removal errors are silently swallowed."""
        file1 = tmp_path / "dir1" / "file.txt"
        file1.parent.mkdir(parents=True, exist_ok=True)
        file1.write_text("content")
        lock_file = _make_lock(tmp_path, ["dir1/file.txt"])

        original_rmdir = Path.rmdir

        def mock_rmdir(self):
            if self.name == "dir1":
                raise PermissionError("Cannot remove directory")  # noqa: TRY003
            return original_rmdir(self)

        with patch.object(Path, "rmdir", mock_rmdir):
            uninstall(tmp_path, force=True)

        assert not file1.exists()
        assert not lock_file.exists()
