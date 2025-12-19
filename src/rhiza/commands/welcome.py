# This file is part of the jebel-quant/rhiza repository
# (https://github.com/jebel-quant/rhiza).
#
"""Command to display a welcome message and explain Rhiza.

This module provides the welcome command that displays a friendly greeting
and explains what Rhiza is and how it can help manage configuration templates.
"""

from loguru import logger

from rhiza import __version__


def welcome():
    """Display a welcome message and explain what Rhiza is.

    Shows a friendly greeting, explains Rhiza's purpose, and provides
    next steps for getting started with the tool.
    """
    logger.remove()  # Remove default logger to avoid timestamp prefixes

    welcome_message = f"""
╭───────────────────────────────────────────────────────────────╮
│                                                               │
│  🌿 Welcome to Rhiza v{__version__:<43} │
│                                                               │
╰───────────────────────────────────────────────────────────────╯

Rhiza helps you maintain consistent configuration across multiple
Python projects using reusable templates stored in a central repository.

✨ What Rhiza can do for you:

  • Initialize projects with standard configuration templates
  • Materialize (inject) templates into target repositories
  • Validate template configurations
  • Keep project configurations synchronized

🚀 Getting started:

  1. Initialize a project:
     $ rhiza init

  2. Customize .github/template.yml to match your needs

  3. Materialize templates into your project:
     $ rhiza materialize

📚 Learn more:

  • View all commands:    rhiza --help
  • Project repository:   https://github.com/jebel-quant/rhiza-cli
  • Documentation:        https://jebel-quant.github.io/rhiza-cli/

Happy templating! 🎉
"""

    print(welcome_message)
