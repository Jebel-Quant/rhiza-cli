# This file is part of the jebel-quant/rhiza repository
# (https://github.com/jebel-quant/rhiza).
#
"""Command to display a welcome message and explain Rhiza.

This module provides the welcome command that displays a friendly greeting
and explains what Rhiza is and how it can help manage configuration templates.
"""

from rhiza import __version__


def welcome() -> None:
    """Display a welcome message and explain what Rhiza is.

    Shows a friendly greeting, explains Rhiza's purpose, and provides
    next steps for getting started with the tool.

    This command is useful for new users to understand what Rhiza does
    and how to get started. It provides a high-level overview without
    performing any operations on the file system.
    """
    # Construct a nicely formatted welcome message with ASCII art border
    # The version is dynamically inserted from the package metadata
    welcome_message = f"""
╭───────────────────────────────────────────────────────────────╮
│                                                               │
│  🌿 Welcome to Rhiza v{__version__:<39} │
│                                                               │
╰───────────────────────────────────────────────────────────────╯

Rhiza helps you maintain consistent configuration across multiple
Python projects using reusable templates stored in a central repository.

✨ What Rhiza can do for you:

  • Initialize projects with standard configuration templates
  • Sync templates into target repositories (with 3-way merge)
  • Validate template configurations
  • Keep project configurations synchronized

🚀 Getting started:

  1. Initialize a project:
     $ rhiza init

  2. Customize .rhiza/template.yml to match your needs

  3. Sync templates into your project:
     $ rhiza sync

📚 Learn more:

  • View all commands:    rhiza --help
  • Project repository:   https://github.com/jebel-quant/rhiza-cli
  • Documentation:        https://jebel-quant.github.io/rhiza-cli/

Happy templating! 🎉
"""

    # Print the welcome message to stdout
    print(welcome_message)
