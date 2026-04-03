# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.1] - 2026-04-04

### Changed
- Updated GUI list presentation so date-based overview, daily analysis, and raw message lists show newest entries first.
- Kept the newest-first ordering scoped to display/viewmodel output so export dataset ordering remains unchanged.

### Tests
- Added viewmodel coverage to verify newest-first ordering for day rows and raw message rows.

## [0.1.0] - 2026-03-27

### Added
- Added broader bundled pricing coverage in `opencode_token_app/prices.json`.
- Added currency-aware estimated cost totals to exported datasets and CSV outputs.
- Added formal project metadata and editable-install support via `pyproject.toml`.
- Added a formal MIT `LICENSE`, `CHANGELOG.md`, and `CONTRIBUTING.md`.
- Added structured engineering documentation under `docs/` for architecture, development, and release workflows.

### Changed
- Refined the GUI overview and raw-message browsing flow, including better display/viewmodel coverage and pagination-oriented behavior.
- Reworked pricing/export flows so mixed-currency estimated costs are preserved as per-currency totals instead of being merged incorrectly.
- Rewrote the root `README.md` to document installation, GUI/CLI usage, repository structure, and maintenance expectations.
- Moved Windows helper scripts into `scripts/` to separate maintainer tooling from application code.
- Clarified release boundaries with `.gitignore` for local/generated files and `.gitattributes` for archive-time exclusions.

### Improved
- Consolidated local-only history into a cleaner maintenance baseline.
- Preserved source, tests, and the authoritative PyInstaller spec while removing process-heavy planning docs from the trusted baseline.
- Kept the repository buildable and testable after the baseline rewrite: pytest, editable install, and Windows executable build all validate successfully.
