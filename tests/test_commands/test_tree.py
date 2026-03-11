"""Tests for the tree command and CLI wiring.

This module verifies that `tree` reads `.rhiza/template.lock` and renders
the managed files as a tree, and that the Typer CLI entry `rhiza tree`
behaves as expected across scenarios.
"""

import yaml
from typer.testing import CliRunner

from rhiza.cli import app
from rhiza.commands.tree import _count_directories, tree
from rhiza.models.lock import _build_tree


class TestBuildTree:
    """Unit tests for the _build_tree helper."""

    def test_single_file_at_root(self):
        """Single root-level file produces a flat dict."""
        result = _build_tree(["Makefile"])
        assert result == {"Makefile": {}}

    def test_nested_file(self):
        """Deeply nested path produces a nested dict."""
        result = _build_tree([".github/workflows/ci.yml"])
        assert result == {".github": {"workflows": {"ci.yml": {}}}}

    def test_multiple_files_same_dir(self):
        """Multiple files under the same directory share the parent node."""
        result = _build_tree(["src/a.py", "src/b.py"])
        assert result == {"src": {"a.py": {}, "b.py": {}}}

    def test_mixed_depth(self):
        """Files at different depths are all represented in the tree."""
        result = _build_tree(["Makefile", ".github/workflows/ci.yml"])
        assert ".github" in result
        assert "Makefile" in result


class TestTreeCommand:
    """Tests for the tree command function."""

    def test_warns_when_no_lock_file(self, tmp_path, capsys):
        """No template.lock → warning is emitted, no crash."""
        tree(tmp_path)
        # No exception and no tree output
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_displays_tree_when_files_present(self, tmp_path, capsys):
        """Structured lock with files → tree is printed."""
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        lock_data = {
            "sha": "abc123",
            "repo": "owner/repo",
            "host": "github",
            "ref": "main",
            "include": [],
            "exclude": [],
            "templates": [],
            "files": [
                ".github/workflows/ci.yml",
                ".rhiza/template.yml",
                "Makefile",
            ],
        }
        (rhiza_dir / "template.lock").write_text(yaml.dump(lock_data))

        tree(tmp_path)

        captured = capsys.readouterr()
        output = captured.out
        assert "." in output
        assert ".github" in output
        assert "workflows" in output
        assert "ci.yml" in output
        assert ".rhiza" in output
        assert "template.yml" in output
        assert "Makefile" in output
        assert "3 files" in output
        assert "managed by Rhiza" in output
        assert "owner/repo" in output

    def test_no_output_when_files_list_empty(self, tmp_path, capsys):
        """Lock file with no files → info message, no tree."""
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        lock_data = {
            "sha": "abc123",
            "repo": "owner/repo",
            "files": [],
        }
        (rhiza_dir / "template.lock").write_text(yaml.dump(lock_data))

        tree(tmp_path)

        captured = capsys.readouterr()
        assert captured.out == ""

    def test_singular_file_count_label(self, tmp_path, capsys):
        """Single file → '1 file managed' (not '1 files')."""
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        lock_data = {
            "sha": "abc123",
            "files": ["Makefile"],
        }
        (rhiza_dir / "template.lock").write_text(yaml.dump(lock_data))

        tree(tmp_path)

        captured = capsys.readouterr()
        assert "1 file," in captured.out
        assert "managed by Rhiza" in captured.out
        assert "1 files" not in captured.out


class TestTreeCommandCli:
    """Tests for the `rhiza tree` CLI entry point."""

    runner = CliRunner()

    def test_cli_tree_exits_zero_with_lock(self, tmp_path):
        """CLI returns exit code 0 when template.lock exists."""
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        lock_data = {
            "sha": "abc123def456",
            "repo": "owner/repo",
            "host": "github",
            "ref": "main",
            "files": ["Makefile", ".github/workflows/ci.yml"],
        }
        (rhiza_dir / "template.lock").write_text(yaml.dump(lock_data))

        result = self.runner.invoke(app, ["tree", str(tmp_path)])
        assert result.exit_code == 0
        assert "Makefile" in result.output
        assert ".github" in result.output

    def test_cli_tree_exits_zero_without_lock(self, tmp_path):
        """CLI returns exit code 0 even when template.lock is absent (warning only)."""
        result = self.runner.invoke(app, ["tree", str(tmp_path)])
        assert result.exit_code == 0

    def test_cli_tree_help(self):
        """CLI tree command has a help text."""
        result = self.runner.invoke(app, ["tree", "--help"])
        assert result.exit_code == 0
        assert "tree" in result.output.lower()

    def test_cli_tree_exits_one_on_exception(self, tmp_path):
        """CLI returns exit code 1 when an exception occurs."""
        from unittest.mock import patch

        with patch("rhiza.cli.tree_cmd", side_effect=RuntimeError("boom")):
            result = self.runner.invoke(app, ["tree", str(tmp_path)])
        assert result.exit_code == 1


class TestCountDirectories:
    """Unit tests for the _count_directories helper."""

    def test_no_directories(self):
        """Flat list of root-level files has zero directories."""
        node = {"Makefile": {}, "README.md": {}}
        assert _count_directories(node) == 0

    def test_single_directory(self):
        """One directory containing a file counts as one directory."""
        node = {"src": {"main.py": {}}}
        assert _count_directories(node) == 1

    def test_nested_directories(self):
        """Deeply nested paths count each directory node separately."""
        node = {".github": {"workflows": {"ci.yml": {}}}}
        # .github and workflows are both directories
        assert _count_directories(node) == 2

    def test_mixed_files_and_dirs(self):
        """Mix of root files and directories counts only directories."""
        node = {
            "Makefile": {},
            ".github": {"workflows": {"ci.yml": {}}},
            ".rhiza": {"template.yml": {}},
        }
        # .github, workflows, .rhiza
        assert _count_directories(node) == 3


class TestTreeHeaderAndFooter:
    """Tests that the tree command outputs the header and updated footer."""

    def test_displays_header_with_repo_and_sha(self, tmp_path, capsys):
        """Tree output starts with a header containing repo and truncated sha."""
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        lock_data = {
            "sha": "abc123def456",
            "repo": "owner/repo",
            "host": "github",
            "ref": "main",
            "include": [],
            "exclude": [],
            "templates": [],
            "files": ["Makefile"],
        }
        (rhiza_dir / "template.lock").write_text(yaml.dump(lock_data))

        tree(tmp_path)

        output = capsys.readouterr().out
        assert "owner/repo" in output
        assert "abc123def456" in output

    def test_displays_directory_count(self, tmp_path, capsys):
        """Footer includes directory count alongside file count."""
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        lock_data = {
            "sha": "abc123",
            "repo": "owner/repo",
            "host": "github",
            "ref": "main",
            "include": [],
            "exclude": [],
            "templates": [],
            "files": [
                ".github/workflows/ci.yml",
                ".rhiza/template.yml",
                "Makefile",
            ],
        }
        (rhiza_dir / "template.lock").write_text(yaml.dump(lock_data))

        tree(tmp_path)

        output = capsys.readouterr().out
        assert "3 files" in output
        assert "directories" in output
        assert "managed by Rhiza" in output
