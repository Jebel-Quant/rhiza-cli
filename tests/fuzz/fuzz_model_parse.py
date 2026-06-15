"""Fuzz the Rhiza model parsers against arbitrary YAML configuration input.

``RhizaTemplate``, ``TemplateLock``, and ``RhizaBundles`` each parse untrusted
YAML (``.rhiza/template.yml`` and ``.rhiza/template.lock``) into a model via
``from_config``. This harness feeds arbitrary bytes through the same
``YAML -> mapping -> from_config`` path and asserts the parsers either build a
model or reject the input with a documented, well-formed error — never an
unexpected crash.

Run locally:
    RHIZA_FUZZ_ROOT=$(pwd) pip install atheris
    RHIZA_FUZZ_ROOT=$(pwd) python tests/fuzz/fuzz_model_parse.py -atheris_runs=10000

Run in ClusterFuzzLite: this file is built by .clusterfuzzlite/build.sh.
"""

from __future__ import annotations

import contextlib
import os
import sys
from pathlib import Path

import atheris
import yaml

# When running from the source tree (local development), add src/ to sys.path so
# the rhiza package imports without installation. In ClusterFuzzLite, build.sh
# runs `pip install .`, so the package is already importable in the frozen binary.
_REPO_ROOT = Path(os.environ.get("RHIZA_FUZZ_ROOT", str(Path(__file__).resolve().parent.parent.parent)))
_src_dir = str(_REPO_ROOT / "src")
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from rhiza.models.bundle import RhizaBundles  # noqa: E402
from rhiza.models.lock import TemplateLock  # noqa: E402
from rhiza.models.template import RhizaTemplate  # noqa: E402

# Exceptions that represent a well-formed rejection of malformed input, as
# documented on the parsers (read_yaml / from_config / BundleFileEntry).
_EXPECTED_PARSE_ERRORS = (yaml.YAMLError, ValueError, TypeError, KeyError, AttributeError)


def test_one_input(data: bytes) -> None:
    """Parse arbitrary YAML input through each model's from_config path."""
    text = data.decode("utf-8", errors="replace")
    try:
        parsed = yaml.safe_load(text)
    except yaml.YAMLError:
        return
    if not isinstance(parsed, dict):
        return
    for model in (RhizaTemplate, TemplateLock, RhizaBundles):
        with contextlib.suppress(_EXPECTED_PARSE_ERRORS):
            model.from_config(parsed)


def main() -> None:
    """Run the Atheris fuzz loop."""
    atheris.Setup(sys.argv, test_one_input)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
