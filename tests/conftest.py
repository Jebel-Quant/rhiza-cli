"""Shared pytest fixtures for the tests package.

Security Notes:
- S101 (assert usage): Asserts are appropriate in test code for validating conditions.
"""

from pathlib import Path

import pytest
import yaml


@pytest.fixture
def write_yaml(tmp_path):
    """Return a helper that dumps a dict as YAML to *name* in tmp_path.

    Usage::

        def test_something(write_yaml):
            path = write_yaml("config.yml", {"key": "value"})
            result = MyModel.from_yaml(path)
    """

    def _write(name: str, config: dict) -> Path:
        path = tmp_path / name
        with open(path, "w") as f:
            yaml.dump(config, f)
        return path

    return _write
