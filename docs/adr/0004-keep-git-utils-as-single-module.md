# ADR-0004: Keep `models/_git_utils.py` as a single module

**Status:** Superseded by [ADR-0005](0005-split-git-engine-into-subpackage.md)

## Context

`src/rhiza/models/_git_utils.py` is the largest module in the codebase at ~1000 LOC,
roughly 2.6× the next-largest source file. Issue #526 raised whether it should be split
into focused submodules for maintainability.

On inspection, the module is dominated by a single cohesive `GitContext` class
(~815 LOC) that encapsulates one responsibility: driving `git` (sparse-checkout,
ls-remote, snapshot preparation, diff/patch application) for a template checkout. The
remaining ~175 LOC are seven private helper functions that exist solely to support
`GitContext` and are not used elsewhere.

## Decision

Keep `_git_utils.py` as a single module rather than splitting it.

- The bulk is one class with a single responsibility; splitting a class across files
  to satisfy a line count would reduce cohesion, not improve it.
- The module-level helpers are tightly coupled to `GitContext` and have no independent
  consumers, so extracting them would create artificial seams.
- The module has 100% test coverage; there is no correctness or navigability pain
  driving a split today.

If `GitContext` later grows distinct responsibilities (e.g. remote discovery vs. local
patching) with their own consumers, revisit this decision and split along those seams.

## Consequences

- ✅ Cohesion preserved — related git logic stays in one place.
- ✅ No churn or regression risk from moving heavily-tested code.
- ⚠️ The module remains large; reviewers should watch for the emergence of separable
  responsibilities as a trigger to revisit (superseding ADR).
