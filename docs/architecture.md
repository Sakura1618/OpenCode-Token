# Architecture

## Overview

OpenCode Token is a Python desktop utility for analyzing `opencode.db` usage data and exporting priced token reports.

The repository is organized around a small source package plus two root entrypoints:

- `opencode_token_gui.py`: launches the Tkinter desktop application
- `export_opencode_tokens.py`: exports CSV datasets from the same data pipeline

## Module responsibilities

### `opencode_token_app/data_loader.py`
- Reads OpenCode SQLite data
- Normalizes message rows
- Aggregates summary, model, session, and day datasets

### `opencode_token_app/pricing.py`
- Loads bundled and local price maps
- Applies flat and session-tiered pricing
- Computes aggregate estimated-cost overlays, including mixed-currency totals

### `opencode_token_app/viewmodels.py`
- Formats domain data for GUI presentation
- Converts token counts and cost totals into human-readable display values

### `opencode_token_app/gui.py`
- Coordinates Tkinter widgets, filtering, and pagination
- Connects data loading, view models, and charts into the application shell

### `opencode_token_app/charts.py`
- Wraps Matplotlib figure setup and plotting helpers

### `opencode_token_app/exporter.py`
- Writes normalized CSV exports for summary and detailed datasets

## Build and release assets

- `opencode_token_gui.spec` is the authoritative PyInstaller spec.
- `scripts/build.bat` is a maintainer convenience wrapper around the PyInstaller build command.

Generated artifacts under `build/` and `token_export/` are not part of the source baseline.
