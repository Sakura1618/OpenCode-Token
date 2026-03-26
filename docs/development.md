# Development

## Setup

Install the project in editable mode with development dependencies:

```bash
python -m pip install -e .[dev]
```

## Running locally

GUI:

```bash
python opencode_token_gui.py
```

CLI export:

```bash
python export_opencode_tokens.py <path-to-opencode.db> [output-dir]
```

Windows convenience scripts are available under `scripts/`.

## Testing

Run the full suite:

```bash
python -m pytest
```

Current tests cover:

- data loading and aggregation
- pricing and override behavior
- GUI/viewmodel formatting and chart helpers

## Data and artifact hygiene

- Do not commit generated exports from `token_export/`.
- Do not commit build output from `build/`.
- Keep local pricing overrides in `prices.local.json` only.
- Treat `docs/` as intentional repository documentation, not scratch space.
