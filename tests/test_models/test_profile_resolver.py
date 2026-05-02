"""Tests for the profile resolver and ProfileDefinition/RhizaBundles profiles support."""

import pytest

from rhiza.models._profile_resolver import resolve_bundles
from rhiza.models.bundle import ProfileDefinition, RhizaBundles
from rhiza.models.template import RhizaTemplate

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BUNDLES_WITH_PROFILES = {
    "version": "1",
    "bundles": {
        "core": {"description": "Core", "files": ["Makefile"]},
        "book": {"description": "Book", "files": ["docs/"]},
        "tests": {"description": "Tests", "files": ["pytest.ini"]},
        "github": {"description": "GitHub CI", "files": [".github/workflows/ci.yml"]},
        "github-tests": {"description": "GitHub test workflows", "files": [".github/workflows/tests.yml"]},
    },
    "profiles": {
        "local": {
            "description": "Local-first setup",
            "bundles": ["core", "book", "tests"],
        },
        "github-project": {
            "description": "Standard GitHub project",
            "bundles": ["core", "github", "book", "tests", "github-tests"],
        },
    },
}


def _make_bundles(config=None) -> RhizaBundles:
    return RhizaBundles.from_config(config or _BUNDLES_WITH_PROFILES)


def _make_template(**kwargs) -> RhizaTemplate:
    defaults = {
        "template_repository": "owner/repo",
        "template_branch": "main",
    }
    defaults.update(kwargs)
    return RhizaTemplate(**defaults)


# ---------------------------------------------------------------------------
# ProfileDefinition dataclass
# ---------------------------------------------------------------------------


class TestProfileDefinition:
    """Tests for the ProfileDefinition dataclass."""

    def test_basic_construction(self):
        """ProfileDefinition stores description and bundles correctly."""
        p = ProfileDefinition(description="Test profile", bundles=["core", "tests"])
        assert p.description == "Test profile"
        assert p.bundles == ["core", "tests"]

    def test_empty_defaults(self):
        """ProfileDefinition defaults to empty description and bundles."""
        p = ProfileDefinition()
        assert p.description == ""
        assert p.bundles == []


# ---------------------------------------------------------------------------
# RhizaBundles — profiles field parsing
# ---------------------------------------------------------------------------


class TestRhizaBundlesProfiles:
    """Tests for the profiles field on RhizaBundles."""

    def test_profiles_parsed_from_config(self):
        """Known profile names are present after from_config."""
        rb = _make_bundles()
        assert "local" in rb.profiles
        assert "github-project" in rb.profiles

    def test_profile_bundles_correct(self):
        """Profile bundle list matches the source config."""
        rb = _make_bundles()
        assert rb.profiles["local"].bundles == ["core", "book", "tests"]

    def test_profile_description_correct(self):
        """Profile description is parsed from config."""
        rb = _make_bundles()
        assert "Local-first" in rb.profiles["local"].description

    def test_no_profiles_key_defaults_to_empty(self):
        """Old bundle files without a profiles section load without error."""
        rb = RhizaBundles.from_config({"bundles": {"core": {"description": "Core"}}})
        assert rb.profiles == {}

    def test_profiles_round_trips_through_config(self):
        """Profiles survive a config → from_config round-trip."""
        rb = _make_bundles()
        restored = RhizaBundles.from_config(rb.config)
        assert restored.profiles["local"].bundles == rb.profiles["local"].bundles

    def test_profiles_not_a_dict_raises_type_error(self):
        """TypeError raised when profiles value is not a dict."""
        with pytest.raises(TypeError, match="Profiles must be a dictionary"):
            RhizaBundles.from_config({"bundles": {}, "profiles": ["not", "a", "dict"]})

    def test_profile_entry_not_a_dict_raises_type_error(self):
        """TypeError raised when an individual profile entry is not a dict."""
        with pytest.raises(TypeError, match="Profile 'local' must be a dictionary"):
            RhizaBundles.from_config({"bundles": {}, "profiles": {"local": "not-a-dict"}})

    def test_config_omits_profiles_when_empty(self):
        """Config property omits the profiles key when there are no profiles."""
        rb = RhizaBundles.from_config({"bundles": {"core": {"description": "Core"}}})
        assert "profiles" not in rb.config

    def test_config_includes_profiles_when_present(self):
        """Config property includes the profiles key when profiles are defined."""
        rb = _make_bundles()
        assert "profiles" in rb.config
        assert "local" in rb.config["profiles"]


# ---------------------------------------------------------------------------
# RhizaTemplate — profiles field
# ---------------------------------------------------------------------------


class TestRhizaTemplateProfiles:
    """Tests for the profiles field on RhizaTemplate."""

    def test_profiles_defaults_to_empty(self):
        """RhizaTemplate.profiles defaults to an empty list."""
        t = RhizaTemplate()
        assert t.profiles == []

    def test_profiles_set_in_constructor(self):
        """Profiles passed to the constructor are stored correctly."""
        t = _make_template(profiles=["local"])
        assert t.profiles == ["local"]

    def test_from_config_parses_profiles(self):
        """from_config reads the profiles key from a config dict."""
        t = RhizaTemplate.from_config(
            {
                "repository": "owner/repo",
                "profiles": ["local"],
                "templates": [],
            }
        )
        assert t.profiles == ["local"]

    def test_from_config_no_profiles_key_is_empty(self):
        """Old template.yml files without profiles: load without error."""
        t = RhizaTemplate.from_config(
            {
                "repository": "owner/repo",
                "templates": ["core", "tests"],
            }
        )
        assert t.profiles == []

    def test_config_property_emits_profiles(self):
        """Config property includes profiles when set."""
        t = _make_template(profiles=["local"])
        assert "profiles" in t.config
        assert t.config["profiles"] == ["local"]

    def test_config_property_omits_profiles_when_empty(self):
        """Config property omits profiles key when profiles is empty."""
        t = _make_template(templates=["core"])
        assert "profiles" not in t.config


# ---------------------------------------------------------------------------
# resolve_bundles
# ---------------------------------------------------------------------------


class TestResolveBundles:
    """Tests for the resolve_bundles() function."""

    def test_profile_expands_to_bundles(self):
        """A single profile expands to its declared bundle list."""
        rb = _make_bundles()
        t = _make_template(profiles=["local"])
        result = resolve_bundles(t, rb)
        assert result == ["core", "book", "tests"]

    def test_explicit_templates_merged_and_deduplicated(self):
        """Explicit templates: added after profile expansion; duplicates dropped."""
        rb = _make_bundles()
        # local expands to [core, book, tests]; adding github should append it
        t = _make_template(profiles=["local"], templates=["github"])
        result = resolve_bundles(t, rb)
        assert result == ["core", "book", "tests", "github"]

    def test_duplicate_explicit_template_deduplicated(self):
        """A bundle already in the profile expansion is not duplicated."""
        rb = _make_bundles()
        t = _make_template(profiles=["local"], templates=["core"])
        result = resolve_bundles(t, rb)
        assert result.count("core") == 1

    def test_multiple_profiles_merged_in_order(self):
        """Multiple profiles are merged in declaration order without duplicates."""
        rb = _make_bundles()
        # github-project contains core, github, book, tests, github-tests
        # local contains core, book, tests  (core/book/tests already in first profile)
        t = _make_template(profiles=["github-project", "local"])
        result = resolve_bundles(t, rb)
        # All unique bundles from github-project, then local adds nothing new
        assert result == ["core", "github", "book", "tests", "github-tests"]

    def test_no_profiles_no_templates_returns_empty(self):
        """Old config with neither profiles nor templates passes through as empty list."""
        rb = _make_bundles()
        t = _make_template()  # no profiles, no templates
        result = resolve_bundles(t, rb)
        assert result == []

    def test_only_explicit_templates_no_profiles(self):
        """Explicit templates without profiles are returned as-is."""
        rb = _make_bundles()
        t = _make_template(templates=["core", "github"])
        result = resolve_bundles(t, rb)
        assert result == ["core", "github"]

    def test_unknown_profile_raises_value_error(self):
        """ValueError raised when a profile name is not in available_bundles.profiles."""
        rb = _make_bundles()
        t = _make_template(profiles=["nonexistent"])
        with pytest.raises(ValueError, match="Unknown profile 'nonexistent'"):
            resolve_bundles(t, rb)

    def test_unknown_bundle_in_explicit_templates_raises_value_error(self):
        """ValueError raised when an explicit template name is not a known bundle."""
        rb = _make_bundles()
        t = _make_template(templates=["nonexistent-bundle"])
        with pytest.raises(ValueError, match="Unknown bundle 'nonexistent-bundle'"):
            resolve_bundles(t, rb)

    def test_unknown_bundle_inside_profile_raises_value_error(self):
        """A profile referencing a bundle that doesn't exist raises ValueError."""
        bad_config = {
            "bundles": {"core": {"description": "Core", "files": ["Makefile"]}},
            "profiles": {
                "broken": {"description": "Broken profile", "bundles": ["core", "ghost-bundle"]},
            },
        }
        rb = RhizaBundles.from_config(bad_config)
        t = _make_template(profiles=["broken"])
        with pytest.raises(ValueError, match="unknown bundle 'ghost-bundle'"):
            resolve_bundles(t, rb)
