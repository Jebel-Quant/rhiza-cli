"""Tests that ``rhiza sync`` never materializes a symlink in a downstream project.

The upstream Rhiza template repo dogfoods its own templates via symlinks at the repo
root, and a future bundle could in principle contain a symlink too. Downstream
projects must always receive **real files** — a synced symlink would dangle (its
relative target does not exist in the consumer's tree) and, for git-special files, be
silently ignored. rhiza-cli guarantees this by dereferencing symlinks to their real
content while building the snapshot (``_prepare_snapshot``) and copying it into the
target (``_copy_files_to_target``), both via ``shutil.copy2`` with the default
``follow_symlinks=True``.

That guarantee was previously unguarded — nothing pinned the dereferencing behaviour,
so a switch to ``copy2(..., follow_symlinks=False)`` or ``copytree(..., symlinks=True)``
would silently start shipping broken symlinks. These tests lock it in at two levels:

* :class:`TestPrepareSnapshotDereferencesSymlinks` exercises the real
  ``_prepare_snapshot`` directly against a clone tree that contains a file symlink, a
  file symlink nested inside an included directory, and a directory symlink.
* :class:`TestSyncEndToEndDereferencesSymlinks` drives the full ``sync`` entry-point
  (mocking only the network clone) and asserts the file that lands in the target
  project is a real file with the dereferenced content.

Security Notes:
- S101 (assert usage): Asserts are the standard way to validate test conditions in pytest.
- S603 (subprocess without shell=True): Subprocess calls use explicit argument lists
  without shell=True, which is the safe pattern for invoking git in tests.
"""

import subprocess  # nosec B404
from pathlib import Path
from unittest.mock import patch

import pytest

from rhiza.commands.sync import sync
from rhiza.models._git.snapshot import _prepare_snapshot


def _symlink_or_skip(link: Path, target: str) -> None:
    """Create ``link`` pointing at ``target``, skipping the test if unsupported.

    Symlink creation can fail on Windows without the required privilege; in that case
    the test is skipped rather than failed, since the dereferencing guarantee is only
    meaningful where symlinks exist.

    Args:
        link: The symlink path to create.
        target: The (relative) path the symlink should point at.
    """
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError) as exc:  # pragma: no cover - platform dependent
        pytest.skip(f"cannot create symlinks on this platform: {exc}")


class TestPrepareSnapshotDereferencesSymlinks:
    """Verify the snapshot builder resolves every symlink to a real file."""

    def test_symlinks_become_real_files_with_dereferenced_content(self, tmp_path: Path) -> None:
        """A clone containing file/nested/dir symlinks yields a snapshot of only real files.

        The snapshot must contain no symlinks at all, and every resolved file must carry
        the content of the symlink's target — this is exactly what a downstream project
        would receive.
        """
        clone = tmp_path / "clone"
        (clone / "pkg").mkdir(parents=True)

        # A real file plus a top-level symlink to it.
        (clone / "real.txt").write_text("real content\n")
        _symlink_or_skip(clone / "link.txt", "real.txt")

        # A real file inside an included directory plus a symlink beside it.
        (clone / "pkg" / "mod.txt").write_text("module content\n")
        _symlink_or_skip(clone / "pkg" / "mod_link.txt", "mod.txt")

        # A directory symlink pointing at the included directory.
        _symlink_or_skip(clone / "dirlink", "pkg")

        snapshot = tmp_path / "snapshot"
        include = ["real.txt", "link.txt", "pkg", "dirlink"]
        materialized = _prepare_snapshot(clone, include, set(), snapshot)

        # The file symlink was resolved to a real file with its target's content.
        link_out = snapshot / "link.txt"
        assert not link_out.is_symlink(), "file symlink must be materialized as a real file"
        assert link_out.read_text() == "real content\n"

        # The symlink nested inside the included directory was resolved too.
        nested_out = snapshot / "pkg" / "mod_link.txt"
        assert not nested_out.is_symlink(), "nested symlink must be materialized as a real file"
        assert nested_out.read_text() == "module content\n"

        # Files reached via the directory symlink are real files as well.
        dirlink_out = snapshot / "dirlink" / "mod.txt"
        assert not dirlink_out.is_symlink(), "files under a symlinked dir must be real files"
        assert dirlink_out.read_text() == "module content\n"

        # Belt-and-suspenders: nothing anywhere in the snapshot is a symlink.
        surviving = [p for p in snapshot.rglob("*") if p.is_symlink()]
        assert not surviving, f"snapshot must contain no symlinks, found: {surviving}"

        # The symlink entries were included in the materialized set.
        materialized_str = {str(p) for p in materialized}
        assert "link.txt" in materialized_str
        assert str(Path("pkg") / "mod_link.txt") in materialized_str


class TestSyncEndToEndDereferencesSymlinks:
    """Drive the full sync entry-point and assert the target receives a real file."""

    @patch("rhiza.commands._sync_helpers._warn_about_workflow_files")
    def test_sync_materializes_symlink_as_real_file(self, mock_warn, git_project, git_ctx, tmp_path) -> None:
        """A symlinked template file lands in the target project as a real, dereferenced file.

        Only the network clone (``_clone_template``) is mocked; the real
        ``_prepare_snapshot`` and copy-to-target paths run, so this proves the whole sync
        pipeline dereferences symlinks end to end.
        """
        project = git_project
        (project / "pyproject.toml").write_text('[project]\nname = "myapp"\n')
        rhiza_dir = project / ".rhiza"
        rhiza_dir.mkdir()
        (rhiza_dir / "template.yml").write_text(
            "template-repository: jebel-quant/rhiza\ntemplate-branch: main\ninclude:\n  - real.txt\n  - link.txt\n"
        )
        subprocess.run(  # nosec B603
            [git_ctx.executable, "add", "."], cwd=project, check=True, capture_output=True, env=git_ctx.env
        )
        subprocess.run(  # nosec B603
            [git_ctx.executable, "commit", "-m", "init"], cwd=project, check=True, capture_output=True, env=git_ctx.env
        )

        # Simulate the upstream clone: a real file and a symlink pointing at it.
        clone_dir = tmp_path / "clone"
        clone_dir.mkdir()
        (clone_dir / "real.txt").write_text("dereferenced content\n")
        _symlink_or_skip(clone_dir / "link.txt", "real.txt")

        def fake_clone(template, git_ctx_, branch="main"):
            """Return the local clone dir in place of a network sparse-checkout."""
            return clone_dir, "sha_symlink", list(template.include), {}

        with patch("rhiza.commands.sync._clone_template", side_effect=fake_clone):
            sync(target=project, branch="main", target_branch=None, strategy="merge")

        synced = project / "link.txt"
        assert synced.exists(), "symlinked template file must be synced into the target"
        assert not synced.is_symlink(), "sync must materialize a real file, never a symlink"
        assert synced.read_text() == "dereferenced content\n"
