"""Modern terminal UI for Rhiza using Textual framework."""

import asyncio
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, ScrollableContainer
from textual.reactive import reactive
from textual.widgets import Button, Footer, Header, Label, Static

from rhiza.ui.git_scanner import GitRepositoryScanner


class RepoCard(Static):
    """Widget displaying a single repository's information."""

    def __init__(self, repo_info: dict, scanner: GitRepositoryScanner) -> None:
        """Initialize repository card.

        Args:
            repo_info: Repository information dictionary.
            scanner: Git scanner instance for executing operations.
        """
        super().__init__()
        self.repo_info = repo_info
        self.scanner = scanner

    def compose(self) -> ComposeResult:
        """Compose the repository card UI."""
        status_colors = {
            "clean": "green",
            "changes": "yellow",
            "ahead": "blue",
            "behind": "red",
            "diverged": "magenta",
            "no-remote": "grey",
        }
        status = self.repo_info["status"]
        status_color = status_colors.get(status, "white")
        
        # Create compact single-line info strings
        changes_icon = "⚠️" if self.repo_info['has_changes'] else "✅"
        ahead_behind = f"↑{self.repo_info['ahead']} ↓{self.repo_info['behind']}" if self.repo_info['has_remote'] else "no remote"

        yield Container(
            Horizontal(
                Label(f"📁 {self.repo_info['name']}", classes="repo-name"),
                Label(f"[{status_color}]●[/] {status.upper()}", classes="repo-status"),
            ),
            Label(f"🌿 [cyan]{self.repo_info['branch']}[/] │ {changes_icon} │ {ahead_behind} │ 🕐 {self.repo_info['last_commit_date']}"),
            Label(f"💬 {self.repo_info['last_commit_msg'][:80]}...", classes="commit-msg") if len(self.repo_info['last_commit_msg']) > 80 else Label(f"💬 {self.repo_info['last_commit_msg']}", classes="commit-msg"),
            Horizontal(
                Button("📥 Fetch", variant="primary", id=f"fetch-{self.repo_info['name']}"),
                Button("⬇️ Pull", variant="success", id=f"pull-{self.repo_info['name']}"),
                Button("⬆️ Push", variant="warning", id=f"push-{self.repo_info['name']}"),
                Button("📊 Status", variant="default", id=f"status-{self.repo_info['name']}"),
                classes="repo-actions",
            ),
            classes="repo-card",
        )


class StatsBar(Static):
    """Widget displaying repository statistics."""

    total_repos = reactive(0)
    clean_repos = reactive(0)
    changed_repos = reactive(0)
    ahead_repos = reactive(0)
    behind_repos = reactive(0)

    def compose(self) -> ComposeResult:
        """Compose the stats bar UI."""
        yield Horizontal(
            Static(f"📊 Total: [bold cyan]{self.total_repos}[/]", classes="stat"),
            Static(f"✅ Clean: [bold green]{self.clean_repos}[/]", classes="stat"),
            Static(f"⚠️ Changes: [bold yellow]{self.changed_repos}[/]", classes="stat"),
            Static(f"⬆️ Ahead: [bold blue]{self.ahead_repos}[/]", classes="stat"),
            Static(f"⬇️ Behind: [bold red]{self.behind_repos}[/]", classes="stat"),
            classes="stats-bar",
        )

    def update_stats(self, repos: list[dict]) -> None:
        """Update statistics based on repository list.

        Args:
            repos: List of repository information dictionaries.
        """
        self.total_repos = len(repos)
        self.clean_repos = len([r for r in repos if r["status"] == "clean"])
        self.changed_repos = len([r for r in repos if r["status"] == "changes"])
        self.ahead_repos = len([r for r in repos if r["status"] in ("ahead", "diverged")])
        self.behind_repos = len([r for r in repos if r["status"] in ("behind", "diverged")])


class RhizaApp(App):
    """Main Rhiza UI application using Textual."""

    CSS = """
    Screen {
        background: $surface;
    }

    .repo-card {
        border: solid $primary;
        padding: 0 1;
        margin: 0 1 1 1;
        background: $panel;
        width: 100%;
        height: auto;
    }

    .repo-name {
        text-style: bold;
        color: $text;
    }

    .repo-status {
        text-align: right;
    }

    .repo-info {
        padding: 0;
        color: $text-muted;
    }

    .commit-msg {
        padding: 0;
        color: $text-muted;
        text-style: italic;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    .repo-actions {
        height: auto;
        padding: 0;
    }

    .stats-bar {
        dock: top;
        height: 3;
        background: $panel;
        padding: 1;
    }

    .stat {
        padding: 0 2;
    }

    .controls {
        dock: top;
        height: 3;
        background: $panel;
        padding: 1;
    }

    #folder-label {
        padding: 0 2;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh"),
        ("f", "fetch_all", "Fetch All"),
        ("p", "pull_all", "Pull All"),
        ("u", "push_all", "Push All"),
    ]

    def __init__(self, folder: Path) -> None:
        """Initialize the Rhiza UI app.

        Args:
            folder: Path to folder containing Git repositories.
        """
        super().__init__()
        self.folder = folder
        self.scanner = GitRepositoryScanner(folder)
        self.repos = []

    def compose(self) -> ComposeResult:
        """Compose the main UI layout."""
        yield Header()
        yield Container(
            Label(f"Monitoring: {self.folder}", id="folder-label"),
            Horizontal(
                Button("🔄 Refresh", variant="primary", id="refresh"),
                Button("📥 Fetch All", variant="success", id="fetch-all"),
                Button("⬇️ Pull All", variant="success", id="pull-all"),
                Button("⬆️ Push All", variant="warning", id="push-all"),
            ),
            classes="controls",
        )
        yield StatsBar(id="stats")
        yield ScrollableContainer(id="repo-list")
        yield Footer()

    async def on_mount(self) -> None:
        """Handle mount event to load initial data."""
        self.title = "🌳 Rhiza UI - Multi-Repository Manager"
        await self.action_refresh()

    async def action_refresh(self) -> None:
        """Refresh repository list."""
        self.notify("Refreshing repositories...")

        # Run scanner in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        self.repos = await loop.run_in_executor(None, self.scanner.scan_repositories)

        # Update stats
        stats = self.query_one("#stats", StatsBar)
        stats.update_stats(self.repos)

        # Update repo list
        repo_list = self.query_one("#repo-list", ScrollableContainer)
        await repo_list.remove_children()

        for repo in self.repos:
            await repo_list.mount(RepoCard(repo, self.scanner))

        self.notify(f"Found {len(self.repos)} repositories", severity="information")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events.

        Args:
            event: Button press event.
        """
        button_id = event.button.id

        if button_id == "refresh":
            await self.action_refresh()
        elif button_id == "fetch-all":
            await self.action_fetch_all()
        elif button_id == "pull-all":
            await self.action_pull_all()
        elif button_id == "push-all":
            await self.action_push_all()
        elif button_id and "-" in button_id:
            # Individual repo operation
            operation, repo_name = button_id.split("-", 1)
            await self.execute_operation(repo_name, operation)

    async def execute_operation(self, repo_name: str, operation: str) -> None:
        """Execute Git operation on a repository.

        Args:
            repo_name: Name of the repository.
            operation: Operation to execute (fetch, pull, push, status).
        """
        self.notify(f"Running {operation} on {repo_name}...")

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, self.scanner.execute_git_operation, repo_name, operation)

        if result["success"]:
            self.notify(f"✅ {operation} completed: {result['message']}", severity="information")
        else:
            self.notify(f"❌ {operation} failed: {result['message']}", severity="error")

        # Refresh after operation
        await self.action_refresh()

    async def action_fetch_all(self) -> None:
        """Fetch all repositories."""
        self.notify("Fetching all repositories...")
        success_count = 0
        fail_count = 0

        loop = asyncio.get_event_loop()
        for repo in self.repos:
            result = await loop.run_in_executor(None, self.scanner.execute_git_operation, repo["name"], "fetch")
            if result["success"]:
                success_count += 1
            else:
                fail_count += 1

        self.notify(
            f"Fetch completed: {success_count} succeeded, {fail_count} failed",
            severity="information" if fail_count == 0 else "warning",
        )
        await self.action_refresh()

    async def action_pull_all(self) -> None:
        """Pull all repositories."""
        self.notify("Pulling all repositories...")
        success_count = 0
        fail_count = 0

        loop = asyncio.get_event_loop()
        for repo in self.repos:
            result = await loop.run_in_executor(None, self.scanner.execute_git_operation, repo["name"], "pull")
            if result["success"]:
                success_count += 1
            else:
                fail_count += 1

        self.notify(
            f"Pull completed: {success_count} succeeded, {fail_count} failed",
            severity="information" if fail_count == 0 else "warning",
        )
        await self.action_refresh()

    async def action_push_all(self) -> None:
        """Push all repositories."""
        self.notify("Pushing all repositories...")
        success_count = 0
        fail_count = 0

        loop = asyncio.get_event_loop()
        for repo in self.repos:
            result = await loop.run_in_executor(None, self.scanner.execute_git_operation, repo["name"], "push")
            if result["success"]:
                success_count += 1
            else:
                fail_count += 1

        self.notify(
            f"Push completed: {success_count} succeeded, {fail_count} failed",
            severity="information" if fail_count == 0 else "warning",
        )
        await self.action_refresh()
