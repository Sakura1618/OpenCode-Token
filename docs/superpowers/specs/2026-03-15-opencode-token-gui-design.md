# OpenCode Token GUI Design

## Goal

Build a Tkinter desktop app around the existing token export workflow so a user can:

- choose an `opencode.db` file, defaulting to `%USERPROFILE%\.local\share\opencode\opencode.db`
- inspect the derived `token_export` dataset in a GUI instead of raw CSV only
- visualize token usage across summary, model, session, and day dimensions
- estimate spend using built-in mainstream model pricing with local override support

## Confirmed Decisions

- Desktop UI: `Tkinter`
- Pricing strategy: built-in mainstream pricing table plus local manual override/edit path
- Data scope: one selected `opencode.db` and its generated in-memory/exported `token_export`
- Architecture: split into data, pricing, viewmodel, and GUI modules

## Non-Goals

- No automatic multi-folder scan of all historical `token_export` directories
- No mandatory live price scraping on startup
- No dependency on the GUI for CSV export; CLI export remains available
- No hard requirement for advanced GUI testing beyond smoke coverage

## User Flow

1. Launch GUI entry script.
2. App pre-fills the default database path.
3. User can browse to another `opencode.db` file.
4. User clicks reload/analyze.
5. App reads the database, computes aggregates, applies pricing, and renders charts/tables.
6. User can optionally export or refresh `token_export/*.csv` beside the database.

## Architecture

### 1. Data Layer

Responsibility: load SQLite data and produce normalized statistics independent of the UI.

Planned files:

- `opencode_token_app/data_loader.py`
- `opencode_token_app/exporter.py`

Key responsibilities:

- connect to SQLite and read `session` and `message`
- parse JSON payloads safely
- normalize token fields
- normalize provider/model identifiers deterministically for grouping and pricing
- build aggregate datasets for summary, model, session, day, and raw message rows
- expose reusable functions for both CLI and GUI callers
- export CSV files into `token_export`

Normalization rules:

- trim leading and trailing whitespace from `provider` and `model`
- lowercase both fields for matching and grouping keys
- collapse internal repeated whitespace to a single space
- do not apply alias remapping in v1; use the normalized literal values from the source data
- build the canonical model key as `provider + ":" + model`

Planned data contract:

- `summary`
  - fields: `message_count`, `total_tokens`, `input_tokens`, `output_tokens`, `reasoning_tokens`, `cache_read`, `cache_write`, `recorded_cost_total`, `estimated_cost_total`, `priced_message_count`, `unpriced_message_count`
- `by_model`
  - one row per normalized `provider + model`
  - fields: `provider`, `model`, `message_count`, `total_tokens`, `input_tokens`, `output_tokens`, `reasoning_tokens`, `cache_read`, `cache_write`, `recorded_cost_total`, `estimated_cost_total`, `priced_message_count`, `unpriced_message_count`
- `by_session`
  - one row per `session_id`
  - fields: `session_id`, `session_title`, `message_count`, `total_tokens`, `input_tokens`, `output_tokens`, `reasoning_tokens`, `cache_read`, `cache_write`, `recorded_cost_total`, `estimated_cost_total`, `priced_message_count`, `unpriced_message_count`
- `by_day`
  - one row per day in ascending order
  - fields: `day`, `message_count`, `total_tokens`, `input_tokens`, `output_tokens`, `reasoning_tokens`, `cache_read`, `cache_write`, `recorded_cost_total`, `estimated_cost_total`, `priced_message_count`, `unpriced_message_count`
- `raw_messages`
  - one row per included message
  - fields: `message_id`, `session_id`, `session_title`, `time_created`, `time_created_text`, `day`, `provider`, `model`, `role`, `mode`, `cost`, `total_tokens`, `input_tokens`, `output_tokens`, `reasoning_tokens`, `cache_read`, `cache_write`

Recorded cost contract:

- `cost` is interpreted as a USD amount at message-row granularity when present
- parse numeric, integer, float, or numeric-string values into Python `float`
- treat `null`, empty string, and malformed values as missing rather than zero
- `recorded_cost_total` fields at summary/model/session/day levels are sums of valid parsed message-row costs only
- UI tables should show blank recorded cost cells for missing values, not synthetic zeroes

Pricing enrichment contract:

- pricing is first attached at the `raw_messages` row level
- enriched raw rows add `estimated_cost`, `price_status`, `price_source`, and optional cache pricing details
- `pricing.py` owns the pricing enrichment step and sums enriched raw rows into `estimated_cost_total`, `priced_message_count`, and `unpriced_message_count` for summary/model/session/day outputs
- `data_loader.py` owns token aggregation and recorded-cost aggregation only
- `viewmodels.py` formats aggregate pricing fields for display but does not invent new totals

Day derivation rule:

- derive `time_created_text` and `day` from `time_created` using local system time, matching Python `datetime.fromtimestamp(ts / 1000)` behavior
- `day` is the `YYYY-MM-DD` prefix of that local-time rendering
- CLI and GUI paths must share the same helper so `by_day` output stays consistent

### 2. Pricing Layer

Responsibility: map model usage to unit prices and compute estimated cost.

Planned files:

- `opencode_token_app/pricing.py`
- `opencode_token_app/prices.json`

Pricing rules:

- store prices as USD per 1M tokens
- match by normalized `provider` and `model`
- support input and output prices separately
- keep `reasoning_tokens` visible as its own metric, but do not price it independently in v1
- estimate cost from component tokens only, never from `total_tokens`
- v1 formula per raw message row is:
  - `billable_input_tokens = input_tokens`
  - `billable_output_tokens = output_tokens`
  - `estimated_cost = (billable_input_tokens / 1_000_000) * input_price + (billable_output_tokens / 1_000_000) * output_price`
  - add cache read/write cost terms only when the matched price entry explicitly provides them
- `reasoning_tokens` is treated as informational only unless later evidence shows it must be billed separately for a specific provider
- if a row already contains recorded `cost`, show it alongside estimated cost instead of replacing it
- if no price matches, mark the row as unpriced and exclude it from estimated totals

Override behavior:

- ship with curated built-in pricing data for mainstream models in `opencode_token_app/prices.json`
- allow an optional local override file named `prices.local.json` located beside the GUI entry script, or beside the packaged executable in a bundled build
- if that deterministic sibling file does not exist, run with bundled prices only
- when both sources contain the same normalized model key, local override values win field-by-field

Pricing file schema:

- top-level object keyed by normalized model key, for example `openai:gpt-4.1-mini`
- each value object supports:
  - `provider`: string
  - `model`: string
  - `input_price_per_million`: number
  - `output_price_per_million`: number
  - optional `cache_read_price_per_million`: number
  - optional `cache_write_price_per_million`: number
  - optional `notes`: string
- enriched raw rows expose cache details with fields `estimated_cache_read_cost` and `estimated_cache_write_cost`

### 3. View Model Layer

Responsibility: reshape raw aggregates into UI-friendly structures.

Planned file:

- `opencode_token_app/viewmodels.py`

Responsibilities:

- format totals for cards and table rows
- compute top-N slices for charts
- derive percentages for token composition views
- produce user-facing labels for priced and unpriced models
- expose tab-ready rows that already include estimated cost, recorded cost, and price status

### 4. GUI Layer

Responsibility: provide the desktop experience and connect UI actions to services.

Planned files:

- `opencode_token_app/gui.py`
- `opencode_token_app/charts.py`
- `opencode_token_gui.py`

Main UI layout:

- header controls
  - database path input
  - browse button
  - reload/analyze button
  - export CSV button
  - derived export directory display
- tabbed main content via `ttk.Notebook`
  - `总览`
  - `模型分析`
  - `按日分析`
  - `会话分析`
  - `明细数据`

Tab design:

#### 总览

- KPI cards for total tokens, input tokens, output tokens, reasoning tokens, estimated cost, recorded cost
- line chart for recent daily token usage
- bar chart for top models by total tokens
- pie chart for input vs output composition

#### 模型分析

- table of all models with token totals, estimated cost, recorded cost, price status
- bar chart for model token ranking
- optional second bar chart for model estimated spend ranking

#### 按日分析

- table of daily rows with message count, token totals, estimated cost, recorded cost
- line chart for daily token trend
- optional second line or bar chart for daily estimated spend

#### 会话分析

- table of sessions with title, counts, tokens, estimated cost
- top-N session chart by tokens or spend

#### 明细数据

- raw message table with provider, model, role, time, tokens, cost fields
- v1 includes filters for day, provider, and model
- sortable columns

Chart implementation:

- use `matplotlib` embedded in Tkinter
- keep tables visible under related charts so exact numbers are available
- prefer readable static charts over highly custom interaction

## File Structure

```text
export_opencode_tokens.py
opencode_token_gui.py
opencode_token_app/
  __init__.py
  data_loader.py
  exporter.py
  pricing.py
  viewmodels.py
  gui.py
  charts.py
  prices.json
tests/
  test_data_loader.py
  test_pricing.py
  fixtures/
```

## CLI Compatibility

The existing `export_opencode_tokens.py` remains as the CLI entry point, but should be refactored to call the shared data/export modules instead of owning all logic inline. This preserves current script usage while removing duplication.

CSV filename contract:

- keep existing export filenames in v1 for backward compatibility:
  - `summary.csv`
  - `by_model.csv`
  - `by_session.csv`
  - `by_day.csv`
  - `raw_messages_with_tokens.csv`
- the in-memory dataset may be named `raw_messages`, but the exported filename remains `raw_messages_with_tokens.csv`

## Row Inclusion Rule

- v1 keeps the current behavior: only messages with `total_tokens > 0` are included in `raw_messages`, aggregates, CSV export, and GUI tables/charts
- messages with missing token data or `total_tokens <= 0` are ignored for analytics and export to avoid mixing non-billed/control rows into usage views
- this rule must be shared by CLI and GUI paths so tests and totals stay consistent

## Error Handling

- if the default DB path does not exist, show the path but keep the app usable for manual browsing
- if SQLite open/query fails, show a clear error dialog and keep the app running
- if the `message` table is missing or unreadable, treat that as non-recoverable for the current load attempt and show an error instead of partial results
- if the `session` table is missing or unreadable, continue loading messages and show blank session titles
- if expected JSON fields are missing or malformed, default missing token/cost fields safely and continue loading the remaining row data
- if pricing is missing for a model, show `未定价` rather than misleading zero-cost output
- if chart rendering fails for a tab, preserve table data and show the rendering error in the tab area

## Testing Strategy

Primary automated coverage should target data and pricing logic.

Planned tests:

- `test_data_loader.py`
  - parses representative message payloads
  - ignores zero-token rows as intended
  - aggregates totals by model, session, and day correctly
  - handles missing or malformed JSON safely
- `test_pricing.py`
  - matches normalized provider/model keys
  - computes estimated input and output costs correctly
  - handles missing prices as unpriced rows
  - respects local override pricing data

GUI verification:

- lightweight smoke checks only
- confirm startup with default path resolution
- confirm a loaded dataset populates notebook tabs without crash

## Dependencies

Expected additions:

- `matplotlib` for embedded charts

Expected standard library usage:

- `tkinter`
- `sqlite3`
- `json`
- `csv`
- `pathlib`

## Implementation Notes

- use ASCII in source files unless an existing file already uses Chinese labels and the label is intentionally user-facing
- keep CSV export encoding behavior compatible with current workflow unless tests indicate a need to change it
- avoid over-engineering the first version with background workers unless UI responsiveness becomes a real issue

## Risks And Mitigations

- `Tkinter` tables are basic: mitigate with sortable `Treeview` columns and focused filtering
- price data can drift: mitigate with bundled defaults plus local override support
- model naming can vary: mitigate with normalization and explicit unmatched-model reporting
- large datasets may slow redraws: mitigate by limiting chart top-N rows and keeping raw tables virtualized only if needed later

## Success Criteria

- user can launch a desktop app and load the default or manually selected `opencode.db`
- app shows summary, model, session, day, and raw message data without requiring manual CSV inspection
- app estimates spend for priced mainstream models and marks unknown models clearly
- app can still export `token_export` CSV files for external analysis
