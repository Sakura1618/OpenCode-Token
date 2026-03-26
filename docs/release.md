# Release

## Source baseline

The maintainable source baseline consists of:

- `opencode_token_app/`
- `opencode_token_gui.py`
- `export_opencode_tokens.py`
- `opencode_token_gui.spec`
- `pyproject.toml`
- `README.md`, `LICENSE`, `CHANGELOG.md`
- `tests/`
- `docs/`

Generated outputs and maintainer-only scripts are excluded from release archives through `.gitattributes` and `.gitignore`.

## Build a Windows executable

```bash
scripts\build.bat
```

This produces:

- `build/opencode_token_gui.exe`

## Validate before release

1. Run `python -m pytest`
2. Build the executable with `scripts\build.bat`
3. Verify the GUI launches and the CLI export still writes all CSV outputs
4. Update `CHANGELOG.md` for the release

## Archive behavior

Release archives generated through `git archive` exclude:

- `tests/`
- `docs/`
- `build/`
- `token_export/`
- `scripts/`

If you manually zip the working tree, you must exclude those paths yourself.
