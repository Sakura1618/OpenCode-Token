# GUI Chart Rendering Fix Design

## Goal

Complete the Tkinter GUI chart area so the software analytics tabs render real charts after loading data instead of showing empty embedded canvases.

## Confirmed Decisions

- Keep the current `matplotlib` + `Tkinter` approach.
- Reuse the existing tab structure in `opencode_token_app/gui.py`.
- Fill all currently intended analytics charts, not just the overview tab.
- Prefer a small, maintainable fix over introducing a new chart data layer.

## Root Cause

`opencode_token_app/gui.py` creates `Figure` and `FigureCanvasTkAgg` instances during UI setup, but it never stores those chart objects in a way that supports later redraws and never sends loaded usage data into plotting code. As a result, the GUI shows chart containers with blank figures only.

## Approach

### Chart Ownership

- `opencode_token_app/charts.py` remains responsible for chart creation and low-level plotting helpers.
- `opencode_token_app/gui.py` remains responsible for choosing which dataset powers each chart and when charts refresh.
- `opencode_token_app/viewmodels.py` stays focused on table-friendly display data; no separate chart-specific viewmodel layer is introduced in this fix.

### Rendering Model

- Build each chart area once during tab construction.
- Store each chart's `figure` and `canvas` on the app instance so they can be refreshed after data load.
- Add a single refresh path triggered from `load_current_db()` after `self.viewmodels` is rebuilt.
- Each refresh helper clears the figure, draws the latest chart, and calls `canvas.draw()`.

## Per-Tab Chart Design

### `总览`

- Daily token trend: line chart using `overview["daily_rows"]` with rows sorted by `day` ascending, `day` on the x-axis, and `total_tokens` on the y-axis.
- Top models: horizontal bar chart using the highest-token rows from `viewmodels["models"]`, sorted by `total_tokens` descending before taking the top 10.
- Token composition: pie chart using overview card totals for `input_tokens`, `output_tokens`, and `reasoning_tokens`.

### `模型分析`

- Horizontal bar chart for top 10 models by `total_tokens` from `viewmodels["models"]`, sorted descending before slicing.
- Category label format: `provider/model` when both values are present, otherwise whichever non-empty field exists.

### `按日分析`

- Line chart for `total_tokens` by day from `viewmodels["days"]`, sorted by `day` ascending.

### `会话分析`

- Horizontal bar chart for top 10 sessions by `total_tokens` from `viewmodels["sessions"]`, sorted descending before slicing.
- Category label format: `session_title` when present, otherwise fall back to `session_id`.

### `明细数据`

- No chart is added in this fix. The raw table remains table-only.

## Empty-State And Failure Handling

- If a chart has no usable rows, render a centered `No data` message instead of raising.
- If `matplotlib` is unavailable, preserve the existing graceful no-chart behavior.
- If one chart refresh fails, the GUI load should still preserve table population and expose a readable status or dialog rather than silently breaking all tabs.
- Chart refresh failures must be isolated per chart so table population can still complete and the overall load is not treated as a total failure solely because one chart did not render.

## Code Changes

### `opencode_token_app/charts.py`

- Keep `create_figure()` and `attach_canvas()`.
- Add reusable plotting helpers for:
  - clearing figures safely
  - empty-state text
  - line charts
  - horizontal bar charts
  - pie charts
- Keep helper inputs simple: figure, title, labels, values, and optional axis labels.

### `opencode_token_app/gui.py`

- Replace fire-and-forget figure creation with stored chart references.
- Add chart metadata storage such as a small chart registry or named attributes for overview/model/day/session charts.
- Add `_refresh_charts()` and smaller per-chart/per-tab helper methods.
- Call chart refresh immediately after `_populate_view()` or inside that flow once `self.viewmodels` is available.
- Separate table population from chart refresh error handling so `_fill_tree(...)` success is not rolled back by a later plotting exception.

## Testing Strategy

- Add tests before implementation for chart helper behavior where practical.
- Focus automated coverage on deterministic logic:
  - empty data produces a valid empty-state chart path
  - GUI chart refresh can consume viewmodel rows without crashing
  - top-N slicing and expected labels/values are passed into chart helpers correctly
- Add fallback coverage that chart helper entry points safely no-op when `matplotlib` objects are unavailable.
- Add failure-isolation coverage showing one chart refresh exception does not stop tree/table population for the rest of the loaded view.
- Avoid brittle pixel or real-window assertions.

## Non-Goals

- No new interactive chart controls.
- No second spend chart per tab in this fix.
- No redesign of the existing notebook layout.
- No migration away from `matplotlib`.

## Success Criteria

- Loading a valid database renders visible charts in `总览`, `模型分析`, `按日分析`, and `会话分析`.
- Empty datasets show a stable `No data` chart state instead of blank confusion or exceptions.
- Table rendering continues to work unchanged.
