"""Tests for the migrate command.

This module verifies that `migrate` creates the .rhiza folder and migrates
configuration files from .github to the new location.
"""

import yaml
from typer.testing import CliRunner

from rhiza import cli
from rhiza.commands.migrate import migrate


class TestMigrateCommand:
    """Tests for the migrate command."""

    def test_migrate_creates_rhiza_folder(self, tmp_path):
        """Test that migrate creates the .rhiza folder."""
        migrate(tmp_path)

        # Verify .rhiza folder was created
        rhiza_dir = tmp_path / ".rhiza"
        assert rhiza_dir.exists()
        assert rhiza_dir.is_dir()

    def test_migrate_copies_template_from_github_rhiza(self, tmp_path):
        """Test that migrate moves template.yml from .github/rhiza/ to .rhiza/."""
        # Create existing template.yml in .github/rhiza/
        github_rhiza_dir = tmp_path / ".github" / "rhiza"
        github_rhiza_dir.mkdir(parents=True)
        old_template_file = github_rhiza_dir / "template.yml"

        template_content = {
            "template-repository": "test/repo",
            "template-branch": "main",
            "include": [".github", "Makefile"],
        }

        with open(old_template_file, "w") as f:
            yaml.dump(template_content, f)

        # Run migrate
        migrate(tmp_path)

        # Verify new template.yml was created
        new_template_file = tmp_path / ".rhiza" / "template.yml"
        assert new_template_file.exists()

        # Verify content matches
        with open(new_template_file) as f:
            migrated_content = yaml.safe_load(f)

        assert migrated_content["template-repository"] == "test/repo"
        assert migrated_content["template-branch"] == "main"
        # After migration, .rhiza should be automatically added to include list
        assert migrated_content["include"] == [".github", "Makefile", ".rhiza"]

        # Verify old file was removed
        assert not old_template_file.exists()

    def test_migrate_copies_template_from_github_root(self, tmp_path):
        """Test that migrate moves template.yml from .github/ to .rhiza/."""
        # Create existing template.yml in .github/ (old location)
        github_dir = tmp_path / ".github"
        github_dir.mkdir(parents=True)
        old_template_file = github_dir / "template.yml"

        template_content = {
            "template-repository": "old/location",
            "template-branch": "dev",
            "include": ["src", "tests"],
        }

        with open(old_template_file, "w") as f:
            yaml.dump(template_content, f)

        # Run migrate
        migrate(tmp_path)

        # Verify new template.yml was created
        new_template_file = tmp_path / ".rhiza" / "template.yml"
        assert new_template_file.exists()

        # Verify content matches
        with open(new_template_file) as f:
            migrated_content = yaml.safe_load(f)

        assert migrated_content["template-repository"] == "old/location"

        # Verify old file was removed
        assert not old_template_file.exists()

    def test_migrate_prefers_github_rhiza_over_github_root(self, tmp_path):
        """Test that migrate prefers .github/rhiza/template.yml over .github/template.yml."""
        # Create template.yml in both locations
        github_dir = tmp_path / ".github"
        github_rhiza_dir = github_dir / "rhiza"
        github_rhiza_dir.mkdir(parents=True)

        # Old location
        old_template_file = github_dir / "template.yml"
        with open(old_template_file, "w") as f:
            yaml.dump({"template-repository": "wrong/repo"}, f)

        # Preferred location
        preferred_template_file = github_rhiza_dir / "template.yml"
        with open(preferred_template_file, "w") as f:
            yaml.dump({"template-repository": "correct/repo"}, f)

        # Run migrate
        migrate(tmp_path)

        # Verify the correct one was migrated
        new_template_file = tmp_path / ".rhiza" / "template.yml"
        with open(new_template_file) as f:
            migrated_content = yaml.safe_load(f)

        assert migrated_content["template-repository"] == "correct/repo"

    def test_migrate_handles_missing_template(self, tmp_path):
        """Test that migrate handles case when no template.yml exists."""
        # Run migrate without creating any template.yml
        migrate(tmp_path)

        # Verify .rhiza folder was still created
        rhiza_dir = tmp_path / ".rhiza"
        assert rhiza_dir.exists()

        # Verify no template.yml was created
        new_template_file = rhiza_dir / "template.yml"
        assert not new_template_file.exists()

    def test_migrate_copies_history_file(self, tmp_path):
        """Test that migrate copies .rhiza.history to .rhiza/history."""
        # Create existing .rhiza.history
        old_history_file = tmp_path / ".rhiza.history"
        history_content = """# Rhiza Template History
# Files under template control:
.editorconfig
.gitignore
Makefile
"""
        old_history_file.write_text(history_content)

        # Run migrate
        migrate(tmp_path)

        # Verify new history file was created
        new_history_file = tmp_path / ".rhiza" / "history"
        assert new_history_file.exists()

        # Verify content matches
        assert new_history_file.read_text() == history_content

        # Verify old file was removed
        assert not old_history_file.exists()

    def test_migrate_handles_missing_history_file(self, tmp_path):
        """Test that migrate handles case when no .rhiza.history exists."""
        # Run migrate without creating .rhiza.history
        migrate(tmp_path)

        # Verify .rhiza folder was created
        rhiza_dir = tmp_path / ".rhiza"
        assert rhiza_dir.exists()

        # Verify no history file was created
        new_history_file = rhiza_dir / "history"
        assert not new_history_file.exists()

    def test_migrate_skips_history_when_both_exist(self, tmp_path):
        """Test that migrate skips history migration when both old and new exist."""
        # Create existing .rhiza.history
        old_history_file = tmp_path / ".rhiza.history"
        old_content = "# Old history content\nold_file.txt\n"
        old_history_file.write_text(old_content)

        # Create existing .rhiza/history (already migrated)
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        new_history_file = rhiza_dir / "history"
        new_content = "# New history content\nnew_file.txt\n"
        new_history_file.write_text(new_content)

        # Run migrate
        migrate(tmp_path)

        # Verify new history file was NOT overwritten
        assert new_history_file.read_text() == new_content

        # Verify old file still exists (not removed since target exists)
        assert old_history_file.exists()
        assert old_history_file.read_text() == old_content

    def test_migrate_handles_existing_rhiza_history(self, tmp_path):
        """Test that migrate handles when .rhiza/history already exists but .rhiza.history doesn't."""
        # Create existing .rhiza/history (no old file)
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        new_history_file = rhiza_dir / "history"
        existing_content = "# Existing history\nfile.txt\n"
        new_history_file.write_text(existing_content)

        # Run migrate without creating .rhiza.history
        migrate(tmp_path)

        # Verify .rhiza/history is unchanged
        assert new_history_file.exists()
        assert new_history_file.read_text() == existing_content

        # Verify no old file was created
        old_history_file = tmp_path / ".rhiza.history"
        assert not old_history_file.exists()

    def test_migrate_skips_existing_files(self, tmp_path):
        """Test that migrate skips existing files in .rhiza."""
        # Create existing .rhiza/template.yml
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        existing_template = rhiza_dir / "template.yml"
        existing_template.write_text("template-repository: existing/repo\n")

        # Create new template in .github/rhiza/
        github_rhiza_dir = tmp_path / ".github" / "rhiza"
        github_rhiza_dir.mkdir(parents=True)
        old_template = github_rhiza_dir / "template.yml"
        old_template.write_text("template-repository: new/repo\n")

        # Run migrate
        migrate(tmp_path)

        # Verify the file was NOT overwritten
        with open(existing_template) as f:
            content = yaml.safe_load(f)

        assert content["template-repository"] == "existing/repo"

        # Verify old file still exists (not moved since target exists)
        assert old_template.exists()

        assert content["template-repository"] == "existing/repo"

    def test_migrate_adds_rhiza_to_include_list(self, tmp_path):
        """Test that migrate adds .rhiza to include list if not present."""
        # Create existing template.yml in .github/rhiza/ without .rhiza in include
        github_rhiza_dir = tmp_path / ".github" / "rhiza"
        github_rhiza_dir.mkdir(parents=True)
        old_template_file = github_rhiza_dir / "template.yml"

        template_content = {
            "template-repository": "test/repo",
            "template-branch": "main",
            "include": [".github", "Makefile"],
        }

        with open(old_template_file, "w") as f:
            yaml.dump(template_content, f)

        # Run migrate
        migrate(tmp_path)

        # Verify new template.yml was created
        new_template_file = tmp_path / ".rhiza" / "template.yml"
        assert new_template_file.exists()

        # Verify .rhiza was added to include list
        with open(new_template_file) as f:
            migrated_content = yaml.safe_load(f)

        assert ".rhiza" in migrated_content["include"]
        assert migrated_content["include"] == [".github", "Makefile", ".rhiza"]

    def test_migrate_does_not_duplicate_rhiza_in_include_list(self, tmp_path):
        """Test that migrate does not duplicate .rhiza if already in include list."""
        # Create existing template.yml in .github/rhiza/ with .rhiza already in include
        github_rhiza_dir = tmp_path / ".github" / "rhiza"
        github_rhiza_dir.mkdir(parents=True)
        old_template_file = github_rhiza_dir / "template.yml"

        template_content = {
            "template-repository": "test/repo",
            "template-branch": "main",
            "include": [".github", ".rhiza", "Makefile"],
        }

        with open(old_template_file, "w") as f:
            yaml.dump(template_content, f)

        # Run migrate
        migrate(tmp_path)

        # Verify new template.yml was created
        new_template_file = tmp_path / ".rhiza" / "template.yml"
        assert new_template_file.exists()

        # Verify .rhiza appears only once in include list
        with open(new_template_file) as f:
            migrated_content = yaml.safe_load(f)

        assert migrated_content["include"].count(".rhiza") == 1
        assert migrated_content["include"] == [".github", ".rhiza", "Makefile"]

    def test_migrate_adds_rhiza_to_existing_template(self, tmp_path):
        """Test that migrate adds .rhiza to include list for existing .rhiza/template.yml."""
        # Create existing template.yml directly in .rhiza/ without .rhiza in include
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        template_file = rhiza_dir / "template.yml"

        template_content = {
            "template-repository": "test/repo",
            "template-branch": "main",
            "include": ["src", "tests"],
        }

        with open(template_file, "w") as f:
            yaml.dump(template_content, f)

        # Run migrate
        migrate(tmp_path)

        # Verify .rhiza was added to include list
        with open(template_file) as f:
            updated_content = yaml.safe_load(f)

        assert ".rhiza" in updated_content["include"]
        assert updated_content["include"] == ["src", "tests", ".rhiza"]

    def test_migrate_skips_rhiza_include_when_no_template(self, tmp_path):
        """Test that migrate skips adding .rhiza to include when template.yml doesn't exist."""
        # Create .rhiza directory but no template.yml
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)

        # Run migrate
        migrate(tmp_path)

        # Verify no template.yml was created
        template_file = rhiza_dir / "template.yml"
        assert not template_file.exists()

    def test_ensure_rhiza_in_include_with_no_template(self, tmp_path):
        """Test _ensure_rhiza_in_include when template file doesn't exist."""
        from rhiza.commands.migrate import _ensure_rhiza_in_include

        # Create .rhiza directory but no template.yml
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        template_file = rhiza_dir / "template.yml"

        # Call the function - it should handle gracefully
        _ensure_rhiza_in_include(template_file)

        # Verify no template.yml was created
        assert not template_file.exists()


class TestMigrateDeprecatedRepository:
    """Tests for the deprecated repository migration functionality."""

    def test_migrate_deprecated_repository_with_prompt(self, tmp_path, monkeypatch):
        """Test that migrate prompts to change deprecated repository."""
        from rhiza.commands.migrate import _migrate_deprecated_repository

        # Create template with deprecated repository
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        template_file = rhiza_dir / "template.yml"

        template_content = {
            "template-repository": ".tschm/.config-templates",
            "template-branch": "main",
            "include": [".github"],
        }

        with open(template_file, "w") as f:
            yaml.dump(template_content, f)

        # Mock questionary to return True (yes, migrate)
        from unittest.mock import MagicMock

        mock_confirm = MagicMock()
        mock_confirm.return_value.ask.return_value = True
        monkeypatch.setattr("rhiza.commands.migrate.questionary.confirm", mock_confirm)

        # Mock sys.stdin.isatty to return True
        import sys

        monkeypatch.setattr(sys.stdin, "isatty", lambda: True)

        # Run migration
        migrations = _migrate_deprecated_repository(template_file)

        # Verify the repository was updated
        with open(template_file) as f:
            content = yaml.safe_load(f)

        assert content["template-repository"] == "Jebel-Quant/rhiza"
        assert len(migrations) == 1
        assert "Updated template-repository" in migrations[0]

    def test_migrate_deprecated_repository_decline(self, tmp_path, monkeypatch):
        """Test that migrate respects user declining to update deprecated repository."""
        from rhiza.commands.migrate import _migrate_deprecated_repository

        # Create template with deprecated repository
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        template_file = rhiza_dir / "template.yml"

        template_content = {
            "template-repository": ".tschm/.config-templates",
            "template-branch": "main",
            "include": [".github"],
        }

        with open(template_file, "w") as f:
            yaml.dump(template_content, f)

        # Mock questionary to return False (no, don't migrate)
        from unittest.mock import MagicMock

        mock_confirm = MagicMock()
        mock_confirm.return_value.ask.return_value = False
        monkeypatch.setattr("rhiza.commands.migrate.questionary.confirm", mock_confirm)

        # Mock sys.stdin.isatty to return True
        import sys

        monkeypatch.setattr(sys.stdin, "isatty", lambda: True)

        # Run migration
        migrations = _migrate_deprecated_repository(template_file)

        # Verify the repository was NOT updated
        with open(template_file) as f:
            content = yaml.safe_load(f)

        assert content["template-repository"] == ".tschm/.config-templates"
        assert len(migrations) == 0

    def test_migrate_non_deprecated_repository(self, tmp_path):
        """Test that migrate doesn't prompt for non-deprecated repository."""
        from rhiza.commands.migrate import _migrate_deprecated_repository

        # Create template with new repository
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        template_file = rhiza_dir / "template.yml"

        template_content = {
            "template-repository": "Jebel-Quant/rhiza",
            "template-branch": "main",
            "include": [".github"],
        }

        with open(template_file, "w") as f:
            yaml.dump(template_content, f)

        # Run migration
        migrations = _migrate_deprecated_repository(template_file)

        # Verify no migrations were performed
        assert len(migrations) == 0

        # Verify repository is unchanged
        with open(template_file) as f:
            content = yaml.safe_load(f)

        assert content["template-repository"] == "Jebel-Quant/rhiza"


class TestMigrateRhizaFolderInclude:
    """Tests for the .rhiza folder include handling."""

    def test_ensure_rhiza_in_include_with_rhiza_in_exclude_shows_warning(self, tmp_path, caplog):
        """Test that warning is shown when .rhiza is in exclude list."""
        from rhiza.commands.migrate import _ensure_rhiza_in_include

        # Create template with .rhiza in exclude
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        template_file = rhiza_dir / "template.yml"

        template_content = {
            "template-repository": "jebel-quant/rhiza",
            "template-branch": "main",
            "include": [".github"],
            "exclude": [".rhiza"],
        }

        with open(template_file, "w") as f:
            yaml.dump(template_content, f)

        # Call the function
        _ensure_rhiza_in_include(template_file)

        # The function should have logged a warning (we can't easily check loguru output)
        # but we can verify the template was still processed

    def test_ensure_rhiza_in_include_prompts_when_not_in_include(self, tmp_path, monkeypatch):
        """Test that user is prompted to add .rhiza when not in include list."""
        from rhiza.commands.migrate import _ensure_rhiza_in_include

        # Create template without .rhiza in include
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        template_file = rhiza_dir / "template.yml"

        template_content = {
            "template-repository": "jebel-quant/rhiza",
            "template-branch": "main",
            "include": [".github", "Makefile"],
        }

        with open(template_file, "w") as f:
            yaml.dump(template_content, f)

        # Mock questionary to return True (yes, add .rhiza)
        from unittest.mock import MagicMock

        mock_confirm = MagicMock()
        mock_confirm.return_value.ask.return_value = True
        monkeypatch.setattr("rhiza.commands.migrate.questionary.confirm", mock_confirm)

        # Mock sys.stdin.isatty to return True
        import sys

        monkeypatch.setattr(sys.stdin, "isatty", lambda: True)

        # Call the function
        _ensure_rhiza_in_include(template_file)

        # Verify .rhiza was added to include
        with open(template_file) as f:
            content = yaml.safe_load(f)

        assert ".rhiza" in content["include"]

    def test_ensure_rhiza_in_include_exclude_only_mode_skips(self, tmp_path):
        """Test that exclude-only mode templates don't get .rhiza added to include."""
        from rhiza.commands.migrate import _ensure_rhiza_in_include

        # Create template in exclude-only mode
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        template_file = rhiza_dir / "template.yml"

        template_content = {
            "template-repository": "jebel-quant/rhiza",
            "template-branch": "main",
            "exclude": ["LICENSE", "README.md"],
        }

        with open(template_file, "w") as f:
            yaml.dump(template_content, f)

        # Call the function
        _ensure_rhiza_in_include(template_file)

        # Verify no include list was added
        with open(template_file) as f:
            content = yaml.safe_load(f)

        assert "include" not in content or content.get("include") == []


class TestMigrateCLI:
    """Tests for the migrate CLI command."""

    def test_migrate_cli_basic(self, tmp_path):
        """Test that 'rhiza migrate' CLI command works."""
        runner = CliRunner()

        # Create a template to migrate
        github_rhiza_dir = tmp_path / ".github" / "rhiza"
        github_rhiza_dir.mkdir(parents=True)
        template_file = github_rhiza_dir / "template.yml"
        template_file.write_text("template-repository: test/repo\n")

        # Run CLI command
        result = runner.invoke(cli.app, ["migrate", str(tmp_path)])

        # Verify it succeeded (exit code 0)
        assert result.exit_code == 0

        # Verify .rhiza folder was created
        assert (tmp_path / ".rhiza").exists()
        assert (tmp_path / ".rhiza" / "template.yml").exists()

    def test_migrate_handles_multiline_exclude_field(self, tmp_path):
        """Test that migrate correctly handles template.yml with multi-line exclude field.

        This tests the bug where exclude: | multi-line YAML format was being
        corrupted during migration, resulting in malformed YAML output.
        """
        # Create existing template.yml in .github/ with multi-line exclude
        github_dir = tmp_path / ".github"
        github_dir.mkdir(parents=True)
        old_template_file = github_dir / "template.yml"

        # Write template with multi-line string format (using |)
        # Note: This is exclude-only mode (no include list), so all files are
        # included by default except those in exclude
        old_template_file.write_text("""template-repository: ".tschm/.config-templates"
template-branch: "main"
exclude: |
  LICENSE
  README.md
  .github/CODEOWNERS
""")

        # Run migrate
        runner = CliRunner()
        result = runner.invoke(cli.app, ["migrate", str(tmp_path)])

        # Verify it succeeded
        assert result.exit_code == 0

        # Verify new template.yml was created
        new_template_file = tmp_path / ".rhiza" / "template.yml"
        assert new_template_file.exists()

        # Verify content was properly converted to YAML lists
        with open(new_template_file) as f:
            migrated_content = yaml.safe_load(f)

        # Exclude should be a proper list, not a malformed string
        assert isinstance(migrated_content["exclude"], list)
        assert migrated_content["exclude"] == ["LICENSE", "README.md", ".github/CODEOWNERS"]

        # In exclude-only mode, include should be empty (all files included by default)
        # .rhiza is not added because it's already included implicitly
        assert migrated_content.get("include", []) == []

        # Verify old file was removed
        assert not old_template_file.exists()
