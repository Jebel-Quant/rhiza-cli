"""Rhiza UI command for monitoring and managing multiple Git repositories.

This module provides a desktop UI application for monitoring and managing
multiple Git repositories in a specified folder.
"""

import subprocess
import threading
import webbrowser
from pathlib import Path
from typing import Any

from loguru import logger


def ui(
    folder: Path,
    port: int = 8080,
    no_browser: bool = False,
) -> None:
    """Launch Rhiza UI for monitoring multiple Git repositories.

    Args:
        folder: Path to folder containing Git repositories to monitor.
        port: Port number for the web server (default: 8080).
        no_browser: If True, don't automatically open browser.

    Raises:
        ImportError: If required dependencies are not installed.
        RuntimeError: If the server fails to start.
    """
    try:
        from flask import Flask
    except ImportError:
        logger.error(
            "Flask is required for Rhiza UI. Install with: pip install 'rhiza[ui]'"
        )
        raise

    logger.info(f"Starting Rhiza UI for folder: {folder}")
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
    logger.info("Rhiza UI is running. Press Ctrl+C to stop.")
    try:
        app.run(host="0.0.0.0", port=port, debug=False)
    except KeyboardInterrupt:
        logger.info("Shutting down Rhiza UI...")
    except Exception as e:
        logger.error(f"Failed to start Rhiza UI: {e}")
        raise RuntimeError(f"Server startup failed: {e}") from e
