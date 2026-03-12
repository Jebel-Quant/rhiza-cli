"""Tests for the TemplateLock dataclass.

This module verifies that TemplateLock correctly serialises and deserialises
.rhiza/template.lock files, handles legacy plain-SHA format, and satisfies
the YamlSerializable protocol.
"""

import pytest
import yaml

from rhiza.models._base import YamlSerializable, load_model
from rhiza.models.lock import TemplateLock, _paths_to_tree, _tree_to_paths


class TestPathsToTree:
    """Unit tests for the _paths_to_tree helper."""

    def test_empty_list(self):
        """Empty input returns an empty dict."""
        assert _paths_to_tree([]) == {}

    def test_single_root_file(self):
        """Single root-level file maps to None leaf."""
        assert _paths_to_tree(["Makefile"]) == {"Makefile": None}

    def test_nested_file(self):
        """Deeply nested path produces nested dicts with None leaf."""
        assert _paths_to_tree([".github/workflows/ci.yml"]) == {".github": {"workflows": {"ci.yml": None}}}

    def test_multiple_files_same_dir(self):
        """Multiple files under the same directory share the parent node."""
        assert _paths_to_tree(["src/a.py", "src/b.py"]) == {"src": {"a.py": None, "b.py": None}}

    def test_mixed_depth(self):
        """Files at different depths are all represented in the tree."""
        result = _paths_to_tree(["Makefile", ".github/workflows/ci.yml"])
        assert result == {".github": {"workflows": {"ci.yml": None}}, "Makefile": None}


class TestTreeToPaths:
    """Unit tests for the _tree_to_paths helper."""

    def test_empty_dict(self):
        """Empty input returns an empty list."""
        assert _tree_to_paths({}) == []

    def test_single_root_file(self):
        """Single None-leaf entry reconstructs the file name."""
        assert _tree_to_paths({"Makefile": None}) == ["Makefile"]

    def test_nested_file(self):
        """Nested dicts are flattened back to a POSIX path."""
        assert _tree_to_paths({".github": {"workflows": {"ci.yml": None}}}) == [".github/workflows/ci.yml"]

    def test_multiple_files(self):
        """Multiple entries are reconstructed and sorted."""
        tree = {"src": {"b.py": None, "a.py": None}}
        assert _tree_to_paths(tree) == ["src/a.py", "src/b.py"]

    def test_empty_dict_leaf_treated_as_file(self):
        """Empty-dict leaves (legacy format) are treated as files."""
        assert _tree_to_paths({"Makefile": {}}) == ["Makefile"]

    def test_round_trip(self):
        """_tree_to_paths(_paths_to_tree(paths)) == sorted(paths)."""
        paths = [".github/workflows/ci.yml", ".rhiza/template.yml", "Makefile"]
        assert _tree_to_paths(_paths_to_tree(paths)) == sorted(paths)


class TestTemplateLock:
    """Tests for the TemplateLock dataclass."""

    def test_template_lock_to_yaml(self, tmp_path):
        """Test TemplateLock serialization: defaults, omissions, parent dir, and formatting."""
        # 1. Defaults and parent directory creation
        lock = TemplateLock(sha="abc123")
        lock_path = tmp_path / ".rhiza" / "template.lock"
        lock.to_yaml(lock_path)
        assert lock_path.exists()

        data = yaml.safe_load(lock_path.read_text(encoding="utf-8"))
        assert data["sha"] == "abc123"
        assert data["repo"] == ""
        assert data["host"] == "github"
        assert data["ref"] == "main"
        assert data["include"] == []
        assert data["exclude"] == []
        assert data["templates"] == []
        assert data["files"] == []  # empty list stays as []
        assert "synced_at" not in data
        assert "strategy" not in data

        # 2. File is valid YAML (parseable)
        raw = lock_path.read_text(encoding="utf-8")
        assert yaml.safe_load(raw) is not None

        # 3. Non-defaults: files serialised as nested tree dict
        lock = TemplateLock(
            sha="abc123def456",
            repo="jebel-quant/rhiza",
            host="gitlab",
            ref="develop",
            include=[".github/", ".rhiza/"],
            exclude=["README.md"],
            templates=["core"],
            files=[".github/workflows/ci.yml"],
            synced_at="2026-02-26T12:00:00Z",
            strategy="merge",
        )
        lock.to_yaml(lock_path)
        data = yaml.safe_load(lock_path.read_text(encoding="utf-8"))
        assert data["sha"] == "abc123def456"
        assert data["repo"] == "jebel-quant/rhiza"
        assert data["host"] == "gitlab"
        assert data["ref"] == "develop"
        assert data["include"] == [".github/", ".rhiza/"]
        assert data["exclude"] == ["README.md"]
        assert data["templates"] == ["core"]
        # files is now a nested dict tree, not a flat list
        assert data["files"] == {".github": {"workflows": {"ci.yml": None}}}
        assert data["synced_at"] == "2026-02-26T12:00:00Z"
        assert data["strategy"] == "merge"

    def test_template_lock_files_tree_yaml_output(self, tmp_path):
        """Files with multiple paths produce a readable nested tree in the YAML."""
        lock = TemplateLock(
            sha="abc123",
            files=[
                "data/prices/aapl.parquet",
                "data/prices/msft.parquet",
                "data/futures/es.parquet",
                "data/futures/nq.parquet",
                "config/model.yaml",
            ],
        )
        lock_path = tmp_path / "template.lock"
        lock.to_yaml(lock_path)

        raw = lock_path.read_text(encoding="utf-8")
        # The YAML must be parseable
        data = yaml.safe_load(raw)
        assert isinstance(data["files"], dict)

        # The nested structure matches the expected tree
        assert data["files"] == {
            "config": {"model.yaml": None},
            "data": {
                "futures": {"es.parquet": None, "nq.parquet": None},
                "prices": {"aapl.parquet": None, "msft.parquet": None},
            },
        }

        # Leaf entries are rendered as empty scalars, not 'null' or '~'
        assert "aapl.parquet:\n" in raw
        assert "null" not in raw
        assert "~ " not in raw

    def test_template_lock_from_yaml(self, tmp_path):
        """Test TemplateLock deserialization: structured format and missing fields."""
        lock_path = tmp_path / "template.lock"

        # 1. Legacy flat-list format is still accepted
        lock_path.write_text(
            "sha: abc123def456\nrepo: jebel-quant/rhiza\nhost: github\nref: main\n"
            "include:\n- .github/\n- .rhiza/\nexclude: []\ntemplates: []\n"
            "files:\n- .github/workflows/ci.yml\n",
            encoding="utf-8",
        )
        lock = TemplateLock.from_yaml(lock_path)
        assert lock.sha == "abc123def456"
        assert lock.repo == "jebel-quant/rhiza"
        assert lock.include == [".github/", ".rhiza/"]
        assert lock.files == [".github/workflows/ci.yml"]

        # 2. New tree-dict format is accepted
        lock_path.write_text(
            "sha: abc123def456\nfiles:\n  .github:\n    workflows:\n      ci.yml:\n",
            encoding="utf-8",
        )
        lock = TemplateLock.from_yaml(lock_path)
        assert lock.files == [".github/workflows/ci.yml"]

        # 3. Missing optional fields in structured format
        lock_path.write_text("sha: abc789\nhost: gitlab\n", encoding="utf-8")
        lock = TemplateLock.from_yaml(lock_path)
        assert lock.sha == "abc789"
        assert lock.host == "gitlab"
        assert lock.ref == "main"  # default fallback
        assert lock.files == []
        assert lock.synced_at == ""

    def test_template_lock_round_trip(self, tmp_path):
        """Test that to_yaml then from_yaml preserves all fields."""
        original = TemplateLock(
            sha="abc123def456",
            repo="jebel-quant/rhiza",
            host="gitlab",
            ref="develop",
            include=[".github/", ".rhiza/"],
            exclude=["README.md"],
            templates=["core"],
            files=[".github/workflows/ci.yml"],
            synced_at="2026-02-26T12:00:00Z",
            strategy="merge",
        )
        lock_path = tmp_path / "template.lock"
        original.to_yaml(lock_path)
        loaded = TemplateLock.from_yaml(lock_path)
        assert loaded == original

    def test_template_lock_from_yaml_invalid_format(self, tmp_path):
        """from_yaml raises TypeError when the lock data is not a dict."""
        lock_path = tmp_path / "template.lock"
        lock_path.write_text("- item1\n- item2\n", encoding="utf-8")

        with pytest.raises(TypeError, match="does not contain a YAML mapping"):
            TemplateLock.from_yaml(lock_path)


# ---------------------------------------------------------------------------
# YamlSerializable Protocol — lock-related check
# ---------------------------------------------------------------------------


class TestYamlSerializableProtocol:
    """Tests for the YamlSerializable Protocol as it applies to TemplateLock."""

    def test_template_lock_satisfies_protocol(self):
        """TemplateLock is a runtime-checkable instance of YamlSerializable."""
        lock = TemplateLock(sha="abc123")
        assert isinstance(lock, YamlSerializable)


# ---------------------------------------------------------------------------
# load_model helper — lock-related check
# ---------------------------------------------------------------------------


class TestLoadModel:
    """Tests for the load_model generic helper as it applies to TemplateLock."""

    def test_load_model_returns_template_lock(self, tmp_path):
        """load_model loads a TemplateLock and returns the correct type/values."""
        lock = TemplateLock(sha="deadbeef", repo="owner/repo", host="github", ref="main")
        lock_path = tmp_path / "template.lock"
        lock.to_yaml(lock_path)

        result = load_model(TemplateLock, lock_path)

        assert isinstance(result, TemplateLock)
        assert result.sha == "deadbeef"
        assert result.repo == "owner/repo"
