#!/usr/bin/env python3
"""Generate PR description for rhiza sync operations.

This script is a thin wrapper around the rhiza summarise command.
It imports the logic from rhiza.commands.summarise to avoid code duplication.
"""

import argparse
import sys
from pathlib import Path


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Generate PR description for rhiza sync")
    parser.add_argument(
        "repo_path",
        nargs="?",
        default=".",
        help="Path to the repository (default: current directory)",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Output file (default: stdout)",
    )

    args = parser.parse_args()

    repo_path = Path(args.repo_path).resolve()

    if not repo_path.exists():
        print(f"Error: Repository path does not exist: {repo_path}", file=sys.stderr)
        sys.exit(1)

    # Import from command module to avoid code duplication
    try:
        from rhiza.commands.summarise import generate_pr_description
    except ImportError:
        print(
            "Error: Could not import rhiza.commands.summarise. Make sure rhiza is installed: pip install -e .",
            file=sys.stderr,
        )
        sys.exit(1)

    description = generate_pr_description(repo_path)

    if args.output:
        output_path = Path(args.output)
        output_path.write_text(description)
        print(f"PR description written to {output_path}")
    else:
        print(description)


if __name__ == "__main__":
    main()
