## [0.17.6] - 2026-06-08

### 💼 Other

- Bump version 0.17.5 → 0.17.6

### ⚙️ Miscellaneous Tasks

- Update CHANGELOG.md for v0.17.5 [skip ci]
- Update rhiza to v0.18.8 (#517)
## [0.17.5] - 2026-05-30

### 💼 Other

- Bump version 0.17.4 → 0.17.5

### ⚙️ Miscellaneous Tasks

- Update CHANGELOG.md for v0.17.4 [skip ci]
- Remove redundant trailing newline in __init__.py.jinja2 template
- Remove unused pyproject.toml.template
## [0.17.4] - 2026-05-30

### 🐛 Bug Fixes

- Preserve trailing newlines in Jinja2-rendered files

### 💼 Other

- Bump version 0.17.3 → 0.17.4

### ⚙️ Miscellaneous Tasks

- Update CHANGELOG.md for v0.17.3 [skip ci]
## [0.17.3] - 2026-05-30

### 🚀 Features

- *(init)* Generate mkdocs.yml with host-aware URLs

### 💼 Other

- Bump version 0.17.2 → 0.17.3

### ⚙️ Miscellaneous Tasks

- Update CHANGELOG.md for v0.17.2 [skip ci]
## [0.17.2] - 2026-05-30

### 🚀 Features

- *(init)* Enrich generated pyproject.toml and run uv lock

### 💼 Other

- Bump version 0.17.1 → 0.17.2

### ⚙️ Miscellaneous Tasks

- Update CHANGELOG.md for v0.17.1 [skip ci]
## [0.17.1] - 2026-05-30

### 🚀 Features

- *(init)* Fail early when target is not a git repository

### 💼 Other

- Bump version 0.17.0 → 0.17.1

### ⚙️ Miscellaneous Tasks

- Update CHANGELOG.md for v0.17.0 [skip ci]
## [0.17.0] - 2026-05-30

### 🚀 Features

- Improve rhiza init scaffolding (pyproject.toml, Makefile, template.yml)
- *(init)* Resolve latest tag from template repo instead of pinning to main
- *(init)* Auto-detect git host from origin remote URL

### 🐛 Bug Fixes

- *(init)* Hide empty default brackets in template repo prompt
- *(init)* Default template repo selection to [1] instead of []

### 💼 Other

- Bump version 0.16.1 → 0.17.0

### ⚙️ Miscellaneous Tasks

- Update CHANGELOG.md for v0.16.1 [skip ci]
- Update rhiza to v0.15.2 (#508)
- Update rhiza to v0.15.3 (#509)
- Update rhiza to v0.17.0 (#510)
- Update rhiza to v0.18.4 (#511)
## [0.16.1] - 2026-05-25

### 🐛 Bug Fixes

- Follow symlinks when scanning bundle directories

### 💼 Other

- Bump version 0.16.0 → 0.16.1

### ⚙️ Miscellaneous Tasks

- Update CHANGELOG.md for v0.16.0 [skip ci]
## [0.16.0] - 2026-05-25

### 🚀 Features

- Support directory-based bundle resolution (no explicit files) (#506)

### 💼 Other

- Bump version 0.15.0 → 0.16.0

### ⚙️ Miscellaneous Tasks

- Update CHANGELOG.md for v0.15.0 [skip ci]
## [0.15.0] - 2026-05-25

### 🚀 Features

- Add path remapping support for bundle file entries (#504)

### 🐛 Bug Fixes

- Point coverage badge at GitHub Pages URL

### 💼 Other

- Bump version 0.14.1 → 0.15.0

### ⚙️ Miscellaneous Tasks

- Update CHANGELOG.md for v0.14.1 [skip ci]
- Bump rhiza template to v0.11.0 (#503)
## [0.14.1] - 2026-05-24

### 🚀 Features

- Change profile from scalar to list (profiles)

### 💼 Other

- Bump version 0.14.0 → 0.14.1

### ⚙️ Miscellaneous Tasks

- Update CHANGELOG.md for v0.14.0 [skip ci]
## [0.14.0] - 2026-05-24

### 🚀 Features

- Add profile support to template configuration (#502)

### 💼 Other

- Bump version 0.13.6 → 0.14.0

### ⚙️ Miscellaneous Tasks

- Update CHANGELOG.md for v0.13.6 [skip ci]
## [0.13.6] - 2026-05-23

### 🐛 Bug Fixes

- *(init)* Normalise package name in generated test file import (#489)
- *(docs)* Fix index page rendering and update nav

### 💼 Other

- Bump version 0.13.5 → 0.13.6

### 🧪 Testing

- Bring test coverage to 100%

### ⚙️ Miscellaneous Tasks

- Update via rhiza (#496)
- Sync rhiza template to v0.10.9 (#501)
- *(docs)* Comment out theme and markdown_extensions in mkdocs.yml
## [0.13.5] - 2026-05-02

### 🐛 Bug Fixes

- *(docs)* Set docs_dir: docs to avoid site_dir inside docs_dir error
- *(book)* Remove unsupported -d flag from zensical build
- *(summarise)* Use template.lock/RhizaTemplate model for template info; add output customisation flags (#470)
- Skip template.lock write when no effective changes after sync (#478)
- Resolve broken links in README.md (weekly link-check CI) (#486)

### 💼 Other

- Add mkdocs.yml and fix book target when mkdocs is skipped
- Bump version 0.13.4 → 0.13.5

### 📚 Documentation

- Simplify mkdocs.yml via INHERIT from docs/mkdocs-base.yml

### ⚙️ Miscellaneous Tasks

- Sync rhiza template to v0.9.5 (#476)
## [0.13.4] - 2026-04-02

### 💼 Other

- Bump version 0.13.3 → 0.13.4
## [0.13.3] - 2026-03-22

### 🐛 Bug Fixes

- Replace broken coverage badge with direct gh-pages SVG (#454)

### 💼 Other

- Bump version 0.13.2 → 0.13.3
## [0.13.2] - 2026-03-18

### 🐛 Bug Fixes

- Derive template-bundles.yml path from --path-to-template directory (#449)

### ⚙️ Miscellaneous Tasks

- Bump 0.13.1 -> 0.13.2 (#450)
## [0.13.1] - 2026-03-13

### 🚀 Features

- Add --path-to-template option to rhiza validate and rhiza init (#442)

### 💼 Other

- Bump version 0.13.0 → 0.13.1
## [0.13.0] - 2026-03-13

### 🚀 Features

- *(sync)* Custom bundle path + hybrid mode merge (#440)

### 💼 Other

- Bump version 0.12.2 → 0.13.0
## [0.12.2] - 2026-03-12

### 💼 Other

- Bump version 0.12.1 → 0.12.2
## [0.12.1] - 2026-03-09

### 🐛 Bug Fixes

- *(models)* Make `TemplateLock` immutable with `@dataclass(frozen=Tr… (#426)

### 💼 Other

- Template.lock include field contains resolved paths instead of original config values (#424)
- Bump version 0.12.0 → 0.12.1

### 🚜 Refactor

- Slim RhizaTemplate to a pure data class (#427)
- Eliminate duplicated code patterns across command modules (#429)
## [0.12.0] - 2026-03-08

### 🐛 Bug Fixes

- *(models)* Set default values for `template_repository` and `template_branch` fields

### 💼 Other

- Remove mypy configuration from pyproject.toml
- Migrate template helpers from `_sync_helpers` to `RhizaTemplate` private methods (#383)
- Bump version 0.11.12 → 0.12.0

### 🚜 Refactor

- *(sync)* Remove unnecessary type casts for `template_repositor… (#395)
- Split monolithic models.py into a models/ subpackage (#397)
- Consolidate _log_git_stderr_errors, fix docstring, logging, and exception narrowing (#401)
- Consolidate `_log_git_stderr_errors` into `models/_git_utils.py` (#409)
- *(sync)* Remove redundant helper functions, consolidate `_sync… (#417)
- *(models)* Add `TYPE_CHECKING` imports for TemplateLock and Rh… (#418)
- *(tests)* Replace `_read_lock` calls with `TemplateLock.read_s… (#419)
- *(tests)* Move model tests into tests/test_models/ folder
- *(tests)* Remove unnecessary __init__.py from test_models
- *(tests)* Remove `test_bundle_resolver.py` and relocate `test_git_utils.py` into `test_models/`

### 🧪 Testing

- *(bundle)* Add coverage for RhizaBundles.config property to reach 100%
- *(models)* Add comprehensive round-trip, E2E, and Hypothesis tests
- *(models)* Increase test coverage to 100%
## [0.11.12] - 2026-03-07

### 🐛 Bug Fixes

- Restore template-managed files missing from target during sync (#375)

### 💼 Other

- Bump version 0.11.11 → 0.11.12
## [0.11.11] - 2026-03-07

### 💼 Other

- Bump version 0.11.10 → 0.11.11
## [0.11.10] - 2026-03-07

### 💼 Other

- Bump version 0.11.9 → 0.11.10
## [0.11.9] - 2026-03-07

### 💼 Other

- Bump version 0.11.8 → 0.11.9
## [0.11.8] - 2026-03-07

### 🚀 Features

- Interactive template repository picker in `rhiza init` (#338)

### 🐛 Bug Fixes

- Persist and populate files list in template.lock to enable orphan deletion (#342)

### 💼 Other

- Bump version 0.11.7 → 0.11.8

### 🚜 Refactor

- *(tests)* Reduce test_uninstall.py from 621 to 340 LOC (#347)
## [0.11.7] - 2026-03-02

### 💼 Other

- Bump version 0.11.6 → 0.11.7

### 🧪 Testing

- Increase coverage to 100% (#336)
## [0.11.6] - 2026-02-27

### 🐛 Bug Fixes

- Fall back to git merge-file when apply -3 lacks blob objects

### 💼 Other

- Bump version 0.11.5 → 0.11.6

### ⚙️ Miscellaneous Tasks

- Sync template to 0404d2f35361 (v0.8.5)
## [0.11.5] - 2026-02-27

### 🚀 Features

- Add `rhiza status` command (#317)
- *(sync)* Concurrency-safe lock file I/O with fcntl + atomic rename (#315)

### 🐛 Bug Fixes

- Loosen PyYAML pin and migrate materialize to sync (#303)
- Migrate rhiza_sync.yml from deprecated `materialize --force` to `rhiza sync` (#305)

### 💼 Other

- Actually remove cruft — inline get_diff and drop dependency (#297)
- Bump version 0.11.4-rc.6 → 0.11.5

### 📚 Documentation

- Reorder REPOSITORY_ANALYSIS.md newest-first
- Remove PyYAML exact-pin weakness from latest analysis entries
- Add ADR directory with two initial architecture decision records (#309)
- Add ADR-0003 for lock file concurrency (#323)
- Update Third Analysis to 9.5/10 reflecting PRs #315–#323
- Correct misleading version comparison in REPOSITORY_ANALYSIS
- Add authentication guide for private template repositories (#325)
## [0.11.4-rc.6] - 2026-02-26

### 🚀 Features

- Add `synced_at` and `strategy` metadata to `TemplateLock` (#296)

### 🐛 Bug Fixes

- Make `repository` and `ref` the canonical YAML keys (#292)

### 💼 Other

- Bump version 0.11.4-rc.5 → 0.11.4-rc.6
## [0.11.4-rc.5] - 2026-02-26

### 💼 Other

- Bump version 0.11.4-rc.3 → 0.11.4-rc.4
- Bump version 0.11.4-rc.4 → 0.11.4-rc.5
## [0.11.4-rc.3] - 2026-02-26

### 💼 Other

- Template.lock include field reflects template.yml verbatim (#282)
- Bump version 0.11.4-rc.2 → 0.11.4-rc.3
## [0.11.4-rc.2] - 2026-02-26

### 💼 Other

- Bump version 0.11.4-rc.1 → 0.11.4-rc.2
## [0.11.4-rc.1] - 2026-02-26

### 🚀 Features

- Delete orphaned files during sync when template.yml changes (#271)

### 💼 Other

- Bump version 0.11.3 → 0.11.4-rc.1
## [0.11.3] - 2026-02-24

### 💼 Other

- Bump version 0.11.2 → 0.11.3
## [0.11.2] - 2026-02-24

### 💼 Other

- Bump version 0.11.1-beta.2 → 0.11.2
## [0.11.1-beta.2] - 2026-02-20

### 💼 Other

- Bump version 0.11.1-beta.1 → 0.11.1-beta.2
## [0.11.1-beta.1] - 2026-02-17

### 💼 Other

- Bump version 0.11.0 → 0.11.1-beta.1
- Bump version 0.11.0 → 0.11.1-beta.1
- Bump version 0.11.0 → 0.11.1-beta.1

### 🚜 Refactor

- Replace custom sync with cruft-based diff/merge (#244)
## [0.11.0] - 2026-02-13

### 💼 Other

- Bump version 0.10.4 → 0.11.0
## [0.10.4] - 2026-02-12

### 💼 Other

- Bump version 0.10.3 → 0.10.4
## [0.10.3] - 2026-02-07

### 💼 Other

- Bump version 0.10.2 → 0.10.3
## [0.10.2] - 2026-02-05

### 💼 Other

- Bump version 0.10.1 → 0.10.2
## [0.10.1] - 2026-02-05

### 💼 Other

- Bump version 0.10.0 → 0.10.1
## [0.10.0] - 2026-02-05

### 💼 Other

- Bump version 0.9.1 → 0.10.0
## [0.9.1] - 2026-02-02

### 💼 Other

- Bump version 0.9.0 → 0.9.1

### ⚙️ Miscellaneous Tasks

- Sync with rhiza (#180)
- Import rhiza templates (#186)
- Update via rhiza (#192)
- Update via rhiza (#198)
## [0.9.0] - 2026-01-18

### 💼 Other

- Bump version 0.8.8 → 0.9.0

### ⚙️ Miscellaneous Tasks

- Update via rhiza (#164)
## [0.8.8] - 2026-01-11

### 💼 Other

- Bump version 0.8.7 → 0.8.8
## [0.8.7] - 2026-01-11

### 🐛 Bug Fixes

- Handle multi-line YAML strings in include/exclude fields (#153)

### 💼 Other

- Bump version 0.8.6 → 0.8.7

### ⚙️ Miscellaneous Tasks

- Update via rhiza (#150)
- Update via rhiza (#152)
- Import rhiza templates (#155)
- Import rhiza templates (#156)
## [0.8.6] - 2026-01-03

### ⚙️ Miscellaneous Tasks

- Bump version to 0.8.6
## [0.8.5] - 2026-01-03

### ⚙️ Miscellaneous Tasks

- Bump version to 0.8.5
## [0.8.4] - 2026-01-01

### ⚙️ Miscellaneous Tasks

- Update via rhiza (#123)
- Bump version to 0.8.4
## [0.8.3] - 2025-12-27

### ⚙️ Miscellaneous Tasks

- Bump version to 0.8.3
## [0.8.2] - 2025-12-27

### ⚙️ Miscellaneous Tasks

- Bump version to 0.8.2
## [0.8.1] - 2025-12-26

### ⚙️ Miscellaneous Tasks

- Bump version to 0.8.1
## [0.8.0] - 2025-12-26

### ⚙️ Miscellaneous Tasks

- Bump version to 0.8.0
## [0.7.3] - 2025-12-24

### ⚙️ Miscellaneous Tasks

- Bump version to 0.7.3
## [0.7.2] - 2025-12-24

### ⚙️ Miscellaneous Tasks

- Bump version to 0.7.2
## [0.7.1] - 2025-12-24

### ⚙️ Miscellaneous Tasks

- Bump version to 0.7.1
## [0.7.0] - 2025-12-24

### 🚀 Features

- Auto-cleanup orphaned files during materialize (#95)

### ⚙️ Miscellaneous Tasks

- Bump version to 0.7.0
## [0.6.1] - 2025-12-23

### ⚙️ Miscellaneous Tasks

- Bump version to 0.6.1
## [0.6.0] - 2025-12-23

### 📚 Documentation

- Add uvx installation and update instructions (#85)

### ⚙️ Miscellaneous Tasks

- Bump version to 0.6.0
## [0.5.6] - 2025-12-19

### ⚙️ Miscellaneous Tasks

- Bump version to 0.5.6
## [0.5.5] - 2025-12-18

### ⚙️ Miscellaneous Tasks

- Bump version to 0.5.5
## [0.5.4] - 2025-12-18

### ⚙️ Miscellaneous Tasks

- Bump version to 0.5.4
## [0.5.3] - 2025-12-18

### ⚙️ Miscellaneous Tasks

- Bump version to 0.5.3
## [0.5.2] - 2025-12-18

### ⚙️ Miscellaneous Tasks

- Bump version to 0.5.2
## [0.5.1] - 2025-12-17

### 🐛 Bug Fixes

- *(deps)* Update dependency pre-commit to v4.5.1 (#31)

### ⚙️ Miscellaneous Tasks

- Bump version to 0.5.1
## [0.5.0] - 2025-12-17

### ⚙️ Miscellaneous Tasks

- Bump version to 0.5.0
## [0.4.0] - 2025-12-16

### ⚙️ Miscellaneous Tasks

- Sync template files (#7)
