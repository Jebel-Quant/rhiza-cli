"""Tests for symlink handling in the `materialize` command.

This module tests that symlinks in template repositories are properly resolved
and their targets are automatically checked out and copied.
"""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import yaml

from rhiza.commands.materialize import materialize


class TestMaterializeSymlinks:
    """Tests for symlink handling in materialize command."""

    @patch("rhiza.commands.materialize.subprocess.run")
    @patch("rhiza.commands.materialize.shutil.rmtree")
    @patch("rhiza.commands.materialize.shutil.copy2")
    @patch("rhiza.commands.materialize.tempfile.mkdtemp")
    def test_materialize_resolves_file_symlink(
        self, mock_mkdtemp, mock_copy2, mock_rmtree, mock_subprocess, tmp_path
    ):
        """Test that materialize resolves file symlinks and copies target content."""
        # Setup git repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Create template.yml that includes a symlink
        rhiza_dir = tmp_path / ".github" / "rhiza"
        rhiza_dir.mkdir(parents=True)
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump(
                {
                    "template-repository": "test/repo",
                    "template-branch": "main",
                    "include": ["link_to_file.txt"],  # Only include the symlink
                },
                f,
            )

        # Mock tempfile with a symlink pointing to a real file
        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()

        # Create the real file
        real_file = temp_dir / "real_file.txt"
        real_file.write_text("real content")

        # Create symlink to real file
        symlink = temp_dir / "link_to_file.txt"
        symlink.symlink_to("real_file.txt")

        mock_mkdtemp.return_value = str(temp_dir)

        # Mock subprocess to succeed
        mock_subprocess.return_value = Mock(returncode=0)

        # Run materialize
        materialize(tmp_path, "main", None, False)

        # Verify that sparse-checkout was called twice:
        # 1. First with just the symlink
        # 2. Second with both symlink and its target
        sparse_checkout_calls = [
            call
            for call in mock_subprocess.call_args_list
            if len(call[0]) > 0
            and "sparse-checkout" in call[0][0]
            and "set" in call[0][0]
        ]

        assert len(sparse_checkout_calls) == 2, "Should have two sparse-checkout set calls"

        # Second call should include both the symlink and its target
        second_call_args = sparse_checkout_calls[1][0][0]
        assert "link_to_file.txt" in second_call_args
        assert "real_file.txt" in second_call_args

        # Verify copy2 was called to copy the file
        assert mock_copy2.called

    @patch("rhiza.commands.materialize.subprocess.run")
    @patch("rhiza.commands.materialize.shutil.rmtree")
    @patch("rhiza.commands.materialize.shutil.copy2")
    @patch("rhiza.commands.materialize.tempfile.mkdtemp")
    def test_materialize_resolves_directory_symlink(
        self, mock_mkdtemp, mock_copy2, mock_rmtree, mock_subprocess, tmp_path
    ):
        """Test that materialize resolves directory symlinks and copies target content."""
        # Setup git repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Create template.yml that includes a directory symlink
        rhiza_dir = tmp_path / ".github" / "rhiza"
        rhiza_dir.mkdir(parents=True)
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump(
                {
                    "template-repository": "test/repo",
                    "template-branch": "main",
                    "include": [".gitlab"],  # Symlink to .github
                },
                f,
            )

        # Mock tempfile with a directory symlink
        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()

        # Create the real directory with content
        real_dir = temp_dir / ".github"
        real_dir.mkdir()
        (real_dir / "workflows").mkdir()
        (real_dir / "workflows" / "ci.yml").write_text("workflow: content")
        (real_dir / "CODEOWNERS").write_text("* @owner")

        # Create symlink to real directory
        symlink_dir = temp_dir / ".gitlab"
        symlink_dir.symlink_to(".github")

        mock_mkdtemp.return_value = str(temp_dir)

        # Mock subprocess to succeed
        mock_subprocess.return_value = Mock(returncode=0)

        # Run materialize
        materialize(tmp_path, "main", None, False)

        # Verify that sparse-checkout was updated to include the target
        sparse_checkout_calls = [
            call
            for call in mock_subprocess.call_args_list
            if len(call[0]) > 0
            and "sparse-checkout" in call[0][0]
            and "set" in call[0][0]
        ]

        assert len(sparse_checkout_calls) == 2, "Should have two sparse-checkout set calls"

        # Second call should include both .gitlab and .github
        second_call_args = sparse_checkout_calls[1][0][0]
        assert ".gitlab" in second_call_args
        assert ".github" in second_call_args

        # Verify files were copied
        assert mock_copy2.called

    @patch("rhiza.commands.materialize.subprocess.run")
    @patch("rhiza.commands.materialize.shutil.rmtree")
    @patch("rhiza.commands.materialize.shutil.copy2")
    @patch("rhiza.commands.materialize.tempfile.mkdtemp")
    def test_materialize_symlink_creates_correct_destination_paths(
        self, mock_mkdtemp, mock_copy2, mock_rmtree, mock_subprocess, tmp_path
    ):
        """Test that files from symlinked directories are placed at symlink path."""
        # Setup git repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Create template.yml
        rhiza_dir = tmp_path / ".github" / "rhiza"
        rhiza_dir.mkdir(parents=True)
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump(
                {
                    "template-repository": "test/repo",
                    "template-branch": "main",
                    "include": [".gitlab"],
                },
                f,
            )

        # Mock tempfile
        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()

        # Create real directory structure
        real_dir = temp_dir / ".github"
        real_dir.mkdir()
        (real_dir / "ci.yml").write_text("ci config")

        # Create symlink
        symlink_dir = temp_dir / ".gitlab"
        symlink_dir.symlink_to(".github")

        mock_mkdtemp.return_value = str(temp_dir)
        mock_subprocess.return_value = Mock(returncode=0)

        # Run materialize
        materialize(tmp_path, "main", None, False)

        # Check that copy2 was called with destination under .gitlab (not .github)
        copy_calls = mock_copy2.call_args_list
        assert len(copy_calls) > 0

        # At least one call should have .gitlab in the destination path
        destination_paths = [str(call[0][1]) for call in copy_calls]
        assert any(".gitlab" in path for path in destination_paths), \
            f"Expected .gitlab in destination paths, got: {destination_paths}"

    @patch("rhiza.commands.materialize.subprocess.run")
    @patch("rhiza.commands.materialize.shutil.rmtree")
    @patch("rhiza.commands.materialize.shutil.copy2")
    @patch("rhiza.commands.materialize.tempfile.mkdtemp")
    def test_materialize_symlink_with_nested_files(
        self, mock_mkdtemp, mock_copy2, mock_rmtree, mock_subprocess, tmp_path
    ):
        """Test that nested files in symlinked directories are handled correctly."""
        # Setup git repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Create template.yml
        rhiza_dir = tmp_path / ".github" / "rhiza"
        rhiza_dir.mkdir(parents=True)
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump(
                {
                    "template-repository": "test/repo",
                    "template-branch": "main",
                    "include": ["link_dir"],
                },
                f,
            )

        # Mock tempfile with nested structure
        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()

        # Create real directory with nested files
        real_dir = temp_dir / "real_dir"
        real_dir.mkdir()
        (real_dir / "file1.txt").write_text("file1")
        subdir = real_dir / "subdir"
        subdir.mkdir()
        (subdir / "file2.txt").write_text("file2")
        (subdir / "file3.txt").write_text("file3")

        # Create symlink
        symlink_dir = temp_dir / "link_dir"
        symlink_dir.symlink_to("real_dir")

        mock_mkdtemp.return_value = str(temp_dir)
        mock_subprocess.return_value = Mock(returncode=0)

        # Run materialize
        materialize(tmp_path, "main", None, False)

        # Verify all nested files were copied
        copy_calls = mock_copy2.call_args_list
        assert len(copy_calls) == 3, "Should copy all 3 files"

        # All destination paths should be under link_dir, not real_dir
        destination_paths = [str(call[0][1]) for call in copy_calls]
        assert all("link_dir" in path for path in destination_paths)
        assert not any("real_dir" in path for path in destination_paths)

    @patch("rhiza.commands.materialize.subprocess.run")
    @patch("rhiza.commands.materialize.shutil.rmtree")
    @patch("rhiza.commands.materialize.tempfile.mkdtemp")
    def test_materialize_broken_symlink_logs_warning(
        self, mock_mkdtemp, mock_rmtree, mock_subprocess, tmp_path
    ):
        """Test that broken symlinks (target doesn't exist) are handled gracefully."""
        # Setup git repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Create template.yml
        rhiza_dir = tmp_path / ".github" / "rhiza"
        rhiza_dir.mkdir(parents=True)
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump(
                {
                    "template-repository": "test/repo",
                    "template-branch": "main",
                    "include": ["broken_link"],
                },
                f,
            )

        # Mock tempfile with a broken symlink
        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()

        # Create broken symlink (target doesn't exist)
        broken_link = temp_dir / "broken_link"
        broken_link.symlink_to("nonexistent_target")

        mock_mkdtemp.return_value = str(temp_dir)
        mock_subprocess.return_value = Mock(returncode=0)

        # Run materialize - should not crash
        with patch("rhiza.commands.materialize.logger") as mock_logger:
            materialize(tmp_path, "main", None, False)

            # Should log a warning about the broken symlink
            warning_calls = [call for call in mock_logger.warning.call_args_list]
            assert len(warning_calls) > 0, "Should log warning for broken symlink"

    @patch("rhiza.commands.materialize.subprocess.run")
    @patch("rhiza.commands.materialize.shutil.rmtree")
    @patch("rhiza.commands.materialize.shutil.copy2")
    @patch("rhiza.commands.materialize.tempfile.mkdtemp")
    def test_materialize_multiple_symlinks(
        self, mock_mkdtemp, mock_copy2, mock_rmtree, mock_subprocess, tmp_path
    ):
        """Test that multiple symlinks are all resolved correctly."""
        # Setup git repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Create template.yml with multiple symlinks
        rhiza_dir = tmp_path / ".github" / "rhiza"
        rhiza_dir.mkdir(parents=True)
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump(
                {
                    "template-repository": "test/repo",
                    "template-branch": "main",
                    "include": ["link1.txt", "link2.txt", "linkdir"],
                },
                f,
            )

        # Mock tempfile with multiple symlinks
        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()

        # Create real files
        (temp_dir / "file1.txt").write_text("content1")
        (temp_dir / "file2.txt").write_text("content2")
        real_dir = temp_dir / "realdir"
        real_dir.mkdir()
        (real_dir / "file3.txt").write_text("content3")

        # Create symlinks
        (temp_dir / "link1.txt").symlink_to("file1.txt")
        (temp_dir / "link2.txt").symlink_to("file2.txt")
        (temp_dir / "linkdir").symlink_to("realdir")

        mock_mkdtemp.return_value = str(temp_dir)
        mock_subprocess.return_value = Mock(returncode=0)

        # Run materialize
        materialize(tmp_path, "main", None, False)

        # Verify all targets were added to sparse checkout
        sparse_checkout_calls = [
            call
            for call in mock_subprocess.call_args_list
            if len(call[0]) > 0
            and "sparse-checkout" in call[0][0]
            and "set" in call[0][0]
        ]

        assert len(sparse_checkout_calls) == 2
        second_call_args = sparse_checkout_calls[1][0][0]

        # Should include all original paths plus targets
        assert "link1.txt" in second_call_args
        assert "link2.txt" in second_call_args
        assert "linkdir" in second_call_args
        assert "file1.txt" in second_call_args
        assert "file2.txt" in second_call_args
        assert "realdir" in second_call_args
