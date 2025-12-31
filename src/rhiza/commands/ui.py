"""Rhiza UI command for monitoring and managing multiple Git repositories.

This module provides a modern terminal-based UI application for monitoring
and managing multiple Git repositories in a specified folder.
"""

from pathlib import Path

from loguru import logger


def ui(
    folder: Path,
    web: bool = False,
    port: int = 8080,
    no_browser: bool = False,
) -> None:
    """Launch Rhiza UI for monitoring multiple Git repositories.

    Args:
        folder: Path to folder containing Git repositories to monitor.
        web: Use web-based UI instead of terminal UI (default: False).
        port: Port number for the web server (default: 8080, only used with --web).
        no_browser: If True, don't automatically open browser (only used with --web).

    Raises:
        ImportError: If required dependencies are not installed.
        RuntimeError: If the UI fails to start.
    """
    _launch_terminal_ui(folder)


def _launch_terminal_ui(folder: Path) -> None:
    """Launch modern terminal-based UI using Textual.

    Args:
        folder: Path to folder containing Git repositories to monitor.

    Raises:
        ImportError: If Textual is not installed.
    """
    logger.info(f"Starting Rhiza UI for folder: {folder}")

    # Import and run Textual app
    from rhiza.ui.tui import RhizaApp

    app = RhizaApp(folder)
    try:
        app.run()
    except KeyboardInterrupt:
        logger.info("Shutting down Rhiza UI...")
    except Exception as e:
        logger.error(f"Failed to start Rhiza UI: {e}")
        raise RuntimeError(f"UI startup failed: {e}") from e
