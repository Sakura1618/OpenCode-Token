# Contributing

## Development workflow

1. Create a feature branch from the current maintenance baseline.
2. Install development dependencies:

```bash
python -m pip install -e .[dev]
```

3. Run the test suite before every commit:

```bash
python -m pytest
```

4. If you change packaging or GUI startup behavior, also run the build smoke test:

```bash
scripts\build.bat
```

## Repository conventions

- Keep generated outputs out of version control: `build/`, `token_export/`, caches, and local price overrides.
- Treat `opencode_token_app/` as the authoritative source package.
- Keep tests in `tests/`, and update them in the same commit as behavioral changes.
- Update `README.md` for user-facing behavior changes and `CHANGELOG.md` for release-facing changes.

## Commit quality

- Use clear semantic commit messages such as `feat: ...`, `fix: ...`, or `chore: ...`.
- Avoid placeholder commits and checkpoint commits.
- Prefer small, reviewable commits that can be reverted independently.
