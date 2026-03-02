"""Tests for the list_repos command and CLI wiring.

This module verifies that `list_repos` correctly queries the GitHub API,
formats the output table, and that the `rhiza list` CLI entry point behaves
as expected.
"""

import json
import urllib.error
import urllib.request
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from rhiza.cli import app
from rhiza.commands.list_repos import (
    _DEFAULT_TOPIC,
    _format_date,
    _render_table,
    _RepoInfo,
    _wrap_text,
    list_repos,
)

# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _make_api_response(items: list[dict]) -> MagicMock:
    """Build a mock urllib response that returns *items* as JSON."""
    body = json.dumps({"total_count": len(items), "items": items}).encode()
    mock_resp = MagicMock()
    mock_resp.read.return_value = body
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


_SAMPLE_ITEM = {
    "full_name": "Jebel-Quant/rhiza",
    "description": "A collection of reusable configuration templates for modern Python projects",
    "updated_at": "2026-03-02T12:12:02Z",
}

_SAMPLE_ITEM_GO = {
    "full_name": "Jebel-Quant/rhiza-go",
    "description": "A collection of reusable configuration templates for modern Golang projects",
    "updated_at": "2026-03-02T12:15:20Z",
}


# ---------------------------------------------------------------------------
# _format_date
# ---------------------------------------------------------------------------


class TestFormatDate:
    """Tests for the _format_date helper."""

    def test_iso_date_truncated_to_date(self):
        """Verify that ISO 8601 timestamps are truncated to the date part."""
        assert _format_date("2026-03-02T12:12:02Z") == "2026-03-02"

    def test_empty_string_returns_empty(self):
        """Verify that an empty string returns an empty string."""
        assert _format_date("") == ""

    def test_plain_date_string_unchanged(self):
        """Verify that plain date strings are returned unchanged."""
        assert _format_date("2026-03-02") == "2026-03-02"


# ---------------------------------------------------------------------------
# _wrap_text
# ---------------------------------------------------------------------------


class TestWrapText:
    """Tests for the _wrap_text helper."""

    def test_short_text_not_wrapped(self):
        """Verify that short text does not get wrapped."""
        assert _wrap_text("hello", 10) == ["hello"]

    def test_empty_string_returns_one_empty_line(self):
        """Verify that an empty string returns a single empty line."""
        assert _wrap_text("", 20) == [""]

    def test_long_text_wrapped_at_word_boundary(self):
        """Verify that long text is wrapped at word boundaries within width limit."""
        text = "A collection of reusable configuration templates for modern Python projects"
        lines = _wrap_text(text, 30)
        assert all(len(line) <= 30 for line in lines)
        assert len(lines) > 1

    def test_joined_lines_contain_all_words(self):
        """Verify that wrapped lines when joined contain all original words."""
        text = "one two three four five six seven eight nine ten"
        lines = _wrap_text(text, 15)
        assert " ".join(lines) == text


# ---------------------------------------------------------------------------
# _render_table
# ---------------------------------------------------------------------------


class TestRenderTable:
    """Tests for the _render_table helper."""

    def test_no_repos_returns_no_repositories_message(self):
        """Verify that an empty list returns a 'No repositories found' message."""
        assert _render_table([]) == "No repositories found."

    def test_table_contains_repo_name(self):
        """Verify that the rendered table contains the repository name."""
        repos = [_RepoInfo("owner/repo", "A description", "2026-01-01T00:00:00Z")]
        table = _render_table(repos)
        assert "owner/repo" in table

    def test_table_contains_description(self):
        """Verify that the rendered table contains the repository description."""
        repos = [_RepoInfo("owner/repo", "My unique description", "2026-01-01T00:00:00Z")]
        table = _render_table(repos)
        assert "My unique description" in table

    def test_table_contains_date(self):
        """Verify that the rendered table contains the update date."""
        repos = [_RepoInfo("owner/repo", "desc", "2026-03-02T12:00:00Z")]
        table = _render_table(repos)
        assert "2026-03-02" in table

    def test_table_has_header_row(self):
        """Verify that the rendered table includes header row with column names."""
        repos = [_RepoInfo("owner/repo", "desc", "2026-01-01")]
        table = _render_table(repos)
        assert "Repo" in table
        assert "Description" in table
        assert "Updated" in table

    def test_table_has_box_drawing_characters(self):
        """Verify that the rendered table contains box-drawing characters."""
        repos = [_RepoInfo("owner/repo", "desc", "2026-01-01")]
        table = _render_table(repos)
        assert "┌" in table
        assert "┘" in table
        assert "│" in table

    def test_multiple_repos_each_in_table(self):
        """Verify that multiple repositories are each included in the rendered table."""
        repos = [
            _RepoInfo("org/repo-a", "Description A", "2026-01-01T00:00:00Z"),
            _RepoInfo("org/repo-b", "Description B", "2026-02-01T00:00:00Z"),
        ]
        table = _render_table(repos)
        assert "org/repo-a" in table
        assert "org/repo-b" in table


# ---------------------------------------------------------------------------
# list_repos (unit — mocked HTTP)
# ---------------------------------------------------------------------------


class TestListRepos:
    """Tests for the list_repos function."""

    def test_returns_true_on_success(self, capsys):
        """Verify that list_repos returns True when API call succeeds."""
        mock_resp = _make_api_response([_SAMPLE_ITEM])
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = list_repos()
        assert result is True

    def test_output_contains_repo_name(self, capsys):
        """Verify that output contains the repository name."""
        mock_resp = _make_api_response([_SAMPLE_ITEM])
        with patch("urllib.request.urlopen", return_value=mock_resp):
            list_repos()
        captured = capsys.readouterr()
        assert "Jebel-Quant/rhiza" in captured.out

    def test_output_contains_both_repos(self, capsys):
        """Verify that output contains both repositories."""
        mock_resp = _make_api_response([_SAMPLE_ITEM, _SAMPLE_ITEM_GO])
        with patch("urllib.request.urlopen", return_value=mock_resp):
            list_repos()
        captured = capsys.readouterr()
        assert "Jebel-Quant/rhiza" in captured.out
        assert "Jebel-Quant/rhiza-go" in captured.out

    def test_returns_false_on_network_error(self):
        """Verify that list_repos returns False when a network error occurs."""
        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("connection refused"),
        ):
            result = list_repos()
        assert result is False

    def test_empty_items_returns_true_no_table(self, capsys):
        """Verify that empty items return True and produce no table output."""
        mock_resp = _make_api_response([])
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = list_repos()
        assert result is True
        captured = capsys.readouterr()
        assert "┌" not in captured.out

    def test_uses_default_topic(self, capsys):
        """Verify that the default topic is used in the API request."""
        mock_resp = _make_api_response([_SAMPLE_ITEM])
        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_open:
            list_repos()
        call_args = mock_open.call_args
        req = call_args[0][0]
        assert f"topic:{_DEFAULT_TOPIC}" in req.full_url

    def test_custom_topic_used_in_request(self, capsys):
        """Verify that a custom topic is used in the API request when provided."""
        mock_resp = _make_api_response([_SAMPLE_ITEM])
        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_open:
            list_repos(topic="rhiza-go")
        call_args = mock_open.call_args
        req = call_args[0][0]
        assert "topic:rhiza-go" in req.full_url

    def test_github_token_added_to_headers(self, monkeypatch):
        """Verify that the GitHub token is added to request headers when set."""
        monkeypatch.setenv("GITHUB_TOKEN", "test-token-abc")
        mock_resp = _make_api_response([_SAMPLE_ITEM])
        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_open:
            list_repos()
        call_args = mock_open.call_args
        req = call_args[0][0]
        assert req.get_header("Authorization") == "Bearer test-token-abc"

    def test_no_github_token_no_auth_header(self, monkeypatch):
        """Verify that no Authorization header is added when GitHub token is not set."""
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        mock_resp = _make_api_response([_SAMPLE_ITEM])
        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_open:
            list_repos()
        call_args = mock_open.call_args
        req = call_args[0][0]
        assert req.get_header("Authorization") is None


# ---------------------------------------------------------------------------
# CLI wiring — `rhiza list`
# ---------------------------------------------------------------------------


class TestListCli:
    """Tests for the `rhiza list` CLI entry point."""

    def test_cli_list_exits_zero_on_success(self):
        """Verify that the CLI list command exits with code 0 on success."""
        mock_resp = _make_api_response([_SAMPLE_ITEM])
        runner = CliRunner()
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = runner.invoke(app, ["list"])
        assert result.exit_code == 0

    def test_cli_list_output_contains_repo(self):
        """Verify that the CLI list command output contains the repository name."""
        mock_resp = _make_api_response([_SAMPLE_ITEM])
        runner = CliRunner()
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = runner.invoke(app, ["list"])
        assert "Jebel-Quant/rhiza" in result.output

    def test_cli_list_exits_one_on_error(self):
        """Verify that the CLI list command exits with code 1 on network error."""
        runner = CliRunner()
        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("network error"),
        ):
            result = runner.invoke(app, ["list"])
        assert result.exit_code == 1

    def test_cli_list_custom_topic(self):
        """Verify that the CLI list command uses a custom topic when provided."""
        mock_resp = _make_api_response([_SAMPLE_ITEM_GO])
        runner = CliRunner()
        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_open:
            runner.invoke(app, ["list", "--topic", "rhiza-go"])
        call_args = mock_open.call_args
        req = call_args[0][0]
        assert "topic:rhiza-go" in req.full_url

    def test_cli_list_short_topic_flag(self):
        """Verify that the CLI list command accepts the short topic flag (-t)."""
        mock_resp = _make_api_response([_SAMPLE_ITEM_GO])
        runner = CliRunner()
        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_open:
            runner.invoke(app, ["list", "-t", "rhiza-go"])
        call_args = mock_open.call_args
        req = call_args[0][0]
        assert "topic:rhiza-go" in req.full_url

    def test_cli_list_help_exits_zero(self):
        """Verify that the CLI list help command exits with code 0."""
        runner = CliRunner()
        result = runner.invoke(app, ["list", "--help"])
        assert result.exit_code == 0
