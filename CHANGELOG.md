# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-03-27

### Added
- Established a maintainable repository baseline with packaging metadata via `pyproject.toml`.
- Added a formal MIT `LICENSE` and this `CHANGELOG` for legal and release clarity.
- Added structured engineering documentation under `docs/` for architecture, development, and release workflows.

### Changed
- Rewrote the root `README.md` to document installation, GUI/CLI usage, repository structure, and maintenance expectations.
- Moved Windows helper scripts into `scripts/` to separate maintainer tooling from application code.
- Clarified release boundaries with `.gitignore` and `.gitattributes`.

### Improved
- Consolidated local-only history into a cleaner maintenance baseline.
- Preserved source, tests, and authoritative build spec while removing process-heavy planning docs from the trusted baseline.
