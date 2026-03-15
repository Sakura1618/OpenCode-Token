# GUI Chart Rendering Fix Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Tkinter analytics UI render real charts for overview, model, day, and session tabs after loading data, with stable empty-state and failure-isolation behavior.

**Architecture:** Keep chart drawing inside `opencode_token_app/charts.py` and chart selection/refresh orchestration inside `opencode_token_app/gui.py`. Reuse existing viewmodel rows as chart inputs, store chart references during UI construction, and refresh each chart independently after table population.

**Tech Stack:** Python, Tkinter/ttk, matplotlib, pytest

---

## File Map

- Modify: `opencode_token_app/charts.py`
  - Add reusable helpers for clearing figures, drawing empty states, drawing line charts, drawing horizontal bar charts, and drawing pie charts.
- Modify: `opencode_token_app/gui.py`
  - Persist chart figures/canvases, add chart refresh orchestration, isolate chart errors from table population, and wire loaded viewmodels into chart rendering.
- Modify: `tests/test_gui_viewmodels.py`
  - Add regression tests for chart helper no-op/empty behavior and GUI chart refresh coordination/failure isolation.
- Reference: `docs/superpowers/specs/2026-03-16-gui-chart-rendering-fix-design.md`
  - Source of approved behavior, ordering rules, and scope boundaries.

## Chunk 1: Chart Helper Coverage And Implementation

### Task 1: Add failing tests for chart helper behavior

**Files:**
- Modify: `tests/test_gui_viewmodels.py`
- Modify: `opencode_token_app/charts.py`

- [ ] **Step 1: Write the failing tests**

Add tests that exercise deterministic helper behavior without opening a real GUI window:

```python
from opencode_token_app import charts
import pytest


def test_create_figure_returns_none_when_matplotlib_unavailable(monkeypatch):
    monkeypatch.setattr(charts, "Figure", None)
    assert charts.create_figure() is None


@pytest.mark.skipif(charts.Figure is None, reason="matplotlib unavailable")
def test_line_chart_renders_empty_state_when_no_values():
    figure = charts.create_figure()

    charts.plot_line_chart(figure, title="Daily Tokens", labels=[], values=[])

    axis = figure.axes[0]
    assert axis.get_title() == "Daily Tokens"
    assert axis.texts[0].get_text() == "No data"


@pytest.mark.skipif(charts.Figure is None, reason="matplotlib unavailable")
def test_bar_chart_uses_expected_labels_and_values():
    figure = charts.create_figure()

    charts.plot_horizontal_bar_chart(
        figure,
        title="Top Models",
        labels=["openai/gpt-4.1-mini", "openai/o3"],
        values=[100, 80],
    )

    axis = figure.axes[0]
    assert axis.get_title() == "Top Models"
    assert [tick.get_text() for tick in axis.get_yticklabels()] == ["openai/gpt-4.1-mini", "openai/o3"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_gui_viewmodels.py -k chart -v`
Expected: FAIL because chart helper functions like `plot_line_chart` do not exist yet.

- [ ] **Step 3: Write the minimal implementation**

Add focused helpers to `opencode_token_app/charts.py`:

```python
def clear_figure(figure):
    if figure is None:
        return None
    figure.clear()
    return figure.add_subplot(111)


def show_empty_state(axis, title, message="No data"):
    axis.set_title(title)
    axis.text(0.5, 0.5, message, ha="center", va="center", transform=axis.transAxes)
    axis.set_xticks([])
    axis.set_yticks([])


def plot_line_chart(figure, title, labels, values, ylabel=""):
    axis = clear_figure(figure)
    if axis is None:
        return
    if not labels or not values:
        show_empty_state(axis, title)
        return
    axis.plot(labels, values, marker="o")
    axis.set_title(title)
    if ylabel:
        axis.set_ylabel(ylabel)
    figure.tight_layout()
```

Mirror the same style for horizontal bar and pie chart helpers, always handling `figure is None` and empty datasets safely.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_gui_viewmodels.py -k chart -v`
Expected: PASS for the new chart helper tests.

- [ ] **Step 5: Commit**

```bash
git add tests/test_gui_viewmodels.py opencode_token_app/charts.py
git commit -m "test: cover chart helper rendering states"
```

### Task 2: Refine chart helper output for GUI readability

**Files:**
- Modify: `opencode_token_app/charts.py`
- Test: `tests/test_gui_viewmodels.py`

- [ ] **Step 1: Write the failing test**

Add a test that confirms the helper keeps charts readable and deterministic for the intended GUI usage:

```python
@pytest.mark.skipif(charts.Figure is None, reason="matplotlib unavailable")
def test_pie_chart_sets_labels_for_token_composition():
    figure = charts.create_figure()

    charts.plot_pie_chart(
        figure,
        title="Token Composition",
        labels=["Input", "Output", "Reasoning"],
        values=[40, 50, 10],
    )

    axis = figure.axes[0]
    assert axis.get_title() == "Token Composition"
    assert len(axis.texts) >= 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_gui_viewmodels.py::test_pie_chart_sets_labels_for_token_composition -v`
Expected: FAIL until `plot_pie_chart` exists and draws the chart.

- [ ] **Step 3: Write the minimal implementation**

Implement `plot_pie_chart` in `opencode_token_app/charts.py` using the same guard pattern as the other helpers:

```python
def plot_pie_chart(figure, title, labels, values):
    axis = clear_figure(figure)
    if axis is None:
        return
    filtered = [(label, value) for label, value in zip(labels, values) if value]
    if not filtered:
        show_empty_state(axis, title)
        return
    filtered_labels, filtered_values = zip(*filtered)
    axis.pie(filtered_values, labels=filtered_labels, autopct="%1.0f%%")
    axis.set_title(title)
    figure.tight_layout()
```

- [ ] **Step 4: Run relevant tests to verify they pass**

Run: `pytest tests/test_gui_viewmodels.py -k chart -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_gui_viewmodels.py opencode_token_app/charts.py
git commit -m "feat: add reusable gui chart plotters"
```

## Chunk 2: GUI Chart Refresh Wiring

### Task 3: Add failing tests for GUI chart refresh orchestration

**Files:**
- Modify: `tests/test_gui_viewmodels.py`
- Modify: `opencode_token_app/gui.py`

- [ ] **Step 1: Write the failing tests**

Add small unit-style tests for chart refresh logic using fake treeviews/canvases or monkeypatched chart functions:

```python
from types import SimpleNamespace

from opencode_token_app.gui import OpenCodeTokenApp


def test_populate_view_refreshes_tables_and_charts(monkeypatch):
    calls = []
    app = OpenCodeTokenApp.__new__(OpenCodeTokenApp)
    app.viewmodels = {
        "overview": {"cards": {"total_tokens": 100, "input_tokens": 40, "output_tokens": 50, "reasoning_tokens": 10}, "daily_rows": [{"day": "2024-03-09", "total_tokens": 100}]},
        "models": [{"provider": "openai", "model": "gpt-4.1-mini", "total_tokens": 100}],
        "days": [{"day": "2024-03-09", "total_tokens": 100}],
        "sessions": [{"session_id": "s1", "session_title": "Demo", "total_tokens": 100}],
        "raw_messages": [],
    }
    app.overview_card_labels = {"total_tokens": SimpleNamespace(configure=lambda **kwargs: None), "input_tokens": SimpleNamespace(configure=lambda **kwargs: None), "output_tokens": SimpleNamespace(configure=lambda **kwargs: None), "reasoning_tokens": SimpleNamespace(configure=lambda **kwargs: None)}
    app.overview_table = object()
    app.treeviews = {"models": object(), "days": object(), "sessions": object(), "raw_messages": object()}
    app._fill_tree = lambda tree, rows: calls.append((tree, rows))
    app._refresh_charts = lambda: calls.append("charts")

    app._populate_view()

    assert "charts" in calls
```

And a failure-isolation test:

```python
def test_refresh_charts_isolates_single_chart_failure(monkeypatch):
    app = OpenCodeTokenApp.__new__(OpenCodeTokenApp)
    calls = []
    app.status_var = SimpleNamespace(set=lambda value: calls.append(("status", value)))
    app._refresh_overview_charts = lambda: (_ for _ in ()).throw(RuntimeError("boom"))
    app._refresh_models_chart = lambda: calls.append("models")
    app._refresh_days_chart = lambda: calls.append("days")
    app._refresh_sessions_chart = lambda: calls.append("sessions")

    app._refresh_charts()

    assert "models" in calls
    assert "days" in calls
    assert "sessions" in calls
    assert any(item[0] == "status" for item in calls if isinstance(item, tuple))
```

The exact test double structure can stay simple, but it must prove table filling and chart refresh are no longer one inseparable failure path.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_gui_viewmodels.py -k refresh -v`
Expected: FAIL because `_refresh_charts` is not implemented or not called from `_populate_view()` yet.

- [ ] **Step 3: Write the minimal implementation**

Update `opencode_token_app/gui.py` to:

```python
def _populate_view(self):
    overview = self.viewmodels["overview"]
    ...
    self._fill_tree(...)
    self._refresh_charts()
```

Add explicit per-chart isolation inside `_refresh_charts()`:

```python
def _refresh_charts(self):
    for refresh in [
        self._refresh_overview_charts,
        self._refresh_models_chart,
        self._refresh_days_chart,
        self._refresh_sessions_chart,
    ]:
        try:
            refresh()
        except Exception as exc:
            self.status_var.set(f"Loaded with chart warning: {exc}")
```

Do not wrap `_populate_view()` in a single broad chart exception block; table population must finish before chart isolation logic runs.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_gui_viewmodels.py -k refresh -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_gui_viewmodels.py opencode_token_app/gui.py
git commit -m "test: cover gui chart refresh orchestration"
```

### Task 4: Persist chart references and render all tab charts

**Files:**
- Modify: `opencode_token_app/gui.py`
- Modify: `opencode_token_app/charts.py`
- Test: `tests/test_gui_viewmodels.py`

- [ ] **Step 1: Write the failing tests**

Add focused tests for the chart-input preparation logic. Prefer testing small helper methods added to `OpenCodeTokenApp` so the chart inputs are deterministic:

```python
def test_model_chart_rows_are_sorted_descending_and_trimmed_to_top_10():
    app = OpenCodeTokenApp.__new__(OpenCodeTokenApp)
    rows = [{"provider": "openai", "model": f"m{i}", "total_tokens": i} for i in range(1, 15)]

    labels, values = app._top_model_chart_data(rows)

    assert len(labels) == 10
    assert labels[0] == "openai/m14"
    assert values[0] == 14


def test_overview_top_model_chart_uses_descending_total_tokens():
    app = OpenCodeTokenApp.__new__(OpenCodeTokenApp)

    labels, values = app._top_model_chart_data([
        {"provider": "openai", "model": "m1", "total_tokens": 10},
        {"provider": "openai", "model": "m2", "total_tokens": 30},
        {"provider": "openai", "model": "m3", "total_tokens": 20},
    ])

    assert labels == ["openai/m2", "openai/m3", "openai/m1"]
    assert values == [30, 20, 10]


def test_session_chart_uses_session_id_when_title_missing():
    app = OpenCodeTokenApp.__new__(OpenCodeTokenApp)

    labels, values = app._top_session_chart_data([
        {"session_id": "s1", "session_title": "", "total_tokens": 7},
    ])

    assert labels == ["s1"]
    assert values == [7]


def test_day_chart_rows_are_sorted_ascending():
    app = OpenCodeTokenApp.__new__(OpenCodeTokenApp)

    labels, values = app._day_chart_data([
        {"day": "2024-03-10", "total_tokens": 20},
        {"day": "2024-03-09", "total_tokens": 10},
    ])

    assert labels == ["2024-03-09", "2024-03-10"]
    assert values == [10, 20]


def test_overview_composition_chart_uses_input_output_reasoning_cards():
    app = OpenCodeTokenApp.__new__(OpenCodeTokenApp)

    labels, values = app._overview_composition_chart_data({
        "input_tokens": 40,
        "output_tokens": 50,
        "reasoning_tokens": 10,
    })

    assert labels == ["Input", "Output", "Reasoning"]
    assert values == [40, 50, 10]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_gui_viewmodels.py -k "top_model_chart_data or overview_top_model_chart or session_chart or day_chart_rows_are_sorted_ascending or overview_composition_chart_uses_input_output_reasoning_cards" -v`
Expected: FAIL because the helper methods do not exist yet.

- [ ] **Step 3: Write the minimal implementation**

In `opencode_token_app/gui.py`:

- store chart references during `_build_overview_tab()` and `_build_analysis_tab()`
- add helpers such as `_register_chart`, `_refresh_charts`, `_refresh_overview_charts`, `_refresh_models_chart`, `_refresh_days_chart`, `_refresh_sessions_chart`
- add chart-data helpers:

```python
def _top_model_chart_data(self, rows):
    sorted_rows = sorted(rows, key=lambda row: row.get("total_tokens", 0) or 0, reverse=True)[:10]
    labels = []
    values = []
    for row in sorted_rows:
        provider = row.get("provider", "") or ""
        model = row.get("model", "") or ""
        if provider and model:
            labels.append(f"{provider}/{model}")
        else:
            labels.append(provider or model)
        values.append(row.get("total_tokens", 0) or 0)
    return labels, values
```

Add similar helpers for day rows and session rows, including ascending day ordering and `session_title` fallback to `session_id`.

Render with the new chart helpers in `opencode_token_app/charts.py` and call `canvas.draw()` after each successful refresh.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_gui_viewmodels.py -v`
Expected: PASS for new and existing GUI/viewmodel tests.

- [ ] **Step 5: Commit**

```bash
git add tests/test_gui_viewmodels.py opencode_token_app/gui.py opencode_token_app/charts.py
git commit -m "feat: render analytics charts in gui tabs"
```

## Chunk 3: End-to-End Verification

### Task 5: Verify the regression fix in the full test suite

**Files:**
- Test: `tests/test_gui_viewmodels.py`
- Test: `tests/test_data_loader.py`
- Test: `tests/test_pricing.py`

- [ ] **Step 1: Run the focused regression tests**

Run: `pytest tests/test_gui_viewmodels.py -v`
Expected: PASS.

- [ ] **Step 2: Run the broader test suite**

Run: `pytest -v`
Expected: PASS with no new failures.

- [ ] **Step 3: Perform a quick manual smoke check**

Run: `python opencode_token_gui.py`
Expected: GUI opens, loads a valid DB, and shows charts in `总览`, `模型分析`, `按日分析`, and `会话分析`.

- [ ] **Step 4: If smoke check reveals a chart-specific issue, add one regression test before fixing it**

Only add the smallest targeted test needed; do not bundle unrelated UI cleanup.

- [ ] **Step 5: Commit the verified fix**

```bash
git add opencode_token_app/charts.py opencode_token_app/gui.py tests/test_gui_viewmodels.py
git commit -m "fix: populate gui analytics charts after load"
```
