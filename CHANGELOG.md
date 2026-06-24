# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com),
and entries are generated from [Conventional Commits](https://www.conventionalcommits.org).

## [0.18.0] - 2026-06-24

### Bug Fixes
- *(fuzz)* Treat RecursionError as a well-formed rejection in fuzz_model_parse (#551)

### Documentation
- Add documentation map cross-links; fix Issues URL (#535)
- Add architecture overview tracing the sync flow (#546)

### Maintenance
- Chore(deps)(deps): bump the python-dependencies group with 3 updates (#522)
- Chore(deps)(deps): bump the github-actions group with 9 updates (#521)
- Remove stray pr-description.md from repo root (#529)
- Add Rhiza Claude commands (/rhiza_quality, /rhiza_update) (#536)
- Chore(deps)(deps): bump the python-dependencies group with 4 updates (#542)
- Chore(deps)(deps): bump actions/checkout in the github-actions group (#541)
- Chore(deps-dev)(deps-dev): bump the python-dependencies group with 3 updates (#549)
- Chore(deps)(deps): bump jebel-quant/rhiza/.github/workflows/rhiza_mutation.yml (#548)
- *(models)* Split _git_utils into a _git/ subpackage (ADR-0005) (#547)
- *(fuzz)* Copy source into $SRC directly and pin pip in the build (#550)

### Other Changes
- Enable pytest timeout support in test environment (#528)
- Address repository analysis findings (#523–#526) (#527)
- Sync Rhiza template v0.18.8 → v0.19.1 (#540)
- Sync Rhiza template v0.18.8 → v0.19.3 (#544)
- Sync Rhiza template v0.19.3 → v0.19.4 (#545)

## [0.17.6] - 2026-06-08

### Maintenance
- Chore(deps)(deps): bump the python-dependencies group with 3 updates (#515)
- Update rhiza to v0.18.8 (#517)
- Chore(deps)(deps): bump the github-actions group with 9 updates (#516)

### Other Changes
- Update rhiza_book.yml to use version 0.18.7
- Potential fix for code scanning alert no. 5: Incomplete URL substring sanitization (#520)
- Potential fix for code scanning alert no. 7: Incomplete URL substring sanitization (#519)
- Bump version 0.17.5 → 0.17.6

## [0.17.5] - 2026-05-30

### Maintenance
- Remove redundant trailing newline in __init__.py.jinja2 template
- Remove unused pyproject.toml.template

### Other Changes
- Bump version 0.17.4 → 0.17.5

## [0.17.4] - 2026-05-30

### Bug Fixes
- Preserve trailing newlines in Jinja2-rendered files

### Other Changes
- Bump version 0.17.3 → 0.17.4

## [0.17.3] - 2026-05-30

### New Features
- *(init)* Generate mkdocs.yml with host-aware URLs

### Other Changes
- Bump version 0.17.2 → 0.17.3

## [0.17.2] - 2026-05-30

### New Features
- *(init)* Enrich generated pyproject.toml and run uv lock

### Other Changes
- Bump version 0.17.1 → 0.17.2

## [0.17.1] - 2026-05-30

### New Features
- *(init)* Fail early when target is not a git repository

### Other Changes
- Bump version 0.17.0 → 0.17.1

## [0.17.0] - 2026-05-30

### New Features
- Improve rhiza init scaffolding (pyproject.toml, Makefile, template.yml)
- *(init)* Resolve latest tag from template repo instead of pinning to main
- *(init)* Auto-detect git host from origin remote URL

### Bug Fixes
- *(init)* Hide empty default brackets in template repo prompt
- *(init)* Default template repo selection to [1] instead of []

### Maintenance
- Update rhiza to v0.15.2 (#508)
- Update rhiza to v0.15.3 (#509)
- Update rhiza to v0.17.0 (#510)
- Update rhiza to v0.18.4 (#511)
- Chore(deps)(deps): bump the github-actions group with 8 updates (#512)
- Chore(deps)(deps): bump the python-dependencies group with 2 updates (#513)

### Other Changes
- Remove unused templates from template.yml
- Bump version 0.16.1 → 0.17.0

## [0.16.1] - 2026-05-25

### Bug Fixes
- Follow symlinks when scanning bundle directories

### Other Changes
- Bump version 0.16.0 → 0.16.1

## [0.16.0] - 2026-05-25

### New Features
- Support directory-based bundle resolution (no explicit files) (#506)

### Other Changes
- Bump version 0.15.0 → 0.16.0

## [0.15.0] - 2026-05-25

### New Features
- Add path remapping support for bundle file entries (#504)

### Bug Fixes
- Point coverage badge at GitHub Pages URL

### Other Changes
- Bump version 0.14.1 → 0.15.0

## [0.14.1] - 2026-05-24

### New Features
- Change profile from scalar to list (profiles)

### Other Changes
- Bump version 0.14.0 → 0.14.1

## [0.14.0] - 2026-05-24

### New Features
- Add profile support to template configuration (#502)

### Other Changes
- Bump version 0.13.6 → 0.14.0

## [0.13.6] - 2026-05-23

### Bug Fixes
- *(init)* Normalise package name in generated test file import (#489)
- *(docs)* Fix index page rendering and update nav

### Dependencies
- *(deps)* Lock file maintenance (#491)

### Maintenance
- Chore(deps)(deps): bump github/codeql-action in the github-actions group (#492)
- Chore(deps)(deps): bump github/codeql-action in the github-actions group (#494)
- Update via rhiza (#496)
- Chore(deps-dev)(deps-dev): bump hypothesis (#495)
- Chore(deps)(deps): bump the python-dependencies group with 2 updates (#500)
- Sync rhiza template to v0.10.9 (#501)
- Chore(deps)(deps): bump github/codeql-action in the github-actions group (#499)
- *(docs)* Comment out theme and markdown_extensions in mkdocs.yml
- Bring test coverage to 100%

### Other Changes
- Update template.yml
- Delete renovate.json
- Resolve template bundle dependencies transitively in templates mode (#498)
- Bump version 0.13.5 → 0.13.6

## [0.13.5] - 2026-05-02

### Bug Fixes
- *(docs)* Set docs_dir: docs to avoid site_dir inside docs_dir error
- *(book)* Remove unsupported -d flag from zensical build
- *(summarise)* Use template.lock/RhizaTemplate model for template info; add output customisation flags (#470)
- Skip template.lock write when no effective changes after sync (#478)
- Resolve broken links in README.md (weekly link-check CI) (#486)

### Documentation
- Docs
- Simplify mkdocs.yml via INHERIT from docs/mkdocs-base.yml

### Dependencies
- *(deps)* Lock file maintenance (#473)
- *(deps)* Lock file maintenance (#484)

### Maintenance
- Chore(deps)(deps): bump the python-dependencies group with 2 updates (#467)
- Chore(deps-dev)(deps-dev): bump hypothesis (#475)
- Sync rhiza template to v0.9.5 (#476)
- Chore(deps-dev)(deps-dev): bump hypothesis (#482)
- Chore(deps)(deps): bump github/codeql-action in the github-actions group (#481)

### Other Changes
- Tschm patch 1 (#465)
- Remove security and quality targets from Makefile
- Add mkdocs.yml and fix book target when mkdocs is skipped
- Update template branch to v0.9.2 (#471)
- Rhiza/update template v0.10.1 (#480)
- Rhiza/update template v0.10.3 (#483)
- [WIP] Fix issue with unresolved conflict markers in sync (#469)
- Bump version 0.13.4 → 0.13.5

## [0.13.4] - 2026-04-02

### Maintenance
- Chore(deps)(deps): bump github/codeql-action in the github-actions group (#462)
- Chore(deps)(deps): bump the python-dependencies group across 1 directory with 2 updates (#463)

### Other Changes
- Update template branch to v0.8.20 and add renovate (#464)
- Bump version 0.13.3 → 0.13.4

## [0.13.3] - 2026-03-22

### Bug Fixes
- Replace broken coverage badge with direct gh-pages SVG (#454)

### Maintenance
- Chore(deps)(deps): bump rhiza-tools in the python-dependencies group (#444)

### Other Changes
- Update template branch to v0.8.14 (#452)
- Modify license field in pyproject.toml (#456)
- Update template branch version to v0.8.16 (#455)
- Bump version 0.13.2 → 0.13.3

## [0.13.2] - 2026-03-18

### Bug Fixes
- Derive template-bundles.yml path from --path-to-template directory (#449)

### Maintenance
- Chore(deps)(deps): bump astral-sh/setup-uv (#447)

### Other Changes
- Update template branch to v0.8.13 and modify templates (#446)

## [0.13.1] - 2026-03-13

### New Features
- Add --path-to-template option to rhiza validate and rhiza init (#442)

### Other Changes
- Bump version 0.13.0 → 0.13.1

## [0.13.0] - 2026-03-13

### New Features
- *(sync)* Custom bundle path + hybrid mode merge (#440)

### Other Changes
- Bump version 0.12.2 → 0.13.0

## [0.12.2] - 2026-03-12

### Maintenance
- Chore(deps)(deps): bump github/codeql-action in the github-actions group (#431)

### Other Changes
- Use Rich trees for `rhiza tree` output (#436)
- Bump version 0.12.1 → 0.12.2

## [0.12.1] - 2026-03-09

### Bug Fixes
- *(models)* Make `TemplateLock` immutable with `@dataclass(frozen=Tr… (#426)

### Maintenance
- Slim RhizaTemplate to a pure data class (#427)
- Eliminate duplicated code patterns across command modules (#429)

### Other Changes
- Sort `files` section alphabetically in template.lock (#422)
- Template.lock include field contains resolved paths instead of original config values (#424)
- Frozen2 (#428)
- Bump version 0.12.0 → 0.12.1

## [0.12.0] - 2026-03-08

### Bug Fixes
- *(models)* Set default values for `template_repository` and `template_branch` fields

### Maintenance
- *(sync)* Remove unnecessary type casts for `template_repositor… (#395)
- Split monolithic models.py into a models/ subpackage (#397)
- Consolidate _log_git_stderr_errors, fix docstring, logging, and exception narrowing (#401)
- Consolidate `_log_git_stderr_errors` into `models/_git_utils.py` (#409)
- *(sync)* Remove redundant helper functions, consolidate `_sync… (#417)
- *(models)* Add `TYPE_CHECKING` imports for TemplateLock and Rh… (#418)
- *(tests)* Replace `_read_lock` calls with `TemplateLock.read_s… (#419)
- *(bundle)* Add coverage for RhizaBundles.config property to reach 100%
- *(models)* Add comprehensive round-trip, E2E, and Hypothesis tests
- *(tests)* Move model tests into tests/test_models/ folder
- *(tests)* Remove unnecessary __init__.py from test_models
- *(tests)* Remove `test_bundle_resolver.py` and relocate `test_git_utils.py` into `test_models/`
- *(models)* Increase test coverage to 100%

### Other Changes
- Deprecate the `migrate` command (#377)
- Move clone/snapshot logic onto RhizaTemplate; remove redundant _sync_helpers functions (#379)
- Analysis
- Remove mypy configuration from pyproject.toml
- Migrate template helpers from `_sync_helpers` to `RhizaTemplate` private methods (#383)
- Remove `rhiza welcome` command (#391)
- Inline bundle_resolver.py into models.py (#392)
- Move `get_git_executable` from `subprocess_utils` into `models` (#393)
- Refactor CLI error handling with `_exit_on_error` context manager (#394)
- Trim verbose docstring in `commands/__init__.py` (#398)
- Remove deprecated `materialize` command (#399)
- Standardise YAML serialization behind a shared Protocol and generic helper (#405)
- Replace stringly-typed `git_host` with `GitHost` StrEnum (#407)
- Revisit tests: rename test_subprocess_utils.py, split test_models.py, add write_yaml fixture (#411)
- Establish GitContext dataclass for injectable git context (#415)
- Git refactor (#416)
- Bump version 0.11.12 → 0.12.0

## [0.11.12] - 2026-03-07

### Bug Fixes
- Restore template-managed files missing from target during sync (#375)

### Other Changes
- Block sync when git working tree is dirty (#371)
- Bump version 0.11.11 → 0.11.12

## [0.11.11] - 2026-03-07

### Other Changes
- Prevent absent files from being recorded in template.lock (#373)
- Bump version 0.11.10 → 0.11.11

## [0.11.10] - 2026-03-07

### Other Changes
- Re-sync when template.yml config changes even if upstream SHA is unchanged (#364)
- No stop (#369)
- End-to-end tests for updated template.yml include list + orphan cleanup bug fix (#366)
- Bump version 0.11.9 → 0.11.10

## [0.11.9] - 2026-03-07

### Other Changes
- Add `rhiza tree` command to display managed files as a directory tree (#362)
- Bump version 0.11.8 → 0.11.9

## [0.11.8] - 2026-03-07

### New Features
- Interactive template repository picker in `rhiza init` (#338)

### Bug Fixes
- Persist and populate files list in template.lock to enable orphan deletion (#342)

### Maintenance
- Chore(deps)(deps): bump github/codeql-action in the github-actions group (#340)
- Chore(deps)(deps): bump rhiza-tools in the python-dependencies group (#341)
- *(tests)* Reduce test_uninstall.py from 621 to 340 LOC (#347)

### Other Changes
- Remove history file fallback from uninstall command (#344)
- Smaller tests (#345)
- Reduce test_sync.py bloat (2,715 → 2,247 lines) (#349)
- Refactor test_sync.py: parametrize duplicate tests and consolidate fixtures (#352)
- Remove `.rhiza.history` root-level legacy fallback from `_read_previously_tracked_files` (#354)
- Move `_sync_helpers` into the `commands` subpackage (#356)
- Implement end-to-end sync tests + fix excluded-file orphan deletion bug (#358)
- Fix orphan cleanup for lock files missing the `files` field (#360)
- Achieve 100% test coverage and fix test_sync_core import path
- Bump version 0.11.7 → 0.11.8

## [0.11.7] - 2026-03-02

### Dependencies
- *(deps)* Update dependency astral-sh/uv to v0.10.7 (#333)
- *(deps)* Update astral-sh/setup-uv action to v7.3.1 (#332)

### Maintenance
- Increase coverage to 100% (#336)

### Other Changes
- Create a test file when doing init (#334)
- Bump version 0.11.6 → 0.11.7

## [0.11.6] - 2026-02-27

### Bug Fixes
- Fall back to git merge-file when apply -3 lacks blob objects

### Maintenance
- Sync template to 0404d2f35361 (v0.8.5)

### Other Changes
- Sync
- Delete .rhiza/history
- Bump version 0.11.5 → 0.11.6

## [0.11.5] - 2026-02-27

### New Features
- Add `rhiza status` command (#317)
- *(sync)* Concurrency-safe lock file I/O with fcntl + atomic rename (#315)

### Bug Fixes
- Loosen PyYAML pin and migrate materialize to sync (#303)
- Migrate rhiza_sync.yml from deprecated `materialize --force` to `rhiza sync` (#305)

### Documentation
- Reorder REPOSITORY_ANALYSIS.md newest-first
- Remove PyYAML exact-pin weakness from latest analysis entries
- Add ADR directory with two initial architecture decision records (#309)
- Add ADR-0003 for lock file concurrency (#323)
- Update Third Analysis to 9.5/10 reflecting PRs #315–#323
- Correct misleading version comparison in REPOSITORY_ANALYSIS
- Add authentication guide for private template repositories (#325)

### Other Changes
- Actually remove cruft — inline get_diff and drop dependency (#297)
- Template.lock:
- Updated REPOSITORY ANALYSIS
- Initial plan (#301)
- Delete .rhiza/history (#302)
- Retire materialize.py: consolidate shared helpers into sync.py (#299)
- Validate template repository reachability before writing config in `rhiza init` (#307)
- Analysis
- Add rhiza sync smoke test CI workflow (#321)
- [WIP] Extract sync internals to _sync_helpers.py (#319)
- Analysis
- Analysis
- Bump version 0.11.4-rc.6 → 0.11.5

## [0.11.4-rc.6] - 2026-02-26

### New Features
- Add `synced_at` and `strategy` metadata to `TemplateLock` (#296)

### Bug Fixes
- Make `repository` and `ref` the canonical YAML keys (#292)

### Other Changes
- Remove `files` section from `template.lock` (#286)
- Remove obsolete dev dependency-group (#288)
- Remove cruft
- [WIP] Remove direct calls to sys.exit() in command modules (#290)
- Bump version 0.11.4-rc.5 → 0.11.4-rc.6

## [0.11.4-rc.5] - 2026-02-26

### Other Changes
- Bump version 0.11.4-rc.4 → 0.11.4-rc.5

## [0.11.4-rc.4] - 2026-02-26

### Other Changes
- Improve .rhiza/template.lock YAML output format (#284)
- Bump version 0.11.4-rc.3 → 0.11.4-rc.4

## [0.11.4-rc.3] - 2026-02-26

### Other Changes
- Template.lock include field reflects template.yml verbatim (#282)
- Bump version 0.11.4-rc.2 → 0.11.4-rc.3

## [0.11.4-rc.2] - 2026-02-26

### Other Changes
- Fix build: replace `uvx hatch build` with `uv build` (#280)
- Bump version 0.11.4-rc.1 → 0.11.4-rc.2

## [0.11.4-rc.1] - 2026-02-26

### New Features
- Delete orphaned files during sync when template.yml changes (#271)

### Other Changes
- Deprecate `materialize` — collapse into `sync` (#273)
- Remove `--strategy overwrite` from `rhiza sync` (#276)
- Enhance template.lock to structured YAML with full sync metadata (#278)
- Bump version 0.11.3 → 0.11.4-rc.1

## [0.11.3] - 2026-02-24

### Dependencies
- *(deps)* Update dependency jebel-quant/rhiza to v0.8.3 (#266)

### Other Changes
- Bump version 0.11.2 → 0.11.3

## [0.11.2] - 2026-02-24

### Dependencies
- *(deps)* Update pre-commit hook astral-sh/ruff-pre-commit to v0.15.2 (#254)
- *(deps)* Lock file maintenance (#259)
- *(deps)* Update pre-commit hook astral-sh/uv-pre-commit to v0.10.5 (#265)
- *(deps)* Update dependency astral-sh/uv to v0.10.5 (#264)

### Maintenance
- Chore(deps)(deps): bump github/codeql-action in the github-actions group (#261)

### Other Changes
- Use repository and ref in init (#257)
- Make `version` field optional in bundle files (#263)
- Bump version 0.11.1-beta.2 → 0.11.2

## [0.11.1-beta.2] - 2026-02-20

### Dependencies
- *(deps)* Update pre-commit hook astral-sh/uv-pre-commit to v0.10.4 (#251)
- *(deps)* Update dependency astral-sh/uv to v0.10.4 (#250)

### Other Changes
- Add language-specific validation and init support for multi-language templates (#253)
- Bump version 0.11.1-beta.1 → 0.11.1-beta.2

## [0.11.1-beta.1] - 2026-02-17

### Dependencies
- *(deps)* Lock file maintenance (#238)
- *(deps)* Update pre-commit hook rhysd/actionlint to v1.7.11 (#239)
- *(deps)* Update actions/download-artifact action to v7 (#237)
- *(deps)* Update pre-commit hook astral-sh/uv-pre-commit to v0.10.3 (#242)
- *(deps)* Update pre-commit hook python-jsonschema/check-jsonschema to v0.36.2 (#243)
- *(deps)* Update dependency astral-sh/uv to v0.10.3 (#241)
- *(deps)* Update dependency jebel-quant/rhiza to v0.8.0 (#240)

### Maintenance
- Chore(deps)(deps): bump typer in the python-dependencies group (#245)
- Replace custom sync with cruft-based diff/merge (#244)

### Other Changes
- Update template branch to v0.7.5
- Sync (#236)
- Bump version 0.11.0 → 0.11.1-beta.1
- Revert "Chore: bump version 0.11.0 → 0.11.1-beta.1"
- Bump version 0.11.0 → 0.11.1-beta.1
- Revert "Chore: bump version 0.11.0 → 0.11.1-beta.1"
- Enhance version verification in rhiza_release.yml (#248)
- Bump version 0.11.0 → 0.11.1-beta.1

## [0.11.0] - 2026-02-13

### Other Changes
- Support alternative field names for gentler validation (#234)
- Bump version 0.10.4 → 0.11.0

## [0.10.4] - 2026-02-12

### Dependencies
- *(deps)* Lock file maintenance (#222)
- *(deps)* Lock file maintenance (#223)
- *(deps)* Lock file maintenance (#225)
- *(deps)* Update dependency astral-sh/uv to v0.10.1 (#226)
- *(deps)* Update pre-commit hook jebel-quant/rhiza-hooks to v0.2.1 (#228)
- *(deps)* Update pre-commit hook astral-sh/uv-pre-commit to v0.10.2 (#227)

### Other Changes
- Improve test coverage from 95% to 99%
- Fmt
- Sync (#229)
- Init with template rather than include (#231)
- Sync21 (#232)
- Bump version 0.10.3 → 0.10.4

## [0.10.3] - 2026-02-07

### Maintenance
- Chore(deps-dev)(deps-dev): bump marimo in the python-dependencies group (#221)

### Other Changes
- Tschm patch 1 (#220)
- Remove versioning configuration for template-bundles.yml
- Bump version 0.10.2 → 0.10.3

## [0.10.2] - 2026-02-05

### Other Changes
- Update rhiza-hooks to version 0.1.5 (#217)
- Fix template bundles filename reference from underscore to hyphen (#219)
- Update Rhiza validation version in workflow (#212)
- Bump version 0.10.1 → 0.10.2

## [0.10.1] - 2026-02-05

### Other Changes
- Update .rhiza-version
- Fix test to expect default RHIZA_VERSION 0.10.0
- Rename bundles.yml to template_bundles.yml
- Delete .github/workflows/rhiza_benchmarks.yml (#214)
- Delete book directory (#215)
- Delete .rhiza/make.d/02-book.mk (#213)
- Delete .github/workflows/rhiza_book.yml
- Delete .github/workflows/rhiza_marimo.yml (#216)
- Bump version 0.10.0 → 0.10.1

## [0.10.0] - 2026-02-05

### Dependencies
- *(deps)* Update github/codeql-action action to v4.32.1 (#199)
- *(deps)* Update pre-commit hook jebel-quant/rhiza-hooks to v0.1.3 (#200)
- *(deps)* Lock file maintenance (#201)
- *(deps)* Update pre-commit hook astral-sh/uv-pre-commit to v0.9.30 (#204)
- *(deps)* Update dependency astral-sh/uv to v0.9.30 (#202)
- *(deps)* Update ghcr.io/astral-sh/uv docker tag to v0.9.30 (#203)

### Other Changes
- Update README.md
- Implement template-centric bundle support for rhiza
- Fix linting issues in bundle implementation
- Update test to expect TypeError for type validation
- Sync
- Delete book/marimo/.gitkeep
- Update rhiza-hooks version to v0.1.4 (#209)
- Disable Rhiza config validation step (#211)
- Modify template inclusion and exclusion lists (#210)
- Bump version 0.9.1 → 0.10.0

## [0.9.1] - 2026-02-02

### Dependencies
- *(deps)* Lock file maintenance (#179)
- *(deps)* Update pre-commit hook pycqa/bandit to v1.9.3 (#182)
- *(deps)* Lock file maintenance (#183)
- *(deps)* Update actions/attest-build-provenance action to v3 (#184)
- *(deps)* Update pre-commit hook astral-sh/ruff-pre-commit to v0.14.14 (#181)
- *(deps)* Lock file maintenance (#185)
- *(deps)* Lock file maintenance (#191)
- *(deps)* Lock file maintenance (#197)

### Maintenance
- Sync with rhiza (#180)
- Import rhiza templates (#186)
- Update via rhiza (#192)
- Update via rhiza (#198)

### Other Changes
- Add deptry package_module_name_map entries to silence assumption warnings (#178)
- Achieve 100% statement coverage (#188)
- Add doctests to resolve test_docstrings skip (#190)
- Suppress stack traces in materialize command for expected git errors (#169)
- Bump version 0.9.0 → 0.9.1

## [0.9.0] - 2026-01-18

### Dependencies
- *(deps)* Lock file maintenance (#163)

### Maintenance
- Update via rhiza (#164)

### Other Changes
- Update documentation to reference .rhiza/template.yml instead of legacy paths (#166)
- Delete .rhiza.env (#167)
- Add --template-repository and --template-branch options to rhiza init (#173)
- Sync (#176)
- Generate structured PR descriptions for rhiza sync operations and add `rhiza summarise` CLI command (#171)
- Bump version 0.8.8 → 0.9.0

## [0.8.8] - 2026-01-11

### Other Changes
- Template exclude by default (#162)
- Bump version 0.8.7 → 0.8.8

## [0.8.7] - 2026-01-11

### Bug Fixes
- Handle multi-line YAML strings in include/exclude fields (#153)

### Dependencies
- *(deps)* Lock file maintenance (#151)

### Maintenance
- Update via rhiza (#150)
- Update via rhiza (#152)
- Import rhiza templates (#155)
- Import rhiza templates (#156)

### Other Changes
- Sync
- Update template + make sync (#159)
- Git commit -m "chore: import rhiza templates"
- Bump version 0.8.6 → 0.8.7

## [0.8.6] - 2026-01-03

### Other Changes
- Update dependency groups and optional dependencies (#149)

## [0.8.5] - 2026-01-03

### Other Changes
- Requirement files
- Remove optional dependencies
- Dependencies
- Force correct tools version (#148)

## [0.8.4] - 2026-01-01

### Dependencies
- *(deps)* Lock file maintenance (#122)

### Maintenance
- Update via rhiza (#123)

### Other Changes
- Rhiza tools plugin (#124)
- Reference logo and center (#125)
- Add CodeFactor badge to README
- Fix PATH manipulation vulnerability in git subprocess calls across entire codebase (#127)
- Refactor commands to reduce cyclomatic complexity (#129)
- Assign implementation of the UI issue to GitHub Copilot.
- Add Rhiza UI: Terminal-based multi-repository manager with Textual (#132)
- Python version
- Rhiza
- Rhiza.env
- Import python-dotenv
- Rhiza
- Delete .github/workflows/rhiza_docker.yml
- Delete .github/workflows/rhiza_devcontainer.yml
- Update template.yml to include and exclude workflows
- Delete .github/dependabot.yml
- [WIP] Update README.md with downloads and coverage percentage (#136)
- Remove ui (#140)
- Remove RHIZA_UI.md
- Revisit README
- Achieve 100% test coverage (#142)
- 143 remove all traces of UI (#145)

## [0.8.3] - 2025-12-27

### Other Changes
- Add platform selection prompt to rhiza init (#121)

## [0.8.2] - 2025-12-27

### Other Changes
- Add .rhiza folder to default template inclusion
- Fmt

## [0.8.1] - 2025-12-26

### Other Changes
- Replace init with validate in materialize command (#117)
- Ensure .rhiza folder is included in template.yml during migration (#119)

## [0.8.0] - 2025-12-26

### Other Changes
- Add src, tests, and pyproject.toml validation to validate command (#106)
- Achieve 100% test coverage (#111)
- Add uninstall command to remove Rhiza-managed files (#109)
- Add migrate command and update existing commands for .rhiza folder structure (#113)

## [0.7.2] - 2025-12-24

### Other Changes
- Revise GETTING_STARTED.md for clarity and detail (#99)
- Delete .github/workflows/structure.yml
- Fix init (#100)
- Improve init (#101)
- Blank lines at end (#102)

## [0.7.1] - 2025-12-24

### Bug Fixes
- Fixing init

## [0.7.0] - 2025-12-24

### New Features
- Auto-cleanup orphaned files during materialize (#95)

### Other Changes
- Rhiza notebook
- Rhiza notebook

## [0.6.1] - 2025-12-23

### Other Changes
- More init
- Fmt
- Add Getting Started guide with uvx-first approach and enhanced init command (#89)
- Makefiles
- Add comprehensive inline comments and debug logging to command modules (#91)

## [0.6.0] - 2025-12-23

### Documentation
- Add uvx installation and update instructions (#85)

### Maintenance
- Testing issue with security?

### Other Changes
- Rhiza
- Move template into rhiza directory and update validate (#79)
- Achieve 100% test coverage (#83)
- Forgiving validate
- Fmt
- Fmt
- Achieve 100% test coverage (#87)

## [0.5.6] - 2025-12-19

### Other Changes
- Fix git subprocess hanging by disabling credential prompts (#70)
- Add welcome command (#72)

## [0.5.5] - 2025-12-18

### Other Changes
- Hide expand_paths better (#66)
- Fix materialize command hanging on sparse checkout operations (#68)

## [0.5.4] - 2025-12-18

### Other Changes
- [WIP] Add support for Gitlab users (#48)
- [WIP] Add tests to achieve 100% coverage (#54)
- Fix misleading command references and expand docstrings with comprehensive documentation (#52)
- [WIP] Fix weird alignment of comments in help output (#56)
- Better display of comments?
- Add companion page URL to CLI help following Typer pattern (#58)
- [WIP] Enforce empty lines before examples in comments (#60)
- Better comments
- Fmt
- Empty lines for better display
- [WIP] Add branch option to materialize changes (#62)
- Markdown for pdoc?
- Markdown for pdoc?
- Markdown for pdoc?
- Fmt
- Fmt
- Fmt
- Add sym2 workflow for rhiza template materialization from update_rhiza branch (#64)

## [0.5.3] - 2025-12-18

### Bug Fixes
- Fixing tests validation
- Fixing tests

### Other Changes
- Add --version flag to rhiza CLI (#46)

## [0.5.2] - 2025-12-18

### Other Changes
- Don't delete the unused branch?
- Materialize with rhiza history
- Rhiza.history

## [0.5.1] - 2025-12-17

### Bug Fixes
- *(deps)* Update dependency pre-commit to v4.5.1 (#31)

### Documentation
- Docs

### Other Changes
- Add PyPI badge and link to README (#35)
- Add downloads badge to README (#36)
- Add coverage badge linking to companion book (#38)
- Convert docstrings from NumPy to Google style for pdoc compatibility (#40)
- [WIP] Add documentation for cli.py and command explanations (#42)
- Fmt
- Fmt
- Delete .github/scripts/sync.sh
- Create .rhiza.history file to track template-managed files (#44)

## [0.5.0] - 2025-12-17

### Other Changes
- Add rhiza init command for template.yml initialization (#17)
- Remove hello command from CLI (#12)
- Add rhiza validate command for authoritative template.yml validation (#10)
- Add GitHub Copilot instructions file (#22)
- Add RhizaTemplate dataclass to eliminate repeated YAML parsing (#20)
- Achieve 100% test coverage (#24)
- Add comprehensive CLI documentation following industry standards (#27)
- Enhance Copilot instructions with security, error handling, and troubleshooting (#29)

## [0.4.0] - 2025-12-16

### Maintenance
- Sync template files (#7)

### Other Changes
- Initial commit
- Init branch (#1)
- Update sync.yml (#6)
- Bump version from 0.2.0 to 0.4.0

<!-- generated by git-cliff -->
