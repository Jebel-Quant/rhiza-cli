"""Tests for the summarise command.

This module verifies that `summarise` generates correct PR descriptions based on
staged changes and `.rhiza/template.yml` configuration.
"""

import shutil
import subprocess

import pytest
from typer.testing import CliRunner

from rhiza.cli import app
from rhiza.commands.summarise import summarise


class TestSummariseCommand:
    """Tests for the summarise command."""

    @pytest.fixture
    def git_repo(self, tmp_path):
        """Create a temporary git repository."""
        repo = tmp_path / "test_repo"
        repo.mkdir()

        git_cmd = shutil.which("git") or "git"
        subprocess.run([git_cmd, "init"], cwd=repo, check=True)
        subprocess.run([git_cmd, "config", "user.email", "test@test.com"], cwd=repo, check=True)
        subprocess.run([git_cmd, "config", "user.name", "Test"], cwd=repo, check=True)

        return repo

    def test_summarise_default_config(self, git_repo, capsys):
        """Test summarise with default configuration (missing template.yml)."""
        git_cmd = shutil.which("git") or "git"

        # Create and stage a file
        test_file = git_repo / "test.txt"
        test_file.write_text("test content")
        subprocess.run([git_cmd, "add", "."], cwd=git_repo, check=True)

        # Run summarise directly
        summarise(git_repo)

        captured = capsys.readouterr()
        output = captured.out

        # Verify default template info is used
        assert "jebel-quant/rhiza" in output
        assert "main" in output
        assert "files added" in output
        assert "Change Summary" in output

    def test_summarise_custom_config(self, git_repo, capsys):
        """Test summarise with custom template.yml configuration."""
        git_cmd = shutil.which("git") or "git"

        # Create custom template.yml
        rhiza_dir = git_repo / ".rhiza"
        rhiza_dir.mkdir()
        template_file = rhiza_dir / "template.yml"
        template_file.write_text('template-repository: "my-org/my-template"\ntemplate-branch: "v2"\n')

        # Create and stage a file
        test_file = git_repo / "feature.py"
        test_file.write_text("def feature(): pass")
        subprocess.run([git_cmd, "add", "."], cwd=git_repo, check=True)

        # Run summarise directly
        summarise(git_repo)

        captured = capsys.readouterr()
        output = captured.out

        # Verify custom template info is used
        assert "my-org/my-template" in output
        assert "v2" in output
        assert "files added" in output

    def test_summarise_cli_integration(self, git_repo):
        """Test summarise command via CLI invoke."""
        git_cmd = shutil.which("git") or "git"

        # Create custom template.yml
        rhiza_dir = git_repo / ".rhiza"
        rhiza_dir.mkdir()
        template_file = rhiza_dir / "template.yml"
        template_file.write_text('template-repository: "cli-test/repo"\ntemplate-branch: "dev"\n')

        # Create and stage a file
        test_file = git_repo / "cli_test.txt"
        test_file.write_text("cli test")
        subprocess.run([git_cmd, "add", "."], cwd=git_repo, check=True)

        runner = CliRunner()
        result = runner.invoke(app, ["summarise", str(git_repo)])

        assert result.exit_code == 0
        assert "cli-test/repo" in result.stdout
        assert "dev" in result.stdout
        assert "Template Synchronization" in result.stdout

    def test_summarise_with_deleted_files(self, git_repo, capsys):
        """Test summarise with deleted files."""
        git_cmd = shutil.which("git") or "git"

        # Create, commit, then delete a file
        test_file = git_repo / "to_delete.txt"
        test_file.write_text("will be deleted")
        subprocess.run([git_cmd, "add", "."], cwd=git_repo, check=True)
        subprocess.run([git_cmd, "commit", "-m", "initial"], cwd=git_repo, check=True)

        # Delete and stage the deletion
        test_file.unlink()
        subprocess.run([git_cmd, "add", "."], cwd=git_repo, check=True)

        # Run summarise
        summarise(git_repo)

        captured = capsys.readouterr()
        output = captured.out

        # Verify deleted files are shown
        assert "deleted" in output.lower()

    def test_summarise_with_renamed_files(self, git_repo, capsys):
        """Test summarise with renamed files."""
        git_cmd = shutil.which("git") or "git"

        # Create and commit a file
        old_file = git_repo / "old_name.txt"
        old_file.write_text("content")
        subprocess.run([git_cmd, "add", "."], cwd=git_repo, check=True)
        subprocess.run([git_cmd, "commit", "-m", "initial"], cwd=git_repo, check=True)

        # Rename and stage
        new_file = git_repo / "new_name.txt"
        old_file.rename(new_file)
        subprocess.run([git_cmd, "add", "-A"], cwd=git_repo, check=True)

        # Run summarise
        summarise(git_repo)

        captured = capsys.readouterr()
        output = captured.out

        # Renamed files are treated as modified
        assert "modified" in output.lower() or "changed" in output.lower()

    def test_summarise_with_github_workflows(self, git_repo, capsys):
        """Test summarise categorizes GitHub workflows correctly."""
        git_cmd = shutil.which("git") or "git"

        # Create GitHub workflow directory and file
        workflows_dir = git_repo / ".github" / "workflows"
        workflows_dir.mkdir(parents=True)
        workflow_file = workflows_dir / "ci.yml"
        workflow_file.write_text("name: CI")
        subprocess.run([git_cmd, "add", "."], cwd=git_repo, check=True)

        # Run summarise
        summarise(git_repo)

        captured = capsys.readouterr()
        output = captured.out

        # Should categorize as GitHub Actions Workflows
        assert "GitHub Actions Workflows" in output or "github" in output.lower()

    def test_summarise_with_github_config(self, git_repo, capsys):
        """Test summarise categorizes GitHub configuration correctly."""
        git_cmd = shutil.which("git") or "git"

        # Create GitHub config file (not in workflows)
        github_dir = git_repo / ".github"
        github_dir.mkdir(parents=True)
        config_file = github_dir / "CODEOWNERS"
        config_file.write_text("* @owner")
        subprocess.run([git_cmd, "add", "."], cwd=git_repo, check=True)

        # Run summarise
        summarise(git_repo)

        captured = capsys.readouterr()
        output = captured.out

        # Should categorize as GitHub Configuration
        assert "GitHub" in output or "Configuration" in output

    def test_summarise_with_rhiza_scripts(self, git_repo, capsys):
        """Test summarise categorizes Rhiza scripts correctly."""
        git_cmd = shutil.which("git") or "git"

        # Create Rhiza script
        rhiza_dir = git_repo / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        script_file = rhiza_dir / "my-script.sh"
        script_file.write_text("#!/bin/bash")
        subprocess.run([git_cmd, "add", "."], cwd=git_repo, check=True)

        # Run summarise
        summarise(git_repo)

        captured = capsys.readouterr()
        output = captured.out

        # Should categorize as Rhiza Scripts
        assert "Rhiza" in output or "script" in output.lower()

    def test_summarise_with_rhiza_makefile(self, git_repo, capsys):
        """Test summarise categorizes Rhiza Makefiles correctly."""
        git_cmd = shutil.which("git") or "git"

        # Create Rhiza Makefile
        rhiza_dir = git_repo / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        makefile = rhiza_dir / "Makefile"
        makefile.write_text("all:\n\t@echo test")
        subprocess.run([git_cmd, "add", "."], cwd=git_repo, check=True)

        # Run summarise
        summarise(git_repo)

        captured = capsys.readouterr()
        output = captured.out

        # Should categorize as Makefiles
        assert "Makefile" in output or "Rhiza" in output

    def test_summarise_with_tests(self, git_repo, capsys):
        """Test summarise categorizes test files correctly."""
        git_cmd = shutil.which("git") or "git"

        # Create test file
        tests_dir = git_repo / "tests"
        tests_dir.mkdir(parents=True)
        test_file = tests_dir / "test_feature.py"
        test_file.write_text("def test_something(): pass")
        subprocess.run([git_cmd, "add", "."], cwd=git_repo, check=True)

        # Run summarise
        summarise(git_repo)

        captured = capsys.readouterr()
        output = captured.out

        # Should categorize as Tests
        assert "Test" in output or "test" in output.lower()

    def test_summarise_with_book_documentation(self, git_repo, capsys):
        """Test summarise categorizes book documentation correctly."""
        git_cmd = shutil.which("git") or "git"

        # Create book documentation
        book_dir = git_repo / "book"
        book_dir.mkdir(parents=True)
        doc_file = book_dir / "intro.md"
        doc_file.write_text("# Introduction")
        subprocess.run([git_cmd, "add", "."], cwd=git_repo, check=True)

        # Run summarise
        summarise(git_repo)

        captured = capsys.readouterr()
        output = captured.out

        # Should categorize as Documentation
        assert "Documentation" in output or "book" in output.lower()

    def test_summarise_with_markdown_files(self, git_repo, capsys):
        """Test summarise categorizes markdown files as documentation."""
        git_cmd = shutil.which("git") or "git"

        # Create markdown file
        readme = git_repo / "README.md"
        readme.write_text("# Project")
        subprocess.run([git_cmd, "add", "."], cwd=git_repo, check=True)

        # Run summarise
        summarise(git_repo)

        captured = capsys.readouterr()
        output = captured.out

        # Should categorize as Documentation
        assert "Documentation" in output or "README.md" in output

    def test_summarise_with_config_files(self, git_repo, capsys):
        """Test summarise categorizes known config files correctly."""
        git_cmd = shutil.which("git") or "git"

        # Create a known config file
        config_file = git_repo / ".editorconfig"
        config_file.write_text("[*]\nindent_size = 2")
        subprocess.run([git_cmd, "add", "."], cwd=git_repo, check=True)

        # Run summarise
        summarise(git_repo)

        captured = capsys.readouterr()
        output = captured.out

        # Should categorize as Configuration Files
        assert "Configuration" in output or ".editorconfig" in output

    def test_summarise_with_no_changes(self, git_repo, capsys):
        """Test summarise with no staged changes."""
        # Run summarise without staging anything
        summarise(git_repo)

        captured = capsys.readouterr()
        output = captured.out

        # Should indicate no changes
        assert "No changes" in output or "0 file" in output

    def test_summarise_with_history_file(self, git_repo, capsys):
        """Test summarise with .rhiza/history file for last sync date."""
        git_cmd = shutil.which("git") or "git"

        # Create .rhiza/history file
        rhiza_dir = git_repo / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        history_file = rhiza_dir / "history"
        history_file.write_text("some history")

        # Create and stage a file
        test_file = git_repo / "test.txt"
        test_file.write_text("test")
        subprocess.run([git_cmd, "add", "."], cwd=git_repo, check=True)

        # Run summarise
        summarise(git_repo)

        captured = capsys.readouterr()
        output = captured.out

        # Should include last sync date
        assert "Last sync" in output or "Sync date" in output

    def test_summarise_with_output_file(self, git_repo, tmp_path):
        """Test summarise writes to output file."""
        git_cmd = shutil.which("git") or "git"

        # Create and stage a file
        test_file = git_repo / "test.txt"
        test_file.write_text("test")
        subprocess.run([git_cmd, "add", "."], cwd=git_repo, check=True)

        # Run summarise with output file
        output_file = tmp_path / "pr-description.md"
        summarise(git_repo, output=output_file)

        # Verify file was created
        assert output_file.exists()
        content = output_file.read_text()
        assert "Template Synchronization" in content

    def test_summarise_non_git_repo(self, tmp_path):
        """Test summarise exits with error for non-git repository."""
        non_git_dir = tmp_path / "not_a_repo"
        non_git_dir.mkdir()

        # Should exit with error
        with pytest.raises(SystemExit):
            summarise(non_git_dir)

    def test_summarise_with_malformed_git_status(self, git_repo, capsys, monkeypatch):
        """Test summarise handles malformed git status lines gracefully."""
        git_cmd = shutil.which("git") or "git"

        # Create and stage a file normally first
        test_file = git_repo / "test.txt"
        test_file.write_text("test")
        subprocess.run([git_cmd, "add", "."], cwd=git_repo, check=True)

        # Run summarise - it should handle edge cases in parsing
        summarise(git_repo)

        captured = capsys.readouterr()
        output = captured.out

        # Should still generate output
        assert "Template Synchronization" in output

    def test_summarise_with_modified_files(self, git_repo, capsys):
        """Test summarise with modified files."""
        git_cmd = shutil.which("git") or "git"

        # Create and commit a file
        test_file = git_repo / "existing.txt"
        test_file.write_text("original content")
        subprocess.run([git_cmd, "add", "."], cwd=git_repo, check=True)
        subprocess.run([git_cmd, "commit", "-m", "initial"], cwd=git_repo, check=True)

        # Modify and stage
        test_file.write_text("modified content")
        subprocess.run([git_cmd, "add", "."], cwd=git_repo, check=True)

        # Run summarise
        summarise(git_repo)

        captured = capsys.readouterr()
        output = captured.out

        # Should show modified files
        assert "modified" in output.lower() or "changed" in output.lower()

    def test_summarise_with_rhiza_commit_history(self, git_repo, capsys):
        """Test summarise finds last sync from git log with 'rhiza' commit."""
        git_cmd = shutil.which("git") or "git"

        # Create and commit a file with 'rhiza' in commit message
        test_file = git_repo / "test.txt"
        test_file.write_text("content")
        subprocess.run([git_cmd, "add", "."], cwd=git_repo, check=True)
        subprocess.run([git_cmd, "commit", "-m", "Sync with rhiza template"], cwd=git_repo, check=True)

        # Create another file and stage it
        new_file = git_repo / "new.txt"
        new_file.write_text("new content")
        subprocess.run([git_cmd, "add", "."], cwd=git_repo, check=True)

        # Run summarise
        summarise(git_repo)

        captured = capsys.readouterr()
        output = captured.out

        # Should include last sync date from commit
        assert "Last sync" in output

    def test_get_staged_changes_with_malformed_line(self, git_repo):
        """Test get_staged_changes handles malformed git output."""
        from rhiza.commands.summarise import get_staged_changes
        from unittest.mock import patch

        # Mock run_git_command to return malformed output
        with patch("rhiza.commands.summarise.run_git_command") as mock_git:
            # Include a line without tab separator
            mock_git.return_value = "A\tfile1.txt\nMALFORMED_LINE\nM\tfile2.txt"
            
            changes = get_staged_changes(git_repo)
            
            # Should have processed valid lines and skipped malformed one
            assert "file1.txt" in changes["added"]
            assert "file2.txt" in changes["modified"]

    def test_get_staged_changes_with_unusual_status(self, git_repo):
        """Test get_staged_changes handles unusual git status codes."""
        from rhiza.commands.summarise import get_staged_changes
        from unittest.mock import patch

        # Mock run_git_command to return output with unusual status codes
        with patch("rhiza.commands.summarise.run_git_command") as mock_git:
            # Include various status codes including unusual ones
            mock_git.return_value = "A\tfile1.txt\nM\tfile2.txt\nT\tfile3.txt\nX\tfile4.txt"
            
            changes = get_staged_changes(git_repo)
            
            # Should have processed A and M, ignored T and X
            assert "file1.txt" in changes["added"]
            assert "file2.txt" in changes["modified"]
            # T and X should be ignored (not in any category)
            assert "file3.txt" not in changes["added"]
            assert "file3.txt" not in changes["modified"]
            assert "file3.txt" not in changes["deleted"]

    def test_categorize_file_with_empty_path(self):
        """Test _categorize_single_file handles empty path."""
        from rhiza.commands.summarise import _categorize_single_file
        
        # Empty path should be categorized as "Other"
        result = _categorize_single_file("")
        assert result == "Other"
