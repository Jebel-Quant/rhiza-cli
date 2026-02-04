"""Tests for bundle resolver functionality."""

import pytest

from rhiza.bundle_resolver import load_bundles_from_clone, resolve_include_paths
from rhiza.models import BundleDefinition, RhizaBundles, RhizaTemplate


class TestBundleDefinition:
    """Test BundleDefinition dataclass."""

    def test_all_paths(self) -> None:
        """Test all_paths combines files and workflows."""
        bundle = BundleDefinition(
            name="test",
            description="Test bundle",
            files=["file1.txt", "dir1/"],
            workflows=["workflow1.yml", "workflow2.yml"],
        )
        assert bundle.all_paths() == ["file1.txt", "dir1/", "workflow1.yml", "workflow2.yml"]

    def test_all_paths_empty(self) -> None:
        """Test all_paths with no files or workflows."""
        bundle = BundleDefinition(
            name="test",
            description="Test bundle",
        )
        assert bundle.all_paths() == []


class TestRhizaBundles:
    """Test RhizaBundles dataclass."""

    def test_resolve_dependencies_simple(self) -> None:
        """Test resolving dependencies with no circular references."""
        bundles = RhizaBundles(
            version="1.0",
            bundles={
                "core": BundleDefinition(
                    name="core",
                    description="Core",
                    files=["core.txt"],
                ),
                "tests": BundleDefinition(
                    name="tests",
                    description="Tests",
                    files=["tests/"],
                    depends_on=["core"],
                ),
                "docs": BundleDefinition(
                    name="docs",
                    description="Docs",
                    files=["docs/"],
                    depends_on=["tests"],
                ),
            },
        )

        # Should resolve in order: core, tests, docs
        result = bundles.resolve_dependencies(["docs"])
        assert result == ["core", "tests", "docs"]

    def test_resolve_dependencies_multiple_roots(self) -> None:
        """Test resolving multiple independent bundles."""
        bundles = RhizaBundles(
            version="1.0",
            bundles={
                "core": BundleDefinition(name="core", description="Core"),
                "docker": BundleDefinition(name="docker", description="Docker"),
                "github": BundleDefinition(name="github", description="GitHub", depends_on=["core"]),
            },
        )

        result = bundles.resolve_dependencies(["docker", "github"])
        assert set(result) == {"core", "docker", "github"}
        assert result.index("core") < result.index("github")

    def test_resolve_dependencies_circular(self) -> None:
        """Test that circular dependencies raise an error."""
        bundles = RhizaBundles(
            version="1.0",
            bundles={
                "a": BundleDefinition(name="a", description="A", depends_on=["b"]),
                "b": BundleDefinition(name="b", description="B", depends_on=["a"]),
            },
        )

        with pytest.raises(ValueError, match="Circular dependency"):
            bundles.resolve_dependencies(["a"])

    def test_resolve_dependencies_unknown_bundle(self) -> None:
        """Test that unknown bundles raise an error."""
        bundles = RhizaBundles(
            version="1.0",
            bundles={
                "core": BundleDefinition(name="core", description="Core"),
            },
        )

        with pytest.raises(ValueError, match="Bundle 'unknown' not found"):
            bundles.resolve_dependencies(["unknown"])

    def test_resolve_dependencies_unknown_dependency(self) -> None:
        """Test that unknown dependencies raise an error."""
        bundles = RhizaBundles(
            version="1.0",
            bundles={
                "core": BundleDefinition(name="core", description="Core", depends_on=["missing"]),
            },
        )

        with pytest.raises(ValueError, match="depends on unknown bundle 'missing'"):
            bundles.resolve_dependencies(["core"])

    def test_resolve_to_paths_deduplication(self) -> None:
        """Test that paths are deduplicated."""
        bundles = RhizaBundles(
            version="1.0",
            bundles={
                "core": BundleDefinition(
                    name="core",
                    description="Core",
                    files=["Makefile", ".rhiza/"],
                    workflows=[".github/workflows/ci.yml"],
                ),
                "tests": BundleDefinition(
                    name="tests",
                    description="Tests",
                    files=["tests/", ".github/workflows/test.yml"],  # Overlaps with core
                    depends_on=["core"],
                ),
            },
        )

        result = bundles.resolve_to_paths(["tests"])
        # Should have all paths without duplicates
        assert len(result) == len(set(result))  # No duplicates
        assert ".github/workflows/ci.yml" in result
        assert ".github/workflows/test.yml" in result
        assert "tests/" in result

    def test_resolve_to_paths_order(self) -> None:
        """Test that paths maintain dependency order."""
        bundles = RhizaBundles(
            version="1.0",
            bundles={
                "core": BundleDefinition(
                    name="core",
                    description="Core",
                    files=["core1.txt"],
                ),
                "tests": BundleDefinition(
                    name="tests",
                    description="Tests",
                    files=["tests1.txt"],
                    depends_on=["core"],
                ),
                "docs": BundleDefinition(
                    name="docs",
                    description="Docs",
                    files=["docs1.txt"],
                    depends_on=["tests"],
                ),
            },
        )

        result = bundles.resolve_to_paths(["docs"])
        # Check order: core comes before tests, tests before docs
        assert result.index("core1.txt") < result.index("tests1.txt")
        assert result.index("tests1.txt") < result.index("docs1.txt")

    def test_from_yaml_valid(self, tmp_path):
        """Test loading valid bundles.yml."""
        bundles_file = tmp_path / "bundles.yml"
        bundles_file.write_text("""
version: "1.0"
bundles:
  core:
    description: "Core files"
    files:
      - Makefile
      - .rhiza
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
""")

        result = RhizaBundles.from_yaml(bundles_file)
        assert result.version == "1.0"
        assert "core" in result.bundles
        assert "tests" in result.bundles
        assert result.bundles["core"].files == ["Makefile", ".rhiza"]
        assert result.bundles["tests"].depends_on == ["core"]

    def test_from_yaml_empty(self, tmp_path):
        """Test loading empty bundles.yml."""
        bundles_file = tmp_path / "bundles.yml"
        bundles_file.write_text("")

        with pytest.raises(ValueError, match="Bundles file is empty"):
            RhizaBundles.from_yaml(bundles_file)

    def test_from_yaml_missing_version(self, tmp_path):
        """Test loading bundles.yml without version."""
        bundles_file = tmp_path / "bundles.yml"
        bundles_file.write_text("bundles: {}")

        with pytest.raises(ValueError, match="missing required field: version"):
            RhizaBundles.from_yaml(bundles_file)

    def test_from_yaml_invalid_bundles_type(self, tmp_path):
        """Test loading bundles.yml with invalid bundles type."""
        bundles_file = tmp_path / "bundles.yml"
        bundles_file.write_text("version: '1.0'\nbundles: 'invalid'")

        with pytest.raises(ValueError, match="Bundles must be a dictionary"):
            RhizaBundles.from_yaml(bundles_file)


class TestResolveIncludePaths:
    """Test resolve_include_paths function."""

    def test_bundle_mode(self) -> None:
        """Test resolving paths in bundle mode."""
        template = RhizaTemplate(
            template_repository="test/repo",
            bundles=["core", "tests"],
        )
        bundles = RhizaBundles(
            version="1.0",
            bundles={
                "core": BundleDefinition(
                    name="core",
                    description="Core",
                    files=["Makefile"],
                ),
                "tests": BundleDefinition(
                    name="tests",
                    description="Tests",
                    files=["tests/"],
                    depends_on=["core"],
                ),
            },
        )

        result = resolve_include_paths(template, bundles)
        assert "Makefile" in result
        assert "tests/" in result

    def test_legacy_mode(self) -> None:
        """Test resolving paths in legacy include mode."""
        template = RhizaTemplate(
            template_repository="test/repo",
            include=[".rhiza", ".github", "tests/"],
        )

        result = resolve_include_paths(template, None)
        assert result == [".rhiza", ".github", "tests/"]

    def test_bundle_mode_no_bundles_config(self) -> None:
        """Test that bundle mode without bundles config raises error."""
        template = RhizaTemplate(
            template_repository="test/repo",
            bundles=["core"],
        )

        with pytest.raises(ValueError, match=r"Template uses bundles but bundles\.yml not found"):
            resolve_include_paths(template, None)

    def test_no_configuration(self) -> None:
        """Test that templates with no bundles or include raise error."""
        template = RhizaTemplate(
            template_repository="test/repo",
        )

        with pytest.raises(ValueError, match="must specify either 'bundles' or 'include'"):
            resolve_include_paths(template, None)


class TestLoadBundlesFromClone:
    """Test load_bundles_from_clone function."""

    def test_load_existing_bundles(self, tmp_path):
        """Test loading bundles.yml from cloned repo."""
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir()
        bundles_file = rhiza_dir / "bundles.yml"
        bundles_file.write_text("""
version: "1.0"
bundles:
  core:
    description: "Core"
    files: [Makefile]
    workflows: []
    depends-on: []
""")

        result = load_bundles_from_clone(tmp_path)
        assert result is not None
        assert result.version == "1.0"
        assert "core" in result.bundles

    def test_load_missing_bundles(self, tmp_path):
        """Test that missing bundles.yml returns None."""
        result = load_bundles_from_clone(tmp_path)
        assert result is None
