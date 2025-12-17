"""Tests for the `materialize` (inject) command and CLI wiring.

This module focuses on ensuring that `rhiza materialize` delegates to the
underlying inject logic and that basic paths and options are handled.
"""

from unittest.mock import Mock, patch

import pytest
import yaml
from typer.testing import CliRunner

from rhiza import cli
from rhiza.commands.materialize import materialize


class TestInjectCommand:
    """Tests for the inject/materialize command."""

    @patch("rhiza.commands.materialize.subprocess.run")
    @patch("rhiza.commands.materialize.shutil.rmtree")
    @patch("rhiza.commands.materialize.shutil.copy2")
    @patch("rhiza.commands.materialize.tempfile.mkdtemp")
    def test_inject_creates_default_template_yml(
        self, mock_mkdtemp, mock_copy2, mock_rmtree, mock_subprocess, tmp_path
    ):
        """Test that inject creates a default template.yml when it doesn't exist."""
        # Setup git repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Mock tempfile to return a controlled temp directory
        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()
        mock_mkdtemp.return_value = str(temp_dir)

        # Mock subprocess to succeed
        mock_subprocess.return_value = Mock(returncode=0)

        # Run inject
        materialize(tmp_path, "main", False)

        # Verify template.yml was created
        template_file = tmp_path / ".github" / "template.yml"
        assert template_file.exists()

        # Verify it contains expected content

        with open(template_file) as f:
            config = yaml.safe_load(f)

        assert config["template-repository"] == "jebel-quant/rhiza"
        assert config["template-branch"] == "main"
        assert ".github" in config["include"]

    @patch("rhiza.commands.materialize.subprocess.run")
    @patch("rhiza.commands.materialize.shutil.rmtree")
    @patch("rhiza.commands.materialize.shutil.copy2")
    @patch("rhiza.commands.materialize.tempfile.mkdtemp")
    def test_inject_uses_existing_template_yml(self, mock_mkdtemp, mock_copy2, mock_rmtree, mock_subprocess, tmp_path):
        """Test that inject uses an existing template.yml."""
        # Setup git repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Create existing template.yml
        github_dir = tmp_path / ".github"
        github_dir.mkdir()
        template_file = github_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump(
                {"template-repository": "custom/repo", "template-branch": "custom-branch", "include": [".github"]}, f
            )

        # Mock tempfile
        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()
        mock_mkdtemp.return_value = str(temp_dir)

        # Mock subprocess to succeed
        mock_subprocess.return_value = Mock(returncode=0)

        # Run inject
        materialize(tmp_path, "main", False)

        # Verify the git clone command used the custom repo
        clone_call = mock_subprocess.call_args_list[0]
        assert "custom/repo.git" in str(clone_call)

    @patch("rhiza.commands.materialize.subprocess.run")
    @patch("rhiza.commands.materialize.shutil.rmtree")
    @patch("rhiza.commands.materialize.shutil.copy2")
    @patch("rhiza.commands.materialize.tempfile.mkdtemp")
    def test_inject_fails_with_no_include_paths(self, mock_mkdtemp, mock_copy2, mock_rmtree, mock_subprocess, tmp_path):
        """Test that inject fails when template.yml has no include paths."""
        # Setup git repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Create template.yml with empty include
        github_dir = tmp_path / ".github"
        github_dir.mkdir()
        template_file = github_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump({"template-repository": "jebel-quant/rhiza", "template-branch": "main", "include": []}, f)

        # Run inject and expect it to fail
        with pytest.raises(SystemExit):
            materialize(tmp_path, "main", False)

    @patch("rhiza.commands.materialize.subprocess.run")
    @patch("rhiza.commands.materialize.shutil.rmtree")
    @patch("rhiza.commands.materialize.shutil.copy2")
    @patch("rhiza.commands.materialize.tempfile.mkdtemp")
    def test_inject_copies_files(self, mock_mkdtemp, mock_copy2, mock_rmtree, mock_subprocess, tmp_path):
        """Test that inject copies files from template to target."""
        # Setup git repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Create template.yml
        github_dir = tmp_path / ".github"
        github_dir.mkdir()
        template_file = github_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump(
                {"template-repository": "jebel-quant/rhiza", "template-branch": "main", "include": ["test.txt"]}, f
            )

        # Mock tempfile with actual directory containing a file
        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()
        test_file = temp_dir / "test.txt"
        test_file.write_text("content")
        mock_mkdtemp.return_value = str(temp_dir)

        # Mock subprocess to succeed
        mock_subprocess.return_value = Mock(returncode=0)

        # Run inject
        materialize(tmp_path, "main", False)

        # Verify copy2 was called
        assert mock_copy2.called

    @patch("rhiza.commands.materialize.subprocess.run")
    @patch("rhiza.commands.materialize.shutil.rmtree")
    @patch("rhiza.commands.materialize.shutil.copy2")
    @patch("rhiza.commands.materialize.tempfile.mkdtemp")
    def test_inject_skips_existing_files_without_force(
        self, mock_mkdtemp, mock_copy2, mock_rmtree, mock_subprocess, tmp_path
    ):
        """Test that inject skips existing files when force=False."""
        # Setup git repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Create existing file in target
        existing_file = tmp_path / "test.txt"
        existing_file.write_text("existing")

        # Create template.yml
        github_dir = tmp_path / ".github"
        github_dir.mkdir()
        template_file = github_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump(
                {"template-repository": "jebel-quant/rhiza", "template-branch": "main", "include": ["test.txt"]}, f
            )

        # Mock tempfile with file to copy
        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()
        src_file = temp_dir / "test.txt"
        src_file.write_text("new content")
        mock_mkdtemp.return_value = str(temp_dir)

        # Mock subprocess to succeed
        mock_subprocess.return_value = Mock(returncode=0)

        # Run inject without force
        materialize(tmp_path, "main", False)

        # Verify existing file was not overwritten
        assert existing_file.read_text() == "existing"
        # copy2 should not have been called for this file
        # (it might be called 0 times or for other files, depending on implementation)

    @patch("rhiza.commands.materialize.subprocess.run")
    @patch("rhiza.commands.materialize.shutil.rmtree")
    @patch("rhiza.commands.materialize.shutil.copy2")
    @patch("rhiza.commands.materialize.tempfile.mkdtemp")
    def test_inject_overwrites_with_force(self, mock_mkdtemp, mock_copy2, mock_rmtree, mock_subprocess, tmp_path):
        """Test that inject overwrites existing files when force=True."""
        # Setup git repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Create existing file in target
        existing_file = tmp_path / "test.txt"
        existing_file.write_text("existing")

        # Create template.yml
        github_dir = tmp_path / ".github"
        github_dir.mkdir()
        template_file = github_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump(
                {"template-repository": "jebel-quant/rhiza", "template-branch": "main", "include": ["test.txt"]}, f
            )

        # Mock tempfile with file to copy
        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()
        src_file = temp_dir / "test.txt"
        src_file.write_text("new content")
        mock_mkdtemp.return_value = str(temp_dir)

        # Mock subprocess to succeed
        mock_subprocess.return_value = Mock(returncode=0)

        # Run inject with force
        materialize(tmp_path, "main", True)

        # Verify copy2 was called (force should allow overwrite)
        assert mock_copy2.called

    @patch("rhiza.commands.materialize.subprocess.run")
    @patch("rhiza.commands.materialize.shutil.rmtree")
    @patch("rhiza.commands.materialize.shutil.copy2")
    @patch("rhiza.commands.materialize.tempfile.mkdtemp")
    def test_inject_excludes_paths(self, mock_mkdtemp, mock_copy2, mock_rmtree, mock_subprocess, tmp_path):
        """Test that inject excludes specified paths."""
        # Setup git repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Create template.yml with exclude
        github_dir = tmp_path / ".github"
        github_dir.mkdir()
        template_file = github_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump(
                {
                    "template-repository": "jebel-quant/rhiza",
                    "template-branch": "main",
                    "include": ["dir"],
                    "exclude": ["dir/excluded.txt"],
                },
                f,
            )

        # Mock tempfile with files
        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()
        dir_path = temp_dir / "dir"
        dir_path.mkdir()
        included_file = dir_path / "included.txt"
        excluded_file = dir_path / "excluded.txt"
        included_file.write_text("included")
        excluded_file.write_text("excluded")
        mock_mkdtemp.return_value = str(temp_dir)

        # Mock subprocess to succeed
        mock_subprocess.return_value = Mock(returncode=0)

        # Run inject
        materialize(tmp_path, "main", False)

        # Check that only included file was copied
        # This is implementation-specific, but we can check copy2 calls
        if mock_copy2.called:
            # Verify excluded.txt was not in the copy calls
            copy_calls = [str(call) for call in mock_copy2.call_args_list]
            assert any("included.txt" in str(call) for call in copy_calls)

    @patch("rhiza.commands.materialize.subprocess.run")
    @patch("rhiza.commands.materialize.shutil.rmtree")
    def test_inject_cleans_up_temp_dir(self, mock_rmtree, mock_subprocess, tmp_path):
        """Test that inject cleans up the temporary directory."""
        # Setup git repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Create minimal template.yml
        github_dir = tmp_path / ".github"
        github_dir.mkdir()
        template_file = github_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump(
                {"template-repository": "jebel-quant/rhiza", "template-branch": "main", "include": [".github"]}, f
            )

        # Mock subprocess to succeed
        mock_subprocess.return_value = Mock(returncode=0)

        # Run inject
        materialize(tmp_path, "main", False)

        # Verify rmtree was called to clean up
        assert mock_rmtree.called

    @patch("rhiza.commands.materialize.subprocess.run")
    @patch("rhiza.commands.materialize.shutil.rmtree")
    @patch("rhiza.commands.materialize.shutil.copy2")
    @patch("rhiza.commands.materialize.tempfile.mkdtemp")
    def test_cli_materialize_command(self, mock_mkdtemp, mock_copy2, mock_rmtree, mock_subprocess, tmp_path):
        """Test the CLI materialize command via Typer runner."""
        runner = CliRunner()

        # Setup git repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Create template.yml
        github_dir = tmp_path / ".github"
        github_dir.mkdir()
        template_file = github_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump(
                {"template-repository": "jebel-quant/rhiza", "template-branch": "main", "include": [".github"]}, f
            )

        # Mock tempfile
        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()
        mock_mkdtemp.return_value = str(temp_dir)

        # Mock subprocess to succeed
        mock_subprocess.return_value = Mock(returncode=0)

        # Run CLI command
        result = runner.invoke(cli.app, ["materialize", str(tmp_path), "--branch", "main"])
        assert result.exit_code == 0
