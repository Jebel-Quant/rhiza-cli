# ADR-0001: Inline `get_diff` instead of depending on `cruft`

**Status**: Accepted

## Context

The original `sync` command depended on `cruft` — a third-party template management
tool — to compute the diff between the base and upstream versions of a template. This
required importing `cruft`'s private `_generate_diff` API, which:

1. Was an undocumented internal function not intended for external use and subject to
   breaking changes without notice.
2. Added `cruft` as a runtime dependency even though Rhiza only used a single helper.
3. Made the diff pipeline opaque: callers could not control the exact `git diff`
   arguments (e.g., prefixes, binary handling, path stripping) needed for the
   subsequent `git apply -3` step.
4. Introduced cross-platform path issues on Windows where absolute path prefixes in
   the generated diff prevented clean patch application.

## Decision

Replace the `cruft` dependency with an inline `_get_diff(repo0, repo1)` function in
`src/rhiza/commands/sync.py` that calls `git diff --no-index` directly:

```python
result = subprocess.run(
    [
        git, "-c", "diff.noprefix=",
        "diff", "--no-index", "--relative", "--binary",
        f"--src-prefix={_DIFF_SRC_PREFIX}/",
        f"--dst-prefix={_DIFF_DST_PREFIX}/",
        "--no-ext-diff", "--no-color",
        repo0_str, repo1_str,
    ],
    cwd=repo0_str,
    capture_output=True,
)
```

Fixed prefixes (`upstream-template-old` / `upstream-template-new`) are used and any
absolute path segments are stripped from the diff output so that `git apply -3` can
locate files relative to the project root on all platforms.

## Consequences

**Positive**

- `cruft` is no longer a runtime dependency, reducing the dependency surface area and
  eliminating the risk of upstream breakage from internal API changes.
- Full control over every `git diff` flag: `--binary` handles binary files correctly,
  `--no-ext-diff` prevents external diff drivers from corrupting the patch, and the
  fixed prefix scheme is stable across runs.
- Cross-platform path normalisation (Windows drive letters are stripped via regex)
  makes the patch portable.
- The implementation is self-contained and easier to test in isolation.

**Negative**

- `git` must be available on `PATH` (mitigated by `subprocess_utils.get_git_executable`
  which raises a clear error if git is missing).
- The regex strip of drive letters (`/[a-z]:`) is a heuristic that could in theory
  affect non-Windows paths with a matching pattern, though this has not been observed
  in practice.
