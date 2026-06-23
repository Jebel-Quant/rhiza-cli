# ADR-0005: Split the git engine into a `models/_git/` subpackage

**Status:** Accepted (supersedes [ADR-0004](0004-keep-git-utils-as-single-module.md))

## Context

[ADR-0004](0004-keep-git-utils-as-single-module.md) decided to keep
`src/rhiza/models/_git_utils.py` (~1011 LOC) as a single module, on the grounds
that it was one cohesive `GitContext` class with one responsibility — driving
`git`. That decision explicitly left a door open:

> If `GitContext` later grows distinct responsibilities (e.g. remote discovery
> vs. local patching) with their own consumers, revisit this decision and split
> along those seams.

On closer inspection, those seams are already present *within* `GitContext`. Its
methods cluster into three independent concerns that share only the
`executable`/`env` fields:

- **remote operations** — `clone_repository`, `clone_at_sha`,
  `update_sparse_checkout`, `get_head_sha`;
- **diffing** — `get_diff`, `sync_diff`, `_parse_diff_filenames`;
- **the 3-way merge strategy** — `sync_merge`, `_merge_with_base`, `_apply_diff`,
  `_merge_file_fallback`, `_scan_conflict_artifacts`, `_copy_files_to_target`.

Plus a band of module-level helpers (snapshot materialization and small
git/text utilities) that are not methods at all. The single file made it hard to
navigate to a concern and meant every change touched the same 1000-line module.

## Decision

Split `_git_utils.py` into a focused `rhiza/models/_git/` subpackage, preserving
the public surface and the cohesion of `GitContext`:

- `remote.py` — `RemoteOpsMixin`
- `diff.py` — `DiffMixin`
- `merge.py` — `MergeMixin` (composes the remote + diff mixins)
- `snapshot.py` — snapshot materialization helpers
- `helpers.py` — module-level git/text helpers (`get_git_executable`, …)
- `_base.py` — shared `executable`/`env` attribute declarations for the mixins
- `context.py` — the public `GitContext` dataclass, composed from the mixins

`GitContext` remains a **single class** assembled via mixins, so its cohesion and
public API are unchanged — `GitContext().clone_repository(...)`,
`.get_diff(...)`, `.sync_merge(...)` all still resolve. The mixin split is an
organisational seam, not a decomposition of the class's identity.

`models/_git_utils.py` is retained as a thin backwards-compatibility shim that
re-exports the public and previously module-private names, so existing imports
and the test suite's `patch("rhiza.models._git_utils.…")` targets keep working.

## Consequences

- ✅ No module in `models/` exceeds ~420 LOC (was 1011); each concern lives in
  its own file.
- ✅ 100% test coverage and `mypy --strict` are preserved; the public API and
  `GitContext`'s behaviour are unchanged.
- ✅ Future work touches a single concern's module rather than one large file.
- ⚠️ A compatibility shim (`_git_utils.py`) now exists purely for backwards
  compatibility; new code should import from `rhiza.models._git` (or
  `rhiza.models`) directly.
- ⚠️ `GitContext`'s implementation is now spread across mixins; readers must
  follow the MRO (`context → merge → remote/diff → _base`) to see the full
  surface. The `_git/__init__.py` module docstring maps this out.
