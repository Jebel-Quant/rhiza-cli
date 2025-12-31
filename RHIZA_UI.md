# Rhiza UI - Multi-Repository Management Dashboard

## Overview

Rhiza UI is a modern terminal-based dashboard for monitoring and managing multiple Git repositories in a specified folder. Built with [Textual](https://textual.textualize.io/), it provides a rich, interactive terminal interface without requiring a web browser.

![Rhiza UI Screenshot](https://github.com/user-attachments/assets/b51362c5-a49c-43e8-b6fe-742b2ca0b257)
*Web UI mode screenshot*

## Features

### 1. Repository Scanning and Overview
- Automatically detects all Git repositories in a specified folder
- Displays repository information including:
  - Repository name
  - Current branch
  - Git status (clean, changes, ahead, behind, diverged, no-remote)
  - Last commit information
  - Ahead/behind commit counts
  - Remote URL (if configured)

### 2. Repository Monitoring
- Real-time status indicators with color-coded badges
- Keyboard shortcuts for quick actions
- Visual notifications for operations
- Responsive terminal interface

### 3. Batch Operations
Execute Git operations across all repositories simultaneously:
- **Fetch All**: Fetch updates from all remotes (keyboard: `f`)
- **Pull All**: Pull changes from all remotes (keyboard: `p`)
- **Push All**: Push changes to all remotes (keyboard: `u`)
- Operation status feedback with success/failure counts

### 4. Individual Repository Management
For each repository, you can:
- View detailed status information
- Execute individual Git operations:
  - Fetch
  - Pull
  - Push
  - Status check
- See real-time operation results

### 5. Status Indicators

Repositories are marked with color-coded status badges:
- **Clean** (Green): No uncommitted changes, in sync with remote
- **Changes** (Yellow): Uncommitted local changes
- **Ahead** (Blue): Local commits not pushed to remote
- **Behind** (Red): Remote commits not pulled locally
- **Diverged** (Magenta): Both ahead and behind remote
- **No Remote** (Gray): No remote configured

## Installation

Install Rhiza (includes Textual for the terminal UI):

```bash
pip install rhiza
```

## Usage

### Terminal UI (Default - Recommended)

Launch the modern terminal UI:

```bash
rhiza ui
```

Monitor a specific folder:

```bash
rhiza ui /path/to/repositories
```

### Keyboard Shortcuts

- `r` - Refresh repository list
- `f` - Fetch all repositories
- `p` - Pull all repositories
- `u` - Push all repositories
- `q` - Quit application

### Command Options

```bash
rhiza ui [OPTIONS] [FOLDER]
```

**Arguments:**
- `FOLDER`: Folder containing Git repositories (default: current directory)

### Examples

```bash
# Terminal UI (default)
rhiza ui
rhiza ui ~/projects
```

## Architecture

The Rhiza UI consists of several components:

### 1. Git Scanner (`rhiza.ui.git_scanner`)
- Scans folders for Git repositories
- Extracts repository information using Git commands
- Executes Git operations on repositories

### 2. Terminal UI (`rhiza.ui.tui`) - Default
- Modern Textual-based interface
- Rich terminal widgets and styling
- Async operation handling
- Keyboard-driven interaction

## Why Textual?

We chose [Textual](https://textual.textualize.io/) as the default UI framework because:

1. **Modern**: Built for Python 3.11+, uses modern async/await patterns
2. **No Browser Required**: Runs directly in your terminal
3. **Rich Experience**: Beautiful, responsive TUI with widgets and styling
4. **Cross-Platform**: Works on Windows, macOS, and Linux
5. **Lightweight**: No heavyweight dependencies or web server needed
6. **Fast**: Instant startup, no network latency
7. **Developer-Friendly**: Clean API, excellent documentation

## Use Cases

### 1. Managing Multiple Projects
Perfect for developers working on multiple projects who need to:
- Keep track of uncommitted changes across repositories
- Ensure all repositories are up-to-date
- Quickly identify repositories that need attention

### 2. Team Collaboration
Useful for teams to:
- Monitor the state of multiple project repositories
- Perform bulk updates before meetings
- Identify diverged or outdated repositories

### 3. CI/CD Preparation
Before deploying or running CI/CD:
- Check all repositories are clean
- Ensure all changes are committed
- Verify all repositories are in sync with remotes

### 4. Repository Maintenance
For repository maintainers to:
- Get a bird's-eye view of all repositories
- Perform bulk maintenance operations
- Identify repositories needing attention

## Tips and Best Practices

1. **Organize Your Repositories**: Keep related repositories in a common parent folder for easy monitoring

2. **Use Auto-Refresh**: The UI auto-refreshes every 30 seconds, keeping status information current

3. **Batch Operations with Caution**: Always review the confirmation dialog before batch operations

## Limitations

- Only monitors repositories in the immediate child directories (not recursive)
- Requires Git to be installed and accessible in PATH
- Operations timeout after 30 seconds
- No authentication (designed for local use)

## Troubleshooting

### Repositories not detected
- Ensure folders contain `.git` directory
- Check folder permissions
- Verify Git is installed: `git --version`

### Operations fail
- Verify Git credentials are configured
- Check network connectivity for remote operations
- Ensure repositories have remotes configured for fetch/pull/push

## Future Enhancements

Potential future features:
- Integration with GitHub/GitLab/Bitbucket APIs
- Display open pull requests and issues
- Show CI/CD status
- Recursive repository scanning
- WebSocket for real-time updates
- Repository grouping and filtering
- Git history visualization
- Conflict detection and resolution
- Configuration file support

## Contributing

Contributions to Rhiza UI are welcome! Please see the main [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

Rhiza UI is part of the Rhiza project and is licensed under the MIT License.
