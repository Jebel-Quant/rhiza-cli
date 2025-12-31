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
    if web:
        _launch_web_ui(folder, port, no_browser)
    else:
        _launch_terminal_ui(folder)


def _launch_terminal_ui(folder: Path) -> None:
    """Launch modern terminal-based UI using Textual.

    Args:
        folder: Path to folder containing Git repositories to monitor.

    Raises:
        ImportError: If Textual is not installed.
    """
    try:
        from textual.app import App
    except ImportError:
        logger.error(
            "Textual is required for Rhiza UI. Install with: pip install 'rhiza[ui]'"
        )
        raise

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


def _launch_web_ui(folder: Path, port: int, no_browser: bool) -> None:
    """Launch web-based UI using Flask (legacy mode).

    Args:
        folder: Path to folder containing Git repositories to monitor.
        port: Port number for the web server.
        no_browser: If True, don't automatically open browser.

    Raises:
        ImportError: If Flask is not installed.
        RuntimeError: If the server fails to start.
    """
    import threading
    import webbrowser

    try:
        from flask import Flask
    except ImportError:
        logger.error(
            "Flask is required for web UI. Install with: pip install flask"
        )
        raise

    logger.info(f"Starting Rhiza Web UI for folder: {folder}")
    logger.info(f"Server will run on http://localhost:{port}")

    # Import UI server module
    from rhiza.ui.server import create_app

    # Create Flask app
    app = create_app(folder)

    # Open browser after short delay if not disabled
    if not no_browser:

        def open_browser():
            import time

            time.sleep(1.5)  # Wait for server to start
            webbrowser.open(f"http://localhost:{port}")

        threading.Thread(target=open_browser, daemon=True).start()

    # Start server
    logger.info("Rhiza Web UI is running. Press Ctrl+C to stop.")
    try:
        app.run(host="127.0.0.1", port=port, debug=False)
    except KeyboardInterrupt:
        logger.info("Shutting down Rhiza Web UI...")
    except Exception as e:
        logger.error(f"Failed to start Rhiza Web UI: {e}")
        raise RuntimeError(f"Server startup failed: {e}") from e
