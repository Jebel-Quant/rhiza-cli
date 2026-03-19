"""Tests for the tree command and CLI wiring.

This module verifies that `tree` reads `.rhiza/template.lock` and renders
the managed files as a tree, and that the Typer CLI entry `rhiza tree`
behaves as expected across scenarios.
"""

import yaml
from rich.tree import Tree as RichTree
from typer.testing import CliRunner

from rhiza.cli import app
from rhiza.commands.tree import _build_rich_tree, tree


class TestBuildRichTree:
    """Unit tests for the _build_rich_tree helper."""

    def test_single_file_at_root(self):
        """Single root-level file produces a tree with one child."""
        result = _build_rich_tree(["Makefile"])
        assert isinstance(result, RichTree)
        assert len(result.children) == 1
        assert result.children[0].label == "Makefile"

    def test_nested_file(self):
        """Deeply nested path produces nested tree nodes."""
        result = _build_rich_tree([".github/workflows/ci.yml"])
        assert len(result.children) == 1
        github_node = result.children[0]
        assert github_node.label == ".github"
        workflows_node = github_node.children[0]
        assert workflows_node.label == "workflows"
        assert workflows_node.children[0].label == "ci.yml"

    def test_multiple_files_same_dir(self):
        """Multiple files under the same directory share the parent node."""
        result = _build_rich_tree(["src/a.py", "src/b.py"])
        assert len(result.children) == 1
        src_node = result.children[0]
        assert src_node.label == "src"
        child_labels = [c.label for c in src_node.children]
        assert "a.py" in child_labels
        assert "b.py" in child_labels

    def test_mixed_depth(self):
        """Files at different depths are all represented in the tree."""
        result = _build_rich_tree(["Makefile", ".github/workflows/ci.yml"])
        top_labels = [c.label for c in result.children]
        assert ".github" in top_labels
        assert "Makefile" in top_labels


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
        assert "3 files managed by Rhiza" in output

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
        assert "1 file managed by Rhiza" in captured.out
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
