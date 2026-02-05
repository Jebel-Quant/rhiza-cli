"""Integration tests for materialize command with bundle support."""

import pytest

from rhiza.models import RhizaTemplate


@pytest.fixture
def template_repo(tmp_path):
    """Create a mock template repository with template_bundles.yml."""
    repo = tmp_path / "template-repo"
    repo.mkdir()

    # Initialize git repo
    import subprocess  # nosec B404

    subprocess.run(["git", "init"], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, capture_output=True, check=True)

    # Create template_bundles.yml
    rhiza_dir = repo / ".rhiza"
    rhiza_dir.mkdir()
    bundles_file = rhiza_dir / "template_bundles.yml"
    bundles_file.write_text("""
version: "1.0"
bundles:
  core:
    description: "Core files"
    files:
      - Makefile
      - .editorconfig
    workflows: []
    depends-on: []
  tests:
    description: "Test files"
    files:
      - tests
    workflows:
      - .github/workflows/ci.yml
    depends-on:
      - core
  docs:
    description: "Documentation"
    files:
      - docs
    workflows: []
    depends-on:
      - tests
""")

    # Create files referenced by bundles
    (repo / "Makefile").write_text("# Makefile")
    (repo / ".editorconfig").write_text("[*]\nindent_style = space")

    tests_dir = repo / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_example.py").write_text("def test_example(): pass")

    docs_dir = repo / "docs"
    docs_dir.mkdir()
    (docs_dir / "index.md").write_text("# Docs")

    github_workflows = repo / ".github" / "workflows"
    github_workflows.mkdir(parents=True)
    (github_workflows / "ci.yml").write_text("name: CI")

    # Create template.yml with bundles (legacy path-based for test purposes)
    template_file = rhiza_dir / "template.yml"
    template_file.write_text("""
template-repository: jebel-quant/rhiza
template-branch: main
include:
  - .rhiza
  - Makefile
  - .editorconfig
  - tests
  - docs
  - .github/workflows/ci.yml
""")

    # Commit everything
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo, capture_output=True, check=True)

    return repo


@pytest.fixture
def target_repo(tmp_path):
    """Create a mock target repository."""
    repo = tmp_path / "target-repo"
    repo.mkdir()

    # Initialize git repo
    import subprocess  # nosec B404

    subprocess.run(["git", "init"], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, capture_output=True, check=True)

    # Create pyproject.toml (required for validation)
    (repo / "pyproject.toml").write_text("[project]\nname = 'test'")

    # Create .rhiza directory with template.yml
    rhiza_dir = repo / ".rhiza"
    rhiza_dir.mkdir()

    return repo


class TestMaterializeWithBundles:
    """Test materialize command with bundle support."""

    def test_path_based_template(self, target_repo):
        """Test that path-based templates still work."""
        template_file = target_repo / ".rhiza" / "template.yml"
        template_file.write_text("""
template-repository: test/repo
template-branch: main
include:
  - .rhiza
  - Makefile
""")

        # This should load and parse correctly
        template = RhizaTemplate.from_yaml(template_file)
        assert template.include == [".rhiza", "Makefile"]
        assert template.templates == []

    def test_template_based_configuration(self, target_repo):
        """Test that template-based templates load correctly."""
        template_file = target_repo / ".rhiza" / "template.yml"
        template_file.write_text("""
template-repository: test/repo
templates:
  - core
  - tests
""")

        template = RhizaTemplate.from_yaml(template_file)
        assert template.templates == ["core", "tests"]
        assert template.include == []

    def test_to_yaml_with_templates(self, target_repo):
        """Test that templates with templates field write correctly to YAML."""
        template_file = target_repo / ".rhiza" / "template.yml"

        template = RhizaTemplate(
            template_repository="test/repo",
            templates=["core", "tests"],
        )
        template.to_yaml(template_file)

        # Read back and verify
        content = template_file.read_text()
        assert "templates:" in content
        assert "- core" in content
        assert "- tests" in content

    def test_to_yaml_with_include(self, target_repo):
        """Test that templates with include write correctly to YAML."""
        template_file = target_repo / ".rhiza" / "template.yml"

        template = RhizaTemplate(
            template_repository="test/repo",
            include=[".rhiza", "Makefile"],
        )
        template.to_yaml(template_file)

        # Read back and verify
        content = template_file.read_text()
        assert "include:" in content
        assert "- .rhiza" in content

    def test_hybrid_mode_template(self, target_repo):
        """Test that hybrid mode (templates + include) works correctly."""
        template_file = target_repo / ".rhiza" / "template.yml"
        template_file.write_text("""
template-repository: test/repo
templates:
  - core
include:
  - custom/
""")

        template = RhizaTemplate.from_yaml(template_file)
        assert template.templates == ["core"]
        assert template.include == ["custom/"]

    def test_to_yaml_hybrid_mode(self, target_repo):
        """Test that hybrid mode writes both templates and include to YAML."""
        template_file = target_repo / ".rhiza" / "template.yml"

        template = RhizaTemplate(
            template_repository="test/repo",
            templates=["core", "tests"],
            include=[".custom", "extra/"],
        )
        template.to_yaml(template_file)

        # Read back and verify
        content = template_file.read_text()
        assert "templates:" in content
        assert "include:" in content
        assert "- core" in content
        assert "- .custom" in content
