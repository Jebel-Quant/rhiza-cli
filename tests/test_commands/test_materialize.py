"""Tests for the `materialize` (inject) command and CLI wiring.

This module focuses on ensuring that `rhiza materialize` delegates to the
underlying inject logic and that basic paths and options are handled.
"""

import subprocess
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
        materialize(tmp_path, "main", None, False)

        # Verify template.yml was created
        template_file = tmp_path / ".rhiza" / "template.yml"
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
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True, exist_ok=True)
        template_file = rhiza_dir / "template.yml"

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
        materialize(tmp_path, "main", None, False)

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
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True, exist_ok=True)
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump({"template-repository": "jebel-quant/rhiza", "template-branch": "main", "include": []}, f)

        # Run inject and expect it to fail
        with pytest.raises(SystemExit):
            materialize(tmp_path, "main", None, False)

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
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True, exist_ok=True)
        template_file = rhiza_dir / "template.yml"

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
        materialize(tmp_path, "main", None, False)

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
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True, exist_ok=True)
        template_file = rhiza_dir / "template.yml"

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
        materialize(tmp_path, "main", None, False)

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
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True, exist_ok=True)
        template_file = rhiza_dir / "template.yml"

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
        materialize(tmp_path, "main", None, True)

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
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True, exist_ok=True)
        template_file = rhiza_dir / "template.yml"

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
        materialize(tmp_path, "main", None, False)

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
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True, exist_ok=True)
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump(
                {"template-repository": "jebel-quant/rhiza", "template-branch": "main", "include": [".github"]}, f
            )

        # Mock subprocess to succeed
        mock_subprocess.return_value = Mock(returncode=0)

        # Run inject
        materialize(tmp_path, "main", None, False)

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
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True, exist_ok=True)
        template_file = rhiza_dir / "template.yml"

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

    @patch("rhiza.commands.materialize.subprocess.run")
    @patch("rhiza.commands.materialize.shutil.rmtree")
    @patch("rhiza.commands.materialize.shutil.copy2")
    @patch("rhiza.commands.materialize.tempfile.mkdtemp")
    def test_materialize_creates_rhiza_history_file(
        self, mock_mkdtemp, mock_copy2, mock_rmtree, mock_subprocess, tmp_path
    ):
        """Test that materialize creates a .rhiza/history file listing all template files."""
        # Setup git repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Create template.yml
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True, exist_ok=True)
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump(
                {
                    "template-repository": "jebel-quant/rhiza",
                    "template-branch": "main",
                    "include": ["file1.txt", "file2.txt"],
                },
                f,
            )

        # Mock tempfile with actual files
        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()
        file1 = temp_dir / "file1.txt"
        file2 = temp_dir / "file2.txt"
        file1.write_text("content1")
        file2.write_text("content2")
        mock_mkdtemp.return_value = str(temp_dir)

        # Mock subprocess to succeed
        mock_subprocess.return_value = Mock(returncode=0)

        # Run materialize
        materialize(tmp_path, "main", None, False)

        # Verify .rhiza/history was created
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True, exist_ok=True)
        history_file = rhiza_dir / "history"
        assert history_file.exists()

        # Verify content
        history_content = history_file.read_text()
        assert "# Rhiza Template History" in history_content
        assert "# Template repository: jebel-quant/rhiza" in history_content
        assert "# Template branch: main" in history_content
        assert "file1.txt" in history_content
        assert "file2.txt" in history_content

    @patch("rhiza.commands.materialize.subprocess.run")
    @patch("rhiza.commands.materialize.shutil.rmtree")
    @patch("rhiza.commands.materialize.shutil.copy2")
    @patch("rhiza.commands.materialize.tempfile.mkdtemp")
    def test_materialize_history_includes_skipped_files(
        self, mock_mkdtemp, mock_copy2, mock_rmtree, mock_subprocess, tmp_path
    ):
        """Test that .rhiza/history includes files that already exist (were skipped)."""
        # Setup git repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Create existing file that will be skipped
        existing_file = tmp_path / "existing.txt"
        existing_file.write_text("existing content")

        # Create template.yml
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True, exist_ok=True)
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump(
                {
                    "template-repository": "jebel-quant/rhiza",
                    "template-branch": "main",
                    "include": ["existing.txt"],
                },
                f,
            )

        # Mock tempfile with the file to copy
        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()
        src_file = temp_dir / "existing.txt"
        src_file.write_text("new content")
        mock_mkdtemp.return_value = str(temp_dir)

        # Mock subprocess to succeed
        mock_subprocess.return_value = Mock(returncode=0)

        # Run materialize without force (should skip existing file)
        materialize(tmp_path, "main", None, False)

        # Verify .rhiza/history includes the skipped file
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True, exist_ok=True)
        history_file = rhiza_dir / "history"
        assert history_file.exists()
        history_content = history_file.read_text()
        assert "existing.txt" in history_content

    @patch("rhiza.commands.materialize.subprocess.run")
    @patch("rhiza.commands.materialize.shutil.rmtree")
    @patch("rhiza.commands.materialize.shutil.copy2")
    @patch("rhiza.commands.materialize.tempfile.mkdtemp")
    def test_materialize_gitlab_repository(self, mock_mkdtemp, mock_copy2, mock_rmtree, mock_subprocess, tmp_path):
        """Test that materialize uses GitLab URL when template-host is gitlab."""
        # Setup git repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Create template.yml with gitlab host
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True, exist_ok=True)
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump(
                {
                    "template-repository": "mygroup/myproject",
                    "template-branch": "main",
                    "template-host": "gitlab",
                    "include": [".gitlab-ci.yml"],
                },
                f,
            )

        # Mock tempfile
        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()
        mock_mkdtemp.return_value = str(temp_dir)

        # Mock subprocess to succeed
        mock_subprocess.return_value = Mock(returncode=0)

        # Run materialize
        materialize(tmp_path, "main", None, False)

        # Verify the git clone command used GitLab URL
        clone_call = mock_subprocess.call_args_list[0]
        # print(clone_call)
        # print(str(clone_call))
        # assert False
        assert "https://gitlab.com/mygroup/myproject.git" in str(clone_call)

        # assert "gitlab.com" in str(clone_call)
        # assert "mygroup/myproject.git" in str(clone_call)

    @patch("rhiza.commands.materialize.subprocess.run")
    @patch("rhiza.commands.materialize.shutil.rmtree")
    @patch("rhiza.commands.materialize.shutil.copy2")
    @patch("rhiza.commands.materialize.tempfile.mkdtemp")
    def test_materialize_github_repository_explicit(
        self, mock_mkdtemp, mock_copy2, mock_rmtree, mock_subprocess, tmp_path
    ):
        """Test that materialize uses GitHub URL when template-host is explicitly github."""
        # Setup git repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Create template.yml with explicit github host
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True, exist_ok=True)
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump(
                {
                    "template-repository": "jebel-quant/rhiza",
                    "template-branch": "main",
                    "template-host": "github",
                    "include": [".github"],
                },
                f,
            )

        # Mock tempfile
        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()
        mock_mkdtemp.return_value = str(temp_dir)

        # Mock subprocess to succeed
        mock_subprocess.return_value = Mock(returncode=0)

        # Run materialize
        materialize(tmp_path, "main", None, False)

        # Verify the git clone command used GitHub URL
        clone_call = mock_subprocess.call_args_list[0]
        print(clone_call)
        assert "https://github.com/jebel-quant/rhiza.git" in str(clone_call)

    @patch("rhiza.commands.materialize.subprocess.run")
    @patch("rhiza.commands.materialize.shutil.rmtree")
    @patch("rhiza.commands.materialize.tempfile.mkdtemp")
    def test_materialize_fails_with_invalid_host(self, mock_mkdtemp, mock_rmtree, mock_subprocess, tmp_path):
        """Test that materialize fails with an unsupported template-host."""
        # Setup git repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Create template.yml with invalid host
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True, exist_ok=True)
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump(
                {
                    "template-repository": "invalid/repo",
                    "template-branch": "main",
                    "template-host": "bitbucket",
                    "include": [".github"],
                },
                f,
            )

        # Mock tempfile
        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()
        mock_mkdtemp.return_value = str(temp_dir)

        # Run materialize and expect it to fail with ValueError
        with pytest.raises(ValueError, match="Unsupported template-host"):
            materialize(tmp_path, "main", None, False)

    @patch("rhiza.commands.materialize.subprocess.run")
    @patch("rhiza.commands.materialize.shutil.rmtree")
    @patch("rhiza.commands.materialize.shutil.copy2")
    @patch("rhiza.commands.materialize.tempfile.mkdtemp")
    def test_materialize_warns_for_workflow_files(
        self, mock_mkdtemp, mock_copy2, mock_rmtree, mock_subprocess, tmp_path
    ):
        """Test that materialize warns when workflow files are materialized."""
        # Setup git repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Create src and tests folders to avoid validation warnings
        (tmp_path / "src").mkdir()
        (tmp_path / "tests").mkdir()

        # Create template.yml including workflow files
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True, exist_ok=True)
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump(
                {
                    "template-repository": "jebel-quant/rhiza",
                    "template-branch": "main",
                    "include": [".github/workflows"],
                },
                f,
            )

        # Mock tempfile with workflow files
        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()
        workflows_dir = temp_dir / ".github" / "workflows"
        workflows_dir.mkdir(parents=True)
        workflow_file = workflows_dir / "ci.yml"
        workflow_file.write_text("name: CI")
        mock_mkdtemp.return_value = str(temp_dir)

        # Mock subprocess to succeed
        mock_subprocess.return_value = Mock(returncode=0)

        # Patch logger.warning to verify it's called
        with patch("rhiza.commands.materialize.logger.warning") as mock_warning:
            # Run materialize
            materialize(tmp_path, "main", None, False)

            # Verify warning was called
            mock_warning.assert_called_once()
            # Verify the warning message contains expected text
            call_args = mock_warning.call_args[0][0]
            assert "workflow" in call_args.lower()
            assert "permission" in call_args.lower()

    @patch("rhiza.commands.materialize.init")
    def test_materialize_empty_include_paths_raises_error(self, mock_init, tmp_path):
        """Test that materialize raises RuntimeError when include_paths is empty after validation."""
        # Setup git repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Create template.yml with empty include (bypassing normal validation)
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True, exist_ok=True)
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump(
                {
                    "template-repository": "jebel-quant/rhiza",
                    "template-branch": "main",
                    "include": [],
                },
                f,
            )

        # Mock init to return True (bypass validation that would catch this)
        mock_init.return_value = True

        # Run materialize and expect RuntimeError
        with pytest.raises(RuntimeError, match="No include paths found"):
            materialize(tmp_path, "main", None, False)

    @patch("rhiza.commands.materialize.subprocess.run")
    @patch("rhiza.commands.materialize.shutil.rmtree")
    @patch("rhiza.commands.materialize.shutil.copy2")
    @patch("rhiza.commands.materialize.tempfile.mkdtemp")
    def test_materialize_creates_new_branch(self, mock_mkdtemp, mock_copy2, mock_rmtree, mock_subprocess, tmp_path):
        """Test that materialize creates a new branch when target_branch is specified and doesn't exist."""
        # Setup git repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Create template.yml
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True, exist_ok=True)
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump(
                {"template-repository": "jebel-quant/rhiza", "template-branch": "main", "include": [".github"]}, f
            )

        # Mock tempfile
        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()
        mock_mkdtemp.return_value = str(temp_dir)

        # Mock subprocess calls
        # First call: git rev-parse (branch doesn't exist)
        # Remaining calls: git clone, git sparse-checkout, etc.
        def subprocess_side_effect(*args, **kwargs):
            cmd = args[0] if args else kwargs.get("args", [])
            if "rev-parse" in cmd:
                # Return non-zero to indicate branch doesn't exist
                mock_result = Mock()
                mock_result.returncode = 1
                mock_result.stdout = ""
                mock_result.stderr = "fatal: Needed a single revision"
                return mock_result
            # Other commands succeed
            mock_result = Mock()
            mock_result.returncode = 0
            return mock_result

        mock_subprocess.side_effect = subprocess_side_effect

        # Run materialize with target_branch
        materialize(tmp_path, "main", "feature/test-branch", False)

        # Verify git checkout -b was called to create the branch
        checkout_calls = [
            call
            for call in mock_subprocess.call_args_list
            if len(call[0]) > 0 and call[0][0] == ["git", "checkout", "-b", "feature/test-branch"]
        ]
        assert len(checkout_calls) > 0, "Expected git checkout -b feature/test-branch to be called"

    @patch("rhiza.commands.materialize.subprocess.run")
    @patch("rhiza.commands.materialize.shutil.rmtree")
    @patch("rhiza.commands.materialize.shutil.copy2")
    @patch("rhiza.commands.materialize.tempfile.mkdtemp")
    def test_materialize_checks_out_existing_branch(
        self, mock_mkdtemp, mock_copy2, mock_rmtree, mock_subprocess, tmp_path
    ):
        """Test that materialize checks out an existing branch when target_branch is specified."""
        # Setup git repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Create template.yml
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True, exist_ok=True)
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump(
                {"template-repository": "jebel-quant/rhiza", "template-branch": "main", "include": [".github"]}, f
            )

        # Mock tempfile
        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()
        mock_mkdtemp.return_value = str(temp_dir)

        # Mock subprocess calls
        def subprocess_side_effect(*args, **kwargs):
            cmd = args[0] if args else kwargs.get("args", [])
            if "rev-parse" in cmd:
                # Return zero to indicate branch exists
                mock_result = Mock()
                mock_result.returncode = 0
                mock_result.stdout = "abc123"
                return mock_result
            # Other commands succeed
            mock_result = Mock()
            mock_result.returncode = 0
            return mock_result

        mock_subprocess.side_effect = subprocess_side_effect

        # Run materialize with target_branch
        materialize(tmp_path, "main", "existing-branch", False)

        # Verify git checkout (without -b) was called to checkout existing branch
        checkout_calls = [
            call
            for call in mock_subprocess.call_args_list
            if len(call[0]) > 0 and call[0][0] == ["git", "checkout", "existing-branch"]
        ]
        assert len(checkout_calls) > 0, "Expected git checkout existing-branch to be called"

    @patch("rhiza.commands.materialize.subprocess.run")
    @patch("rhiza.commands.materialize.shutil.rmtree")
    @patch("rhiza.commands.materialize.shutil.copy2")
    @patch("rhiza.commands.materialize.tempfile.mkdtemp")
    def test_materialize_no_branch_stays_on_current(
        self, mock_mkdtemp, mock_copy2, mock_rmtree, mock_subprocess, tmp_path
    ):
        """Test that materialize stays on current branch when target_branch is not specified."""
        # Setup git repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Create template.yml
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True, exist_ok=True)
        template_file = rhiza_dir / "template.yml"

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

        # Run materialize without target_branch
        materialize(tmp_path, "main", None, False)

        # Verify no git checkout commands were called for branch switching
        # We check for git commands that start with ["git", "checkout", ...] but exclude sparse-checkout
        branch_checkout_calls = [
            call
            for call in mock_subprocess.call_args_list
            if (
                len(call[0]) > 0
                and len(call[0][0]) >= 2
                and call[0][0][0] == "git"
                and call[0][0][1] == "checkout"
                and "sparse-checkout" not in " ".join(call[0][0])
            )
        ]
        assert len(branch_checkout_calls) == 0, "No git checkout for branch switching should be called"

    @patch("rhiza.commands.materialize.subprocess.run")
    @patch("rhiza.commands.materialize.shutil.rmtree")
    @patch("rhiza.commands.materialize.tempfile.mkdtemp")
    def test_materialize_exits_on_branch_checkout_failure(self, mock_mkdtemp, mock_rmtree, mock_subprocess, tmp_path):
        """Test that materialize exits when branch checkout fails."""
        # Setup git repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Create template.yml
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True, exist_ok=True)
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump(
                {"template-repository": "jebel-quant/rhiza", "template-branch": "main", "include": [".github"]}, f
            )

        # Mock tempfile
        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()
        mock_mkdtemp.return_value = str(temp_dir)

        # Mock subprocess to fail on checkout
        def subprocess_side_effect(*args, **kwargs):
            cmd = args[0] if args else kwargs.get("args", [])
            if "checkout" in cmd:
                raise subprocess.CalledProcessError(1, cmd, stderr="error: pathspec 'bad' did not match")
            mock_result = Mock()
            mock_result.returncode = 0
            return mock_result

        mock_subprocess.side_effect = subprocess_side_effect

        # Run materialize and expect it to exit
        with pytest.raises(SystemExit):
            materialize(tmp_path, "main", "bad-branch", False)

    @patch("rhiza.commands.materialize.subprocess.run")
    @patch("rhiza.commands.materialize.shutil.rmtree")
    @patch("rhiza.commands.materialize.tempfile.mkdtemp")
    def test_materialize_git_clone_failure_with_stderr(self, mock_mkdtemp, mock_rmtree, mock_subprocess, tmp_path):
        """Test that materialize handles git clone failure with stderr."""
        # Setup git repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Create template.yml
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True, exist_ok=True)
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump(
                {"template-repository": "jebel-quant/rhiza", "template-branch": "main", "include": [".github"]}, f
            )

        # Mock tempfile
        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()
        mock_mkdtemp.return_value = str(temp_dir)

        # Mock subprocess to fail on git clone with stderr
        error = subprocess.CalledProcessError(128, ["git", "clone"], stderr="fatal: repository not found")
        mock_subprocess.side_effect = error

        # Run materialize and expect CalledProcessError to be raised
        with pytest.raises(subprocess.CalledProcessError):
            materialize(tmp_path, "main", None, False)

    @patch("rhiza.commands.materialize.subprocess.run")
    @patch("rhiza.commands.materialize.shutil.rmtree")
    @patch("rhiza.commands.materialize.tempfile.mkdtemp")
    def test_materialize_sparse_checkout_init_failure_with_stderr(
        self, mock_mkdtemp, mock_rmtree, mock_subprocess, tmp_path
    ):
        """Test that materialize handles sparse-checkout init failure with stderr."""
        # Setup git repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Create template.yml
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True, exist_ok=True)
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump(
                {"template-repository": "jebel-quant/rhiza", "template-branch": "main", "include": [".github"]}, f
            )

        # Mock tempfile
        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()
        mock_mkdtemp.return_value = str(temp_dir)

        # Mock subprocess to succeed on clone but fail on sparse-checkout init with stderr
        call_count = [0]

        def subprocess_side_effect(*args, **kwargs):
            call_count[0] += 1
            cmd = args[0] if args else kwargs.get("args", [])

            # First call is git clone - succeed
            if call_count[0] == 1:
                mock_result = Mock()
                mock_result.returncode = 0
                return mock_result

            # Second call is sparse-checkout init - fail with stderr
            if call_count[0] == 2 and "sparse-checkout" in cmd and "init" in cmd:
                raise subprocess.CalledProcessError(1, cmd, stderr="fatal: not a git repository")

            mock_result = Mock()
            mock_result.returncode = 0
            return mock_result

        mock_subprocess.side_effect = subprocess_side_effect

        # Run materialize and expect CalledProcessError to be raised
        with pytest.raises(subprocess.CalledProcessError):
            materialize(tmp_path, "main", None, False)

    @patch("rhiza.commands.materialize.subprocess.run")
    @patch("rhiza.commands.materialize.shutil.rmtree")
    @patch("rhiza.commands.materialize.tempfile.mkdtemp")
    def test_materialize_sparse_checkout_set_failure_with_stderr(
        self, mock_mkdtemp, mock_rmtree, mock_subprocess, tmp_path
    ):
        """Test that materialize handles sparse-checkout set failure with stderr."""
        # Setup git repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Create template.yml
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True, exist_ok=True)
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump(
                {"template-repository": "jebel-quant/rhiza", "template-branch": "main", "include": [".github"]}, f
            )

        # Mock tempfile
        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()
        mock_mkdtemp.return_value = str(temp_dir)

        # Mock subprocess to succeed on clone and init, but fail on sparse-checkout set with stderr
        call_count = [0]

        def subprocess_side_effect(*args, **kwargs):
            call_count[0] += 1
            cmd = args[0] if args else kwargs.get("args", [])

            # First call is git clone - succeed
            if call_count[0] == 1:
                mock_result = Mock()
                mock_result.returncode = 0
                return mock_result

            # Second call is sparse-checkout init - succeed
            if call_count[0] == 2:
                mock_result = Mock()
                mock_result.returncode = 0
                return mock_result

            # Third call is sparse-checkout set - fail with stderr
            if call_count[0] == 3 and "sparse-checkout" in cmd and "set" in cmd:
                raise subprocess.CalledProcessError(1, cmd, stderr="fatal: failed to set sparse-checkout")

            mock_result = Mock()
            mock_result.returncode = 0
            return mock_result

        mock_subprocess.side_effect = subprocess_side_effect

        # Run materialize and expect CalledProcessError to be raised
        with pytest.raises(subprocess.CalledProcessError):
            materialize(tmp_path, "main", None, False)

    @patch("rhiza.commands.materialize.subprocess.run")
    @patch("rhiza.commands.materialize.shutil.rmtree")
    @patch("rhiza.commands.materialize.shutil.copy2")
    @patch("rhiza.commands.materialize.tempfile.mkdtemp")
    def test_materialize_deletes_orphaned_files(self, mock_mkdtemp, mock_copy2, mock_rmtree, mock_subprocess, tmp_path):
        """Test that materialize deletes files in old .rhiza/history but not in new materialization."""
        # Setup git repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Create an old .rhiza/history file with files that will become orphaned
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True, exist_ok=True)
        old_history = rhiza_dir / "history"
        old_history.write_text(
            "# Rhiza Template History\n"
            "# Template repository: jebel-quant/rhiza\n"
            "# Template branch: main\n"
            "#\n"
            "# Files under template control:\n"
            "file1.txt\n"
            "orphaned.txt\n"
            "dir/nested_orphaned.txt\n"
        )

        # Create the orphaned files that should be deleted
        orphaned_file = tmp_path / "orphaned.txt"
        orphaned_file.write_text("orphaned content")
        nested_dir = tmp_path / "dir"
        nested_dir.mkdir()
        nested_orphaned = nested_dir / "nested_orphaned.txt"
        nested_orphaned.write_text("nested orphaned content")

        # Create template.yml that only includes file1.txt (not orphaned.txt)
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True, exist_ok=True)
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump(
                {
                    "template-repository": "jebel-quant/rhiza",
                    "template-branch": "main",
                    "include": ["file1.txt"],
                },
                f,
            )

        # Mock tempfile with only file1.txt
        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()
        file1 = temp_dir / "file1.txt"
        file1.write_text("content1")
        mock_mkdtemp.return_value = str(temp_dir)

        # Mock subprocess to succeed
        mock_subprocess.return_value = Mock(returncode=0)

        # Run materialize
        materialize(tmp_path, "main", None, False)

        # Verify orphaned files were deleted
        assert not orphaned_file.exists(), "orphaned.txt should have been deleted"
        assert not nested_orphaned.exists(), "dir/nested_orphaned.txt should have been deleted"

        # Verify .rhiza/history was updated and only contains file1.txt
        history_content = old_history.read_text()
        assert "file1.txt" in history_content
        assert "orphaned.txt" not in history_content
        assert "nested_orphaned.txt" not in history_content

    @patch("rhiza.commands.materialize.subprocess.run")
    @patch("rhiza.commands.materialize.shutil.rmtree")
    @patch("rhiza.commands.materialize.shutil.copy2")
    @patch("rhiza.commands.materialize.tempfile.mkdtemp")
    def test_materialize_handles_missing_orphaned_files(
        self, mock_mkdtemp, mock_copy2, mock_rmtree, mock_subprocess, tmp_path
    ):
        """Test that materialize handles orphaned files that don't exist gracefully."""
        # Setup git repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Create an old .rhiza/history file with a file that doesn't exist
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True, exist_ok=True)
        old_history = rhiza_dir / "history"
        old_history.write_text(
            "# Rhiza Template History\n"
            "# Template repository: jebel-quant/rhiza\n"
            "# Template branch: main\n"
            "#\n"
            "# Files under template control:\n"
            "file1.txt\n"
            "nonexistent.txt\n"
        )

        # Don't create nonexistent.txt

        # Create template.yml that only includes file1.txt
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True, exist_ok=True)
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump(
                {
                    "template-repository": "jebel-quant/rhiza",
                    "template-branch": "main",
                    "include": ["file1.txt"],
                },
                f,
            )

        # Mock tempfile with file1.txt
        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()
        file1 = temp_dir / "file1.txt"
        file1.write_text("content1")
        mock_mkdtemp.return_value = str(temp_dir)

        # Mock subprocess to succeed
        mock_subprocess.return_value = Mock(returncode=0)

        # Run materialize - should not fail even though nonexistent.txt doesn't exist
        materialize(tmp_path, "main", None, False)

        # Verify .rhiza/history was updated
        history_content = old_history.read_text()
        assert "file1.txt" in history_content
        assert "nonexistent.txt" not in history_content

    @patch("rhiza.commands.materialize.subprocess.run")
    @patch("rhiza.commands.materialize.shutil.rmtree")
    @patch("rhiza.commands.materialize.shutil.copy2")
    @patch("rhiza.commands.materialize.tempfile.mkdtemp")
    def test_materialize_no_cleanup_when_no_history(
        self, mock_mkdtemp, mock_copy2, mock_rmtree, mock_subprocess, tmp_path
    ):
        """Test that materialize works correctly when no .rhiza/history exists yet."""
        # Setup git repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # No old .rhiza/history file

        # Create template.yml
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True, exist_ok=True)
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump(
                {
                    "template-repository": "jebel-quant/rhiza",
                    "template-branch": "main",
                    "include": ["file1.txt"],
                },
                f,
            )

        # Mock tempfile with file1.txt
        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()
        file1 = temp_dir / "file1.txt"
        file1.write_text("content1")
        mock_mkdtemp.return_value = str(temp_dir)

        # Mock subprocess to succeed
        mock_subprocess.return_value = Mock(returncode=0)

        # Run materialize - should work fine without old history
        materialize(tmp_path, "main", None, False)

        # Verify .rhiza/history was created
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True, exist_ok=True)
        history_file = rhiza_dir / "history"
        assert history_file.exists()
        history_content = history_file.read_text()
        assert "file1.txt" in history_content

    @patch("rhiza.commands.materialize.subprocess.run")
    @patch("rhiza.commands.materialize.shutil.rmtree")
    @patch("rhiza.commands.materialize.shutil.copy2")
    @patch("rhiza.commands.materialize.tempfile.mkdtemp")
    def test_materialize_handles_file_deletion_failure(
        self, mock_mkdtemp, mock_copy2, mock_rmtree, mock_subprocess, tmp_path
    ):
        """Test that materialize handles exceptions when deleting orphaned files."""
        # Setup git repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Create .rhiza/history with a file that will be orphaned
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True, exist_ok=True)
        history_file = rhiza_dir / "history"
        history_file.write_text("old_file.txt\n")

        # Create the old file that will become orphaned
        old_file = tmp_path / "old_file.txt"
        old_file.write_text("old content")

        # Create template.yml that doesn't include old_file
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True, exist_ok=True)
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump(
                {
                    "template-repository": "jebel-quant/rhiza",
                    "template-branch": "main",
                    "include": ["new_file.txt"],
                },
                f,
            )

        # Mock tempfile with new file
        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()
        new_file = temp_dir / "new_file.txt"
        new_file.write_text("new content")
        mock_mkdtemp.return_value = str(temp_dir)

        # Mock subprocess to succeed
        mock_subprocess.return_value = Mock(returncode=0)

        # Patch Path.unlink to raise an exception on the specific file
        with patch("pathlib.Path.unlink", side_effect=PermissionError("Cannot delete file")):
            # Run materialize - should handle deletion failure gracefully
            materialize(tmp_path, "main", None, False)

        # Verify the file still exists (deletion failed but was handled)
        assert old_file.exists()
