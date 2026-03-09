"""Comprehensive round-trip, end-to-end, and property-based tests for all Rhiza models.

Coverage targets
----------------
- TemplateLock  : config round-trip, YAML E2E, Hypothesis
- RhizaTemplate : config round-trip, YAML E2E, Hypothesis
- RhizaBundles  : config round-trip, YAML E2E, Hypothesis
- _base helpers : read_yaml edge-cases, load_model errors
"""

import tempfile
from pathlib import Path

import pytest
import yaml
from hypothesis import given
from hypothesis import strategies as st

from rhiza.models._base import YamlSerializable, load_model, read_yaml
from rhiza.models.bundle import RhizaBundles
from rhiza.models.lock import TemplateLock
from rhiza.models.template import GitHost, RhizaTemplate

# ---------------------------------------------------------------------------
# Shared Hypothesis strategies
# ---------------------------------------------------------------------------

# Alphanumeric + common path chars — safe for YAML serialisation
_safe_alpha = st.characters(
    whitelist_categories=("Lu", "Ll", "Nd"),
    whitelist_characters="-_./",
)
_text = st.text(alphabet=_safe_alpha, min_size=0, max_size=40)
_nonempty = st.text(alphabet=_safe_alpha, min_size=1, max_size=40)
_path_list = st.lists(_nonempty, max_size=6)

# ============================================================================
# TemplateLock
# ============================================================================

_lock_st = st.builds(
    TemplateLock,
    sha=_nonempty,
    repo=_text,
    host=st.sampled_from(["github", "gitlab"]),
    ref=_nonempty,
    include=_path_list,
    exclude=_path_list,
    templates=st.lists(_nonempty, max_size=5),
    files=_path_list,
    synced_at=st.one_of(st.just(""), _nonempty),
    strategy=st.one_of(st.just(""), st.sampled_from(["merge", "diff", "materialize"])),
)


class TestTemplateLockRoundTrip:
    """Round-trip: from_config(lock.config) == lock."""

    def test_minimal(self):
        """Minimal."""
        lock = TemplateLock(sha="abc")
        assert TemplateLock.from_config(lock.config) == lock

    def test_all_fields(self):
        """All fields."""
        lock = TemplateLock(
            sha="abc123",
            repo="owner/repo",
            host="gitlab",
            ref="develop",
            include=[".github/"],
            exclude=["README.md"],
            templates=["core"],
            files=["Makefile"],
            synced_at="2026-01-01T00:00:00Z",
            strategy="merge",
        )
        assert TemplateLock.from_config(lock.config) == lock

    def test_synced_at_omitted_when_empty(self):
        """Synced at omitted when empty."""
        assert "synced_at" not in TemplateLock(sha="x").config

    def test_strategy_omitted_when_empty(self):
        """Strategy omitted when empty."""
        assert "strategy" not in TemplateLock(sha="x").config

    def test_synced_at_included_when_set(self):
        """Synced at included when set."""
        assert TemplateLock(sha="x", synced_at="2026-01-01T00:00:00Z").config["synced_at"] == "2026-01-01T00:00:00Z"

    def test_strategy_included_when_set(self):
        """Strategy included when set."""
        assert TemplateLock(sha="x", strategy="merge").config["strategy"] == "merge"

    def test_host_serialised_as_string(self):
        """Host serialised as string."""
        assert TemplateLock(sha="x", host=GitHost.GITHUB).config["host"] == "github"
        assert TemplateLock(sha="x", host=GitHost.GITLAB).config["host"] == "gitlab"


class TestTemplateLockE2E:
    """End-to-end: write YAML to disk, read it back."""

    def test_creates_parent_directories(self, tmp_path):
        """Creates parent directories."""
        lock = TemplateLock(sha="deadbeef")
        path = tmp_path / "a" / "b" / "template.lock"
        lock.to_yaml(path)
        assert path.exists()

    def test_full_round_trip(self, tmp_path):
        """Full round trip."""
        lock = TemplateLock(
            sha="abc123",
            repo="owner/repo",
            host="gitlab",
            ref="main",
            include=["Makefile"],
            exclude=["secret.txt"],
            templates=["core"],
            files=["Makefile"],
            synced_at="2026-01-01T00:00:00Z",
            strategy="merge",
        )
        path = tmp_path / "template.lock"
        lock.to_yaml(path)
        assert TemplateLock.from_yaml(path) == lock

    def test_overwrite_is_idempotent(self, tmp_path):
        """Overwrite is idempotent."""
        lock = TemplateLock(sha="aaa", repo="x/y")
        path = tmp_path / "template.lock"
        lock.to_yaml(path)
        lock.to_yaml(path)
        assert TemplateLock.from_yaml(path) == lock

    def test_from_yaml_raises_file_not_found(self, tmp_path):
        """From yaml raises file not found."""
        with pytest.raises(FileNotFoundError):
            TemplateLock.from_yaml(tmp_path / "missing.lock")

    def test_from_yaml_raises_on_empty_file(self, tmp_path):
        """From yaml raises on empty file."""
        p = tmp_path / "empty.lock"
        p.write_text("")
        with pytest.raises(ValueError, match="is empty"):
            TemplateLock.from_yaml(p)

    def test_from_yaml_raises_on_yaml_list(self, tmp_path):
        """From yaml raises on yaml list."""
        p = tmp_path / "list.lock"
        p.write_text("- a\n- b\n")
        with pytest.raises(TypeError):
            TemplateLock.from_yaml(p)

    def test_load_model_helper(self, tmp_path):
        """Load model helper."""
        lock = TemplateLock(sha="cafe", repo="x/y")
        path = tmp_path / "template.lock"
        lock.to_yaml(path)
        result = load_model(TemplateLock, path)
        assert isinstance(result, TemplateLock)
        assert result.sha == "cafe"
        assert result.repo == "x/y"

    def test_satisfies_protocol(self):
        """Satisfies protocol."""
        assert isinstance(TemplateLock(sha="x"), YamlSerializable)


class TestTemplateLockHypothesis:
    """Property-based tests for TemplateLock."""

    @given(lock=_lock_st)
    def test_config_round_trip(self, lock):
        """Config round trip."""
        assert TemplateLock.from_config(lock.config) == lock

    @given(lock=_lock_st)
    def test_yaml_round_trip(self, lock):
        """Yaml round trip."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "template.lock"
            lock.to_yaml(path)
            assert TemplateLock.from_yaml(path) == lock

    @given(lock=_lock_st)
    def test_config_is_yaml_serialisable(self, lock):
        """Config is yaml serialisable."""
        data = yaml.safe_load(yaml.dump(lock.config))
        assert isinstance(data, dict)
        assert data["sha"] == lock.sha

    @given(lock=_lock_st)
    def test_sha_survives_config_round_trip(self, lock):
        """Sha survives config round trip."""
        assert TemplateLock.from_config(lock.config).sha == lock.sha

    @given(lock=_lock_st)
    def test_from_config_is_idempotent(self, lock):
        """From config is idempotent."""
        once = TemplateLock.from_config(lock.config)
        twice = TemplateLock.from_config(once.config)
        assert once == twice

    @given(lock=_lock_st)
    def test_config_always_contains_required_keys(self, lock):
        """Config always contains required keys."""
        cfg = lock.config
        for key in ("sha", "repo", "host", "ref", "include", "exclude", "templates", "files"):
            assert key in cfg


# ============================================================================
# RhizaTemplate
# ============================================================================

_template_st = st.builds(
    RhizaTemplate,
    template_repository=_text,
    template_branch=_text,
    template_host=st.sampled_from(["github", "gitlab"]),
    language=st.one_of(st.just("python"), _nonempty),
    include=_path_list,
    exclude=_path_list,
    templates=st.lists(_nonempty, max_size=5),
)


class TestRhizaTemplateRoundTrip:
    """Round-trip: from_config(template.config) == template."""

    def test_empty_template(self):
        """Empty template."""
        t = RhizaTemplate()
        assert RhizaTemplate.from_config(t.config) == t

    def test_with_repository_and_ref(self):
        """With repository and ref."""
        t = RhizaTemplate(template_repository="owner/repo", template_branch="main")
        assert RhizaTemplate.from_config(t.config) == t

    def test_with_gitlab_host(self):
        """With gitlab host."""
        t = RhizaTemplate(template_host="gitlab")
        assert RhizaTemplate.from_config(t.config) == t

    def test_github_host_is_omitted_from_config(self):
        """Default github host should be omitted to keep the file minimal."""
        t = RhizaTemplate(template_host="github")
        assert "template-host" not in t.config

    def test_gitlab_host_is_included_in_config(self):
        """Gitlab host is included in config."""
        assert RhizaTemplate(template_host="gitlab").config["template-host"] == "gitlab"

    def test_python_language_is_omitted_from_config(self):
        """Python language is omitted from config."""
        assert "language" not in RhizaTemplate(language="python").config

    def test_non_default_language_is_included(self):
        """Non default language is included."""
        assert RhizaTemplate(language="go").config["language"] == "go"

    def test_empty_repo_is_omitted(self):
        """Empty repo is omitted."""
        assert "repository" not in RhizaTemplate(template_repository="").config

    def test_nonempty_repo_is_included(self):
        """Nonempty repo is included."""
        assert RhizaTemplate(template_repository="x/y").config["repository"] == "x/y"

    def test_with_include_and_exclude(self):
        """With include and exclude."""
        t = RhizaTemplate(include=["Makefile"], exclude=["secret.txt"])
        assert RhizaTemplate.from_config(t.config) == t

    def test_with_templates(self):
        """With templates."""
        t = RhizaTemplate(templates=["core", "tests"])
        assert RhizaTemplate.from_config(t.config) == t

    def test_full_template_round_trip(self):
        """Full template round trip."""
        t = RhizaTemplate(
            template_repository="owner/repo",
            template_branch="develop",
            template_host="gitlab",
            language="go",
            include=["Makefile"],
            exclude=["secret.txt"],
            templates=["core"],
        )
        assert RhizaTemplate.from_config(t.config) == t


class TestRhizaTemplateE2E:
    """End-to-end: write YAML to disk, read it back."""

    def test_creates_parent_directories(self, tmp_path):
        """Creates parent directories."""
        t = RhizaTemplate(template_repository="x/y", include=["Makefile"])
        path = tmp_path / ".rhiza" / "template.yml"
        t.to_yaml(path)
        assert path.exists()

    def test_full_round_trip(self, tmp_path):
        """Full round trip."""
        t = RhizaTemplate(
            template_repository="owner/repo",
            template_branch="main",
            template_host="gitlab",
            language="go",
            include=["Makefile"],
            exclude=["secret.txt"],
            templates=["core"],
        )
        path = tmp_path / "template.yml"
        t.to_yaml(path)
        assert RhizaTemplate.from_yaml(path) == t

    def test_default_template_round_trip(self, tmp_path):
        """A template with only defaults serialises and deserialises cleanly."""
        t = RhizaTemplate()
        path = tmp_path / "template.yml"
        t.to_yaml(path)
        raw = yaml.safe_load(path.read_text())
        restored = RhizaTemplate.from_config({}) if raw is None else RhizaTemplate.from_yaml(path)
        assert restored == t

    def test_from_yaml_raises_file_not_found(self, tmp_path):
        """From yaml raises file not found."""
        with pytest.raises(FileNotFoundError):
            RhizaTemplate.from_yaml(tmp_path / "missing.yml")

    def test_from_yaml_raises_on_yaml_list(self, tmp_path):
        """From yaml raises on yaml list."""
        p = tmp_path / "bad.yml"
        p.write_text("- a\n- b\n")
        with pytest.raises(TypeError):
            RhizaTemplate.from_yaml(p)

    def test_load_model_helper(self, tmp_path):
        """Load model helper."""
        t = RhizaTemplate(template_repository="x/y", template_branch="main")
        path = tmp_path / "template.yml"
        t.to_yaml(path)
        result = load_model(RhizaTemplate, path)
        assert isinstance(result, RhizaTemplate)
        assert result.template_repository == "x/y"

    def test_satisfies_protocol(self):
        """Satisfies protocol."""
        assert isinstance(RhizaTemplate(), YamlSerializable)

    def test_repository_key_canonical(self, tmp_path):
        """to_yaml writes 'repository' key, which from_yaml reads back correctly."""
        t = RhizaTemplate(template_repository="owner/repo")
        path = tmp_path / "template.yml"
        t.to_yaml(path)
        data = yaml.safe_load(path.read_text())
        assert "repository" in data
        assert data["repository"] == "owner/repo"

    def test_ref_key_canonical(self, tmp_path):
        """Ref key canonical."""
        t = RhizaTemplate(template_branch="feature")
        path = tmp_path / "template.yml"
        t.to_yaml(path)
        data = yaml.safe_load(path.read_text())
        assert data["ref"] == "feature"


class TestRhizaTemplateHypothesis:
    """Property-based tests for RhizaTemplate."""

    @given(t=_template_st)
    def test_config_round_trip(self, t):
        """Config round trip."""
        assert RhizaTemplate.from_config(t.config) == t

    @given(t=_template_st)
    def test_yaml_round_trip(self, t):
        """Yaml round trip."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "template.yml"
            t.to_yaml(path)
            raw = yaml.safe_load(path.read_text())
            restored = RhizaTemplate.from_config({}) if raw is None else RhizaTemplate.from_yaml(path)
        assert restored == t

    @given(t=_template_st)
    def test_config_is_yaml_serialisable(self, t):
        """Config is yaml serialisable."""
        cfg = t.config
        raw = yaml.dump(cfg)
        data = yaml.safe_load(raw)
        # Empty config serialises as {} or null
        assert data is None or isinstance(data, dict)

    @given(t=_template_st)
    def test_from_config_is_idempotent(self, t):
        """From config is idempotent."""
        once = RhizaTemplate.from_config(t.config)
        twice = RhizaTemplate.from_config(once.config)
        assert once == twice

    @given(repo=_text, branch=_text)
    def test_repository_and_branch_survive_round_trip(self, repo, branch):
        """Repository and branch survive round trip."""
        t = RhizaTemplate(template_repository=repo, template_branch=branch)
        restored = RhizaTemplate.from_config(t.config)
        assert restored.template_repository == repo
        assert restored.template_branch == branch

    @given(
        include=_path_list,
        exclude=_path_list,
        templates=st.lists(_nonempty, max_size=5),
    )
    def test_lists_survive_round_trip(self, include, exclude, templates):
        """Lists survive round trip."""
        t = RhizaTemplate(include=include, exclude=exclude, templates=templates)
        restored = RhizaTemplate.from_config(t.config)
        assert restored.include == include
        assert restored.exclude == exclude
        assert restored.templates == templates


# ============================================================================
# RhizaBundles
# ============================================================================

_bundle_def_st = st.builds(
    dict,
    description=_text,
    files=st.one_of(st.none(), _path_list),
    workflows=st.one_of(st.none(), _path_list),
)

_bundles_config_st = st.fixed_dictionaries(
    {
        "bundles": st.dictionaries(
            keys=_nonempty,
            values=_bundle_def_st,
            min_size=0,
            max_size=5,
        )
    },
    optional={"version": _nonempty},
)


class TestRhizaBundlesRoundTrip:
    """Round-trip: from_config(bundles.config) == bundles."""

    def test_empty_bundles(self):
        """Empty bundles."""
        b = RhizaBundles.from_config({"bundles": {}})
        assert RhizaBundles.from_config(b.config) == b

    def test_bundle_with_files(self):
        """Bundle with files."""
        b = RhizaBundles.from_config({"bundles": {"core": {"description": "Core", "files": ["Makefile"]}}})
        assert RhizaBundles.from_config(b.config) == b

    def test_bundle_with_requires(self):
        """Bundle with depends on."""
        b = RhizaBundles.from_config(
            {
                "bundles": {
                    "core": {"description": "Core"},
                    "extended": {"description": "Extended", "requires": ["core"]},
                }
            }
        )
        restored = RhizaBundles.from_config(b.config)
        assert restored.bundles["extended"].depends_on == ["core"]

    def test_version_survives_round_trip(self):
        """Version survives round trip."""
        b = RhizaBundles.from_config({"version": "2", "bundles": {}})
        assert RhizaBundles.from_config(b.config).version == "2"

    def test_no_version_survives_round_trip(self):
        """No version survives round trip."""
        b = RhizaBundles.from_config({"bundles": {}})
        assert RhizaBundles.from_config(b.config).version is None


class TestRhizaBundlesE2E:
    """End-to-end: write YAML to disk, read it back."""

    def test_full_round_trip(self, tmp_path):
        """Full round trip."""
        b = RhizaBundles.from_config(
            {
                "version": "1",
                "bundles": {
                    "core": {"description": "Core", "files": ["Makefile"]},
                    "ci": {
                        "description": "CI",
                        "requires": ["core"],
                        "standalone": True,
                        "files": [".github/workflows/ci.yml"],
                    },
                },
            }
        )
        path = tmp_path / "template-bundles.yml"
        b.to_yaml(path)
        restored = RhizaBundles.from_yaml(path)
        assert restored.version == b.version
        assert set(restored.bundles.keys()) == set(b.bundles.keys())
        assert restored.bundles["core"].files == ["Makefile"]
        assert restored.bundles["ci"].requires == ["core"]

    def test_load_model_helper(self, tmp_path):
        """Load model helper."""
        b = RhizaBundles.from_config({"bundles": {"core": {"description": "Core"}}})
        path = tmp_path / "bundles.yml"
        b.to_yaml(path)
        result = load_model(RhizaBundles, path)
        assert isinstance(result, RhizaBundles)
        assert "core" in result.bundles

    def test_satisfies_protocol(self):
        """Satisfies protocol."""
        b = RhizaBundles.from_config({"bundles": {}})
        assert isinstance(b, YamlSerializable)

    def test_creates_parent_directories(self, tmp_path):
        """Creates parent directories."""
        b = RhizaBundles.from_config({"bundles": {}})
        path = tmp_path / "nested" / "dir" / "bundles.yml"
        b.to_yaml(path)
        assert path.exists()


class TestRhizaBundlesHypothesis:
    """Property-based tests for RhizaBundles."""

    @given(cfg=_bundles_config_st)
    def test_config_round_trip(self, cfg):
        """Config round trip."""
        b = RhizaBundles.from_config(cfg)
        restored = RhizaBundles.from_config(b.config)
        assert restored.version == b.version
        assert set(restored.bundles.keys()) == set(b.bundles.keys())
        for name in b.bundles:
            assert restored.bundles[name].files == b.bundles[name].files
            assert restored.bundles[name].requires == b.bundles[name].requires
            assert restored.bundles[name].standalone == b.bundles[name].standalone
            assert restored.bundles[name].description == b.bundles[name].description

    @given(cfg=_bundles_config_st)
    def test_yaml_round_trip(self, cfg):
        """Yaml round trip."""
        b = RhizaBundles.from_config(cfg)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bundles.yml"
            b.to_yaml(path)
            restored = RhizaBundles.from_yaml(path)
        assert restored.version == b.version
        assert set(restored.bundles.keys()) == set(b.bundles.keys())

    @given(cfg=_bundles_config_st)
    def test_config_is_yaml_serialisable(self, cfg):
        """Config is yaml serialisable."""
        b = RhizaBundles.from_config(cfg)
        raw = yaml.dump(b.config)
        data = yaml.safe_load(raw)
        assert isinstance(data, dict)
        assert "bundles" in data

    @given(cfg=_bundles_config_st)
    def test_from_config_is_idempotent(self, cfg):
        """From config is idempotent."""
        once = RhizaBundles.from_config(cfg)
        twice = RhizaBundles.from_config(once.config)
        assert once.version == twice.version
        assert set(once.bundles.keys()) == set(twice.bundles.keys())


# ============================================================================
# _base helpers
# ============================================================================


class TestReadYaml:
    """Tests for the read_yaml helper."""

    def test_reads_valid_mapping(self, tmp_path):
        """Reads valid mapping."""
        p = tmp_path / "data.yml"
        p.write_text("key: value\n")
        assert read_yaml(p) == {"key": "value"}

    def test_raises_file_not_found(self, tmp_path):
        """Raises file not found."""
        with pytest.raises(FileNotFoundError):
            read_yaml(tmp_path / "missing.yml")

    def test_raises_value_error_on_empty(self, tmp_path):
        """Raises value error on empty."""
        p = tmp_path / "empty.yml"
        p.write_text("")
        with pytest.raises(ValueError, match="is empty"):
            read_yaml(p)

    def test_raises_value_error_on_null(self, tmp_path):
        """Raises value error on null."""
        p = tmp_path / "null.yml"
        p.write_text("null\n")
        with pytest.raises(ValueError, match="is empty"):
            read_yaml(p)

    def test_raises_type_error_on_list(self, tmp_path):
        """Raises type error on list."""
        p = tmp_path / "list.yml"
        p.write_text("- a\n- b\n")
        with pytest.raises(TypeError, match="does not contain a YAML mapping"):
            read_yaml(p)

    def test_raises_type_error_on_scalar(self, tmp_path):
        """Raises type error on scalar."""
        p = tmp_path / "scalar.yml"
        p.write_text("just a string\n")
        with pytest.raises(TypeError, match="does not contain a YAML mapping"):
            read_yaml(p)


class TestLoadModel:
    """Tests for the load_model helper."""

    def test_raises_when_no_from_config(self, tmp_path):
        """Raises when no from config."""
        p = tmp_path / "data.yml"
        p.write_text("key: value\n")

        class NoFromConfig:
            pass

        with pytest.raises(TypeError, match="does not implement from_config"):
            load_model(NoFromConfig, p)

    def test_works_with_template_lock(self, tmp_path):
        """Works with template lock."""
        lock = TemplateLock(sha="abc")
        p = tmp_path / "template.lock"
        lock.to_yaml(p)
        result = load_model(TemplateLock, p)
        assert isinstance(result, TemplateLock)
        assert result.sha == "abc"

    def test_works_with_rhiza_bundles(self, tmp_path):
        """Works with rhiza bundles."""
        b = RhizaBundles.from_config({"bundles": {"core": {"description": "Core"}}})
        p = tmp_path / "bundles.yml"
        b.to_yaml(p)
        result = load_model(RhizaBundles, p)
        assert isinstance(result, RhizaBundles)
        assert "core" in result.bundles
