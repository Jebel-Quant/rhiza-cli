#!/bin/bash -eu
# ClusterFuzzLite build script — installs the package so the frozen harness can
# import `rhiza` at runtime, then compiles each Python harness in tests/fuzz/
# via OSS-Fuzz's compile_python_fuzzer helper.

cd "$SRC"

# Pin pip so the build environment is reproducible and only changes through a
# reviewed bump (the same rationale as the SHA-pinned base image).
pip3 install --upgrade "pip==24.3.1"

# Install the package (src-layout) and its runtime deps into the build image so
# PyInstaller can discover and bundle `rhiza` into each frozen fuzz binary.
pip3 install .

for fuzzer in tests/fuzz/fuzz_*.py; do
  compile_python_fuzzer "$fuzzer"
done
