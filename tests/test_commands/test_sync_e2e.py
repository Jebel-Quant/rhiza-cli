"""End-to-end tests for the sync command.

These tests exercise the five key behavioural guarantees of ``rhiza sync``:

1. **Typical workflow** – a first sync copies all template files; a subsequent
   sync applies upstream changes while leaving unrelated local files in place.
2. **Orphaned files** – when ``template.yml`` stops including a file it is
   deleted from the project on the next sync.
3. **3-way merge** – when the user has edited a file locally, a subsequent
   sync applies upstream template changes via a 3-way merge so that local
   modifications are *not* overwritten.
4. **Excluded files** – files listed under ``exclude:`` in ``template.yml``
   are never removed, even if they were previously tracked by the template.
5. **Updated template.yml** – when the user edits the ``include:`` list in
   their local ``template.yml`` (adding or removing entries), the next
   ``rhiza sync`` picks up the changes correctly: new entries cause the
   corresponding files to be fetched from the template; removed entries cause
   previously-synced files to be treated as orphans and deleted.

The tests use real git repositories (``git_project`` / ``git_setup``
fixtures from ``conftest.py``) and real file-system operations.  Only
``_clone_at_sha`` / ``RhizaTemplate.clone`` are mocked, since those
helpers would otherwise attempt a network clone; the mocks simply populate
the destination directory from a local "template vN" snapshot that the test
itself builds.

Security Notes:
- S101 (assert usage): Asserts are the standard way to validate test
  conditions in pytest.
- S603 (subprocess without shell=True): Subprocess calls use explicit
  argument lists without shell=True, which is the safe pattern for invoking
  git in tests.
- S607 (partial executable path): git is resolved via shutil.which() in the
  ``git_setup`` fixture.
"""

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from rhiza.commands._sync_helpers import (
    _read_lock,
    _sync_merge,
)
from rhiza.commands.sync import sync
from rhiza.models import RhizaTemplate, TemplateLock

# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _git_commit_all(project: Path, git_executable: str, git_env: dict, message: str = "commit") -> str:
    """Stage all files and create a commit.  Returns the new HEAD SHA."""
    subprocess.run(  # nosec B603
        [git_executable, "add", "."],
        cwd=project,
        check=True,
        capture_output=True,
        env=git_env,
    )
    subprocess.run(  # nosec B603
        [git_executable, "commit", "-m", message],
        cwd=project,
        check=True,
        capture_output=True,
        env=git_env,
    )
    result = subprocess.run(  # nosec B603
        [git_executable, "rev-parse", "HEAD"],
        cwd=project,
        capture_output=True,
        text=True,
        check=True,
        env=git_env,
    )
    return result.stdout.strip()


def _make_lock(sha: str, files: list[str]) -> TemplateLock:
    """Build a minimal :class:`TemplateLock` for use in tests."""
    return TemplateLock(
        sha=sha,
        repo="jebel-quant/rhiza",
        host="github",
        ref="main",
        include=[],
        exclude=[],
        templates=[],
        files=files,
    )


# ---------------------------------------------------------------------------
# Shared project fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def project(git_project, git_setup):
    """A git-initialised project with an initial commit."""
    git_executable, git_env = git_setup
    project = git_project
    (project / "pyproject.toml").write_text('[project]\nname = "myapp"\n')
    rhiza_dir = project / ".rhiza"
    rhiza_dir.mkdir()
    (rhiza_dir / "template.yml").write_text(
        "template-repository: jebel-quant/rhiza\n"
        "template-branch: main\n"
        "include:\n  - Makefile\n  - config.py\n  - README.md\n"
    )
    _git_commit_all(project, git_executable, git_env, "init project")
    return project


# ---------------------------------------------------------------------------
# 1. Typical workflow
# ---------------------------------------------------------------------------


class TestSyncE2ETypicalWorkflow:
    """End-to-end tests for the typical first-then-subsequent-sync workflow."""

    def test_first_sync_copies_all_template_files(self, project, git_setup, tmp_path):
        """First sync (no lock file) copies every materialized template file into target."""
        git_executable, git_env = git_setup

        upstream = tmp_path / "upstream"
        upstream.mkdir()
        (upstream / "Makefile").write_text("install:\n\tpip install .\n")
        (upstream / "config.py").write_text("version = 1\n")
        (upstream / "README.md").write_text("# My Project\n")

        materialized = [Path("Makefile"), Path("config.py"), Path("README.md")]

        with patch("rhiza.models.RhizaTemplate._clone_at_sha"):
            _sync_merge(
                target=project,
                upstream_snapshot=upstream,
                base_sha=None,
                materialized=materialized,
                template=RhizaTemplate(
                    template_repository="example/repo", include=["Makefile", "config.py", "README.md"]
                ),
                include_paths=["Makefile", "config.py", "README.md"],
                excludes=set(),
                git_executable=git_executable,
                git_env=git_env,
                lock=_make_lock("sha_v1", [str(p) for p in materialized]),
            )

        assert (project / "Makefile").exists()
        assert (project / "config.py").exists()
        assert (project / "README.md").exists()
        assert "pip install" in (project / "Makefile").read_text()
        assert "version = 1" in (project / "config.py").read_text()
        assert _read_lock(project) == "sha_v1"

    @patch("rhiza.commands._sync_helpers._warn_about_workflow_files")
    def test_subsequent_sync_applies_template_changes(self, mock_warn, project, git_setup, tmp_path):
        """After first sync, a second sync applies upstream changes and removes orphaned files.

        Timeline:
        - Template v1: Makefile, config.py, README.md
        - User modifies config.py locally.
        - Template v2: Makefile updated (adds test target), README.md removed,
          new.yml added.
        Expected after second sync:
        - Makefile contains the new ``test`` target.
        - config.py retains the user's local edit (template did not change it).
        - README.md deleted (orphaned).
        - new.yml added.
        - Lock SHA updated to sha_v2.
        """
        git_executable, git_env = git_setup

        # ------------------------------------------------------------------
        # First sync
        # ------------------------------------------------------------------
        upstream_v1 = tmp_path / "upstream_v1"
        upstream_v1.mkdir()
        (upstream_v1 / "Makefile").write_text("install:\n\tpip install .\n")
        (upstream_v1 / "config.py").write_text("version = 1\napi = 'default'\n")
        (upstream_v1 / "README.md").write_text("# My Project\n")

        materialized_v1 = [Path("Makefile"), Path("config.py"), Path("README.md")]

        with patch("rhiza.models.RhizaTemplate._clone_at_sha"):
            _sync_merge(
                target=project,
                upstream_snapshot=upstream_v1,
                base_sha=None,
                materialized=materialized_v1,
                template=RhizaTemplate(
                    template_repository="example/repo", include=["Makefile", "config.py", "README.md"]
                ),
                include_paths=["Makefile", "config.py", "README.md"],
                excludes=set(),
                git_executable=git_executable,
                git_env=git_env,
                lock=_make_lock("sha_v1", [str(p) for p in materialized_v1]),
            )

        assert (project / "README.md").exists()

        # ------------------------------------------------------------------
        # User modifies config.py (template did not change this file)
        # ------------------------------------------------------------------
        (project / "config.py").write_text("version = 1\napi = 'my_custom_key'\n")
        _git_commit_all(project, git_executable, git_env, "customise config")

        # ------------------------------------------------------------------
        # Template v2: Makefile updated, README.md removed, new.yml added
        # ------------------------------------------------------------------
        upstream_v2 = tmp_path / "upstream_v2"
        upstream_v2.mkdir()
        (upstream_v2 / "Makefile").write_text("install:\n\tpip install .\n\ntest:\n\tpytest\n")
        (upstream_v2 / "config.py").write_text("version = 1\napi = 'default'\n")
        (upstream_v2 / "new.yml").write_text("feature: enabled\n")

        materialized_v2 = [Path("Makefile"), Path("config.py"), Path("new.yml")]

        def populate_base(sha, dest, include_paths, git_exe, git_env_):
            """Populate the base-snapshot directory with template v1 content."""
            (dest / "Makefile").write_text("install:\n\tpip install .\n")
            (dest / "config.py").write_text("version = 1\napi = 'default'\n")
            (dest / "README.md").write_text("# My Project\n")

        with patch("rhiza.models.RhizaTemplate._clone_at_sha", side_effect=populate_base):
            _sync_merge(
                target=project,
                upstream_snapshot=upstream_v2,
                base_sha="sha_v1",
                materialized=materialized_v2,
                template=RhizaTemplate(
                    template_repository="example/repo", include=["Makefile", "config.py", "new.yml"]
                ),
                include_paths=["Makefile", "config.py", "new.yml"],
                excludes=set(),
                git_executable=git_executable,
                git_env=git_env,
                lock=_make_lock("sha_v2", [str(p) for p in materialized_v2]),
            )

        # Template added a ``test`` target to Makefile.
        assert "pytest" in (project / "Makefile").read_text()

        # User's local edit to config.py is preserved (template didn't change it).
        assert "my_custom_key" in (project / "config.py").read_text()

        # README.md is orphaned (template v2 no longer includes it).
        assert not (project / "README.md").exists()

        # new.yml was added by the template.
        assert (project / "new.yml").exists()
        assert "feature" in (project / "new.yml").read_text()

        # Lock is updated to sha_v2.
        assert _read_lock(project) == "sha_v2"


# ---------------------------------------------------------------------------
# 2. Orphaned files
# ---------------------------------------------------------------------------


class TestSyncE2EOrphanedFiles:
    """End-to-end tests verifying orphaned-file removal when the template changes."""

    @patch("rhiza.commands._sync_helpers._warn_about_workflow_files")
    def test_orphaned_files_removed_when_template_removes_a_file(self, mock_warn, project, git_setup, tmp_path):
        """Files tracked in the previous lock but absent from the new template are deleted.

        Template v1 includes file_a.txt and file_b.txt; template v2 only
        includes file_a.txt.  After the second sync file_b.txt must be gone.
        """
        git_executable, git_env = git_setup

        # First sync: template has both files.
        upstream_v1 = tmp_path / "upstream_v1"
        upstream_v1.mkdir()
        (upstream_v1 / "file_a.txt").write_text("content a\n")
        (upstream_v1 / "file_b.txt").write_text("content b\n")

        materialized_v1 = [Path("file_a.txt"), Path("file_b.txt")]

        with patch("rhiza.models.RhizaTemplate._clone_at_sha"):
            _sync_merge(
                target=project,
                upstream_snapshot=upstream_v1,
                base_sha=None,
                materialized=materialized_v1,
                template=RhizaTemplate(template_repository="example/repo", include=["file_a.txt", "file_b.txt"]),
                include_paths=["file_a.txt", "file_b.txt"],
                excludes=set(),
                git_executable=git_executable,
                git_env=git_env,
                lock=_make_lock("sha_v1", ["file_a.txt", "file_b.txt"]),
            )

        assert (project / "file_a.txt").exists()
        assert (project / "file_b.txt").exists()

        # Second sync: template v2 dropped file_b.txt.
        upstream_v2 = tmp_path / "upstream_v2"
        upstream_v2.mkdir()
        (upstream_v2 / "file_a.txt").write_text("content a updated\n")

        materialized_v2 = [Path("file_a.txt")]

        def populate_base(sha, dest, include_paths, git_exe, git_env_):
            (dest / "file_a.txt").write_text("content a\n")
            (dest / "file_b.txt").write_text("content b\n")

        with patch("rhiza.models.RhizaTemplate._clone_at_sha", side_effect=populate_base):
            _sync_merge(
                target=project,
                upstream_snapshot=upstream_v2,
                base_sha="sha_v1",
                materialized=materialized_v2,
                template=RhizaTemplate(template_repository="example/repo", include=["file_a.txt"]),
                include_paths=["file_a.txt"],
                excludes=set(),
                git_executable=git_executable,
                git_env=git_env,
                lock=_make_lock("sha_v2", ["file_a.txt"]),
            )

        assert (project / "file_a.txt").exists()
        assert not (project / "file_b.txt").exists(), "file_b.txt should be removed as an orphan"

        assert _read_lock(project) == "sha_v2"


# ---------------------------------------------------------------------------
# 3. Three-way merge
# ---------------------------------------------------------------------------


class TestSyncE2EThreeWayMerge:
    """End-to-end tests verifying that local user changes survive a sync."""

    @patch("rhiza.commands._sync_helpers._warn_about_workflow_files")
    def test_user_changes_not_overwritten_by_sync(self, mock_warn, project, git_setup, tmp_path):
        """Local modifications to a file are preserved when the template also changes it.

        The user changes line 2 (api key); the template changes line 1
        (version number).  After a 3-way merge both changes must be present.
        """
        git_executable, git_env = git_setup

        template_v1 = "version = 1\napi = 'default'\n"

        # First sync: copy template v1 into project.
        upstream_v1 = tmp_path / "upstream_v1"
        upstream_v1.mkdir()
        (upstream_v1 / "config.py").write_text(template_v1)

        with patch("rhiza.models.RhizaTemplate._clone_at_sha"):
            _sync_merge(
                target=project,
                upstream_snapshot=upstream_v1,
                base_sha=None,
                materialized=[Path("config.py")],
                template=RhizaTemplate(template_repository="example/repo", include=["config.py"]),
                include_paths=["config.py"],
                excludes=set(),
                git_executable=git_executable,
                git_env=git_env,
                lock=_make_lock("sha_v1", ["config.py"]),
            )

        assert (project / "config.py").read_text() == template_v1

        # User edits line 2 (api key).
        (project / "config.py").write_text("version = 1\napi = 'my_key'\n")
        _git_commit_all(project, git_executable, git_env, "customise api key")

        # Template v2: version bumped on line 1, api key unchanged.
        upstream_v2 = tmp_path / "upstream_v2"
        upstream_v2.mkdir()
        (upstream_v2 / "config.py").write_text("version = 2\napi = 'default'\n")

        def populate_base(sha, dest, include_paths, git_exe, git_env_):
            (dest / "config.py").write_text(template_v1)

        with patch("rhiza.models.RhizaTemplate._clone_at_sha", side_effect=populate_base):
            _sync_merge(
                target=project,
                upstream_snapshot=upstream_v2,
                base_sha="sha_v1",
                materialized=[Path("config.py")],
                template=RhizaTemplate(template_repository="example/repo", include=["config.py"]),
                include_paths=["config.py"],
                excludes=set(),
                git_executable=git_executable,
                git_env=git_env,
                lock=_make_lock("sha_v2", ["config.py"]),
            )

        result = (project / "config.py").read_text()

        # Template's version bump must be applied.
        assert "version = 2" in result, f"expected template's version bump; got:\n{result}"

        # User's api-key customisation must survive.
        assert "my_key" in result, f"expected user's api-key change to survive; got:\n{result}"


# ---------------------------------------------------------------------------
# 4. Excluded files
# ---------------------------------------------------------------------------


class TestSyncE2EExcludedFiles:
    """End-to-end tests verifying that excluded files are never removed."""

    @patch("rhiza.commands._sync_helpers._warn_about_workflow_files")
    def test_local_only_file_not_removed_when_not_tracked(self, mock_warn, project, git_setup, tmp_path):
        """A file that was never tracked by the template is never deleted by sync.

        The user has a local ``secrets.env`` that is not in the template at
        all.  After any sync it must remain untouched.
        """
        git_executable, git_env = git_setup

        # User-owned file, not part of the template.
        (project / "secrets.env").write_text("API_KEY=supersecret\n")

        upstream = tmp_path / "upstream"
        upstream.mkdir()
        (upstream / "Makefile").write_text("install:\n\tpip install .\n")

        with patch("rhiza.models.RhizaTemplate._clone_at_sha"):
            _sync_merge(
                target=project,
                upstream_snapshot=upstream,
                base_sha=None,
                materialized=[Path("Makefile")],
                template=RhizaTemplate(template_repository="example/repo", include=["Makefile"]),
                include_paths=["Makefile"],
                excludes=set(),
                git_executable=git_executable,
                git_env=git_env,
                lock=_make_lock("sha_v1", ["Makefile"]),
            )

        assert (project / "secrets.env").exists(), "local-only file must never be deleted by sync"

    @patch("rhiza.commands._sync_helpers._warn_about_workflow_files")
    def test_previously_tracked_file_excluded_is_not_removed(self, mock_warn, project, git_setup, tmp_path):
        """A file that was synced before but is now excluded must not be deleted.

        Timeline:
        - Sync 1 (no excludes): file_a.txt and file_b.txt both tracked.
        - User adds file_b.txt to the ``exclude:`` list.
        - Sync 2: file_b.txt is excluded (not in materialized), but it is
          also in ``excludes``, so the orphan-cleanup must leave it alone.
        """
        git_executable, git_env = git_setup

        # First sync: both files tracked.
        upstream_v1 = tmp_path / "upstream_v1"
        upstream_v1.mkdir()
        (upstream_v1 / "file_a.txt").write_text("content a\n")
        (upstream_v1 / "file_b.txt").write_text("content b\n")

        materialized_v1 = [Path("file_a.txt"), Path("file_b.txt")]

        with patch("rhiza.models.RhizaTemplate._clone_at_sha"):
            _sync_merge(
                target=project,
                upstream_snapshot=upstream_v1,
                base_sha=None,
                materialized=materialized_v1,
                template=RhizaTemplate(template_repository="example/repo", include=["file_a.txt", "file_b.txt"]),
                include_paths=["file_a.txt", "file_b.txt"],
                excludes=set(),
                git_executable=git_executable,
                git_env=git_env,
                lock=_make_lock("sha_v1", ["file_a.txt", "file_b.txt"]),
            )

        assert (project / "file_a.txt").exists()
        assert (project / "file_b.txt").exists()

        # Second sync: user has excluded file_b.txt.
        upstream_v2 = tmp_path / "upstream_v2"
        upstream_v2.mkdir()
        (upstream_v2 / "file_a.txt").write_text("content a updated\n")
        (upstream_v2 / "file_b.txt").write_text("content b\n")  # still in template

        materialized_v2 = [Path("file_a.txt")]  # file_b excluded from materialized

        def populate_base(sha, dest, include_paths, git_exe, git_env_):
            (dest / "file_a.txt").write_text("content a\n")
            (dest / "file_b.txt").write_text("content b\n")

        with patch("rhiza.models.RhizaTemplate._clone_at_sha", side_effect=populate_base):
            _sync_merge(
                target=project,
                upstream_snapshot=upstream_v2,
                base_sha="sha_v1",
                materialized=materialized_v2,
                template=RhizaTemplate(template_repository="example/repo", include=["file_a.txt", "file_b.txt"]),
                include_paths=["file_a.txt", "file_b.txt"],
                excludes={"file_b.txt"},
                git_executable=git_executable,
                git_env=git_env,
                lock=_make_lock("sha_v2", ["file_a.txt"]),
            )

        assert (project / "file_a.txt").exists()
        assert (project / "file_b.txt").exists(), "file_b.txt must not be removed: it is excluded, not orphaned"
        # file_b.txt should still have original content (not touched by sync).
        assert (project / "file_b.txt").read_text() == "content b\n"

        assert _read_lock(project) == "sha_v2"


# ---------------------------------------------------------------------------
# 5. Updated template.yml
# ---------------------------------------------------------------------------


class TestSyncE2EUpdatedTemplateYml:
    """End-to-end tests for sync behaviour when the local template.yml is edited.

    These tests exercise the full :func:`~rhiza.commands.sync.sync` entry-point
    (rather than ``_sync_merge`` directly) and mock only the network-touching
    :meth:`~rhiza.models.RhizaTemplate.clone` method.  The ``_clone_at_sha``
    helper is additionally mocked for the second sync so that the 3-way-merge
    base snapshot is populated correctly without a real git clone.
    """

    @patch("rhiza.commands._sync_helpers._warn_about_workflow_files")
    def test_adding_include_entry_syncs_new_file(self, mock_warn, project, git_setup, tmp_path):
        """Adding a path to include: in template.yml causes the file to appear after the next sync.

        Timeline:
        - template.yml v1: ``include: [file_a.txt, file_b.txt]``
        - Sync 1: both files copied into project.
        - User edits template.yml: ``include: [file_a.txt, file_b.txt, file_c.txt]``
        - Sync 2: ``file_c.txt`` is fetched from the template and added to the project.

        Expected after sync 2: ``file_c.txt`` exists alongside the existing files.
        """
        git_executable, git_env = git_setup

        # ------------------------------------------------------------------
        # Configure template.yml v1: file_a.txt and file_b.txt
        # ------------------------------------------------------------------
        (project / ".rhiza" / "template.yml").write_text(
            "template-repository: jebel-quant/rhiza\ntemplate-branch: main\ninclude:\n  - file_a.txt\n  - file_b.txt\n"
        )
        _git_commit_all(project, git_executable, git_env, "template.yml v1: file_a + file_b")

        # ------------------------------------------------------------------
        # Sync 1 (first sync — no lock yet)
        # ------------------------------------------------------------------
        upstream_dir_v1 = tmp_path / "upstream_v1"
        upstream_dir_v1.mkdir()
        (upstream_dir_v1 / "file_a.txt").write_text("content a\n")
        (upstream_dir_v1 / "file_b.txt").write_text("content b\n")

        def clone_v1(git_exe, git_env_, branch="main"):
            return upstream_dir_v1, "sha_v1", ["file_a.txt", "file_b.txt"]

        with patch.object(RhizaTemplate, "clone", side_effect=clone_v1):
            sync(target=project, branch="main", target_branch=None, strategy="merge")

        assert (project / "file_a.txt").exists()
        assert (project / "file_b.txt").exists()
        assert _read_lock(project) == "sha_v1"

        _git_commit_all(project, git_executable, git_env, "after sync 1")

        # ------------------------------------------------------------------
        # User adds file_c.txt to the include: list in template.yml
        # ------------------------------------------------------------------
        (project / ".rhiza" / "template.yml").write_text(
            "template-repository: jebel-quant/rhiza\n"
            "template-branch: main\n"
            "include:\n  - file_a.txt\n  - file_b.txt\n  - file_c.txt\n"
        )
        _git_commit_all(project, git_executable, git_env, "template.yml v2: add file_c.txt")

        # ------------------------------------------------------------------
        # Sync 2 — template.yml now requests file_c.txt
        # ------------------------------------------------------------------
        upstream_dir_v2 = tmp_path / "upstream_v2"
        upstream_dir_v2.mkdir()
        (upstream_dir_v2 / "file_a.txt").write_text("content a\n")
        (upstream_dir_v2 / "file_b.txt").write_text("content b\n")
        (upstream_dir_v2 / "file_c.txt").write_text("content c\n")

        def clone_v2(git_exe, git_env_, branch="main"):
            return upstream_dir_v2, "sha_v2", ["file_a.txt", "file_b.txt", "file_c.txt"]

        def populate_base(sha, dest, include_paths, git_exe, git_env_):
            """Base snapshot contains only the files present at sha_v1."""
            (dest / "file_a.txt").write_text("content a\n")
            (dest / "file_b.txt").write_text("content b\n")

        with (
            patch.object(RhizaTemplate, "clone", side_effect=clone_v2),
            patch("rhiza.models.RhizaTemplate._clone_at_sha", side_effect=populate_base),
        ):
            sync(target=project, branch="main", target_branch=None, strategy="merge")

        assert (project / "file_a.txt").exists()
        assert (project / "file_b.txt").exists()
        assert (project / "file_c.txt").exists(), "file_c.txt must be added after it is included in template.yml"
        assert _read_lock(project) == "sha_v2"

    @patch("rhiza.commands._sync_helpers._warn_about_workflow_files")
    def test_removing_include_entry_removes_orphaned_file(self, mock_warn, project, git_setup, tmp_path):
        """Removing a path from include: in template.yml causes it to be deleted on the next sync.

        Timeline:
        - template.yml v1: ``include: [file_a.txt, file_b.txt]``
        - Sync 1: both files copied into project.
        - User edits template.yml: ``include: [file_a.txt]``  (``file_b.txt`` removed)
        - Sync 2: ``file_b.txt`` is no longer in the materialized set; orphan
          cleanup deletes it from the project.

        Expected after sync 2: ``file_b.txt`` is gone; ``file_a.txt`` remains.
        """
        git_executable, git_env = git_setup

        # ------------------------------------------------------------------
        # Configure template.yml v1: file_a.txt and file_b.txt
        # ------------------------------------------------------------------
        (project / ".rhiza" / "template.yml").write_text(
            "template-repository: jebel-quant/rhiza\ntemplate-branch: main\ninclude:\n  - file_a.txt\n  - file_b.txt\n"
        )
        _git_commit_all(project, git_executable, git_env, "template.yml v1: file_a + file_b")

        # ------------------------------------------------------------------
        # Sync 1 (first sync — no lock yet)
        # ------------------------------------------------------------------
        upstream_dir_v1 = tmp_path / "upstream_v1"
        upstream_dir_v1.mkdir()
        (upstream_dir_v1 / "file_a.txt").write_text("content a\n")
        (upstream_dir_v1 / "file_b.txt").write_text("content b\n")

        def clone_v1(git_exe, git_env_, branch="main"):
            return upstream_dir_v1, "sha_v1", ["file_a.txt", "file_b.txt"]

        with patch.object(RhizaTemplate, "clone", side_effect=clone_v1):
            sync(target=project, branch="main", target_branch=None, strategy="merge")

        assert (project / "file_a.txt").exists()
        assert (project / "file_b.txt").exists()
        assert _read_lock(project) == "sha_v1"

        _git_commit_all(project, git_executable, git_env, "after sync 1")

        # ------------------------------------------------------------------
        # User removes file_b.txt from the include: list in template.yml
        # ------------------------------------------------------------------
        (project / ".rhiza" / "template.yml").write_text(
            "template-repository: jebel-quant/rhiza\ntemplate-branch: main\ninclude:\n  - file_a.txt\n"
        )
        _git_commit_all(project, git_executable, git_env, "template.yml v2: remove file_b.txt")

        # ------------------------------------------------------------------
        # Sync 2 — template.yml no longer requests file_b.txt
        # ------------------------------------------------------------------
        upstream_dir_v2 = tmp_path / "upstream_v2"
        upstream_dir_v2.mkdir()
        (upstream_dir_v2 / "file_a.txt").write_text("content a\n")

        def clone_v2(git_exe, git_env_, branch="main"):
            # Only file_a.txt is in the updated include list from template.yml.
            return upstream_dir_v2, "sha_v2", ["file_a.txt"]

        def populate_base(sha, dest, include_paths, git_exe, git_env_):
            # Orphan cleanup uses the lock's ``files`` field, not the diff,
            # so only the currently-included file needs to be in the base.
            (dest / "file_a.txt").write_text("content a\n")

        with (
            patch.object(RhizaTemplate, "clone", side_effect=clone_v2),
            patch("rhiza.models.RhizaTemplate._clone_at_sha", side_effect=populate_base),
        ):
            sync(target=project, branch="main", target_branch=None, strategy="merge")

        assert (project / "file_a.txt").exists()
        assert not (project / "file_b.txt").exists(), (
            "file_b.txt must be removed after it is dropped from template.yml include:"
        )
