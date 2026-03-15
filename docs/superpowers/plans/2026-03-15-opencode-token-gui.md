# OpenCode Token GUI Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Tkinter desktop app that loads an `opencode.db`, visualizes token usage, estimates spend from bundled pricing data, and preserves the existing CSV export workflow.

**Architecture:** Refactor the current script into shared data/export functions, add a pricing enrichment layer that works from raw message rows upward, then build a Tkinter GUI that consumes view-model-ready datasets. Keep CLI behavior backward compatible while adding a separate GUI entry point.

**Tech Stack:** Python, Tkinter, sqlite3, matplotlib, pytest

---

## File Map

- Modify: `export_opencode_tokens.py` - reduce to CLI entry using shared modules
- Create: `opencode_token_gui.py` - GUI entry point and default DB bootstrap
- Create: `opencode_token_app/__init__.py` - package marker
- Create: `opencode_token_app/data_loader.py` - SQLite reading, normalization, aggregation helpers
- Create: `opencode_token_app/exporter.py` - CSV export with backward-compatible filenames
- Create: `opencode_token_app/pricing.py` - pricing load, override merge, row enrichment, aggregate pricing overlays
- Create: `opencode_token_app/viewmodels.py` - GUI-facing formatting and top-N/chart/table shaping
- Create: `opencode_token_app/gui.py` - Tkinter app shell, tabs, controls, error dialogs
- Create: `opencode_token_app/charts.py` - matplotlib embedding helpers
- Create: `opencode_token_app/prices.json` - bundled mainstream pricing data
- Create: `tests/test_data_loader.py` - data parsing and aggregation tests
- Create: `tests/test_pricing.py` - pricing and override tests
- Create: `tests/test_gui_viewmodels.py` - viewmodel and GUI smoke tests
- Create: `tests/fixtures/` - JSON/sample fixtures if needed

## Chunk 1: Shared Data And Export Foundations

### Task 1: Scaffold package and move pure helpers under test

**Files:**
- Create: `opencode_token_app/__init__.py`
- Create: `opencode_token_app/data_loader.py`
- Test: `tests/test_data_loader.py`

- [ ] **Step 1: Write the failing test for normalization and timestamp helpers**

```python
from opencode_token_app.data_loader import canonical_model_key, format_ts_ms_local


def test_canonical_model_key_normalizes_provider_and_model():
    assert canonical_model_key(" OpenAI ", "GPT-4.1  Mini") == "openai:gpt-4.1 mini"


def test_format_ts_ms_local_returns_blank_for_non_positive():
    assert format_ts_ms_local(0) == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_data_loader.py -v`
Expected: FAIL with import or attribute errors for missing module/functions.

- [ ] **Step 3: Write minimal implementation for package marker and helpers**

```python
import re
from datetime import datetime


def _normalize_text(value: str) -> str:
    value = (value or "").strip().lower()
    return re.sub(r"\s+", " ", value)


def canonical_model_key(provider: str, model: str) -> str:
    return f"{_normalize_text(provider)}:{_normalize_text(model)}"


def format_ts_ms_local(ts):
    ts = int(ts or 0)
    if ts <= 0:
        return ""
    return datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d %H:%M:%S")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_data_loader.py -v`
Expected: PASS for the new helper tests.

- [ ] **Step 5: Commit**

```bash
git add opencode_token_app/__init__.py opencode_token_app/data_loader.py tests/test_data_loader.py
git commit -m "test: scaffold shared data helpers"
```

### Task 2: Add failing tests for safe JSON parsing, cost parsing, and raw message normalization

**Files:**
- Modify: `opencode_token_app/data_loader.py`
- Modify: `tests/test_data_loader.py`

- [ ] **Step 1: Write the failing tests for safe parsing helpers and raw message parsing**

```python
from opencode_token_app.data_loader import build_raw_message_row, parse_recorded_cost, safe_json_loads


def test_safe_json_loads_returns_empty_dict_for_bad_json():
    assert safe_json_loads("{") == {}


def test_parse_recorded_cost_returns_none_for_bad_value():
    assert parse_recorded_cost("abc") is None


def test_parse_recorded_cost_accepts_numeric_and_empty_inputs():
    assert parse_recorded_cost(1) == 1.0
    assert parse_recorded_cost("1.25") == 1.25
    assert parse_recorded_cost(1.5) == 1.5
    assert parse_recorded_cost("") is None
    assert parse_recorded_cost(None) is None


def test_build_raw_message_row_keeps_positive_token_message():
    row = {
        "id": "m1",
        "session_id": "s1",
        "time_created": 1710000000000,
        "data": {
            "providerID": "OpenAI",
            "modelID": "gpt-4.1-mini",
            "role": "assistant",
            "mode": "chat",
            "cost": "0.12",
            "tokens": {"total": 30, "input": 10, "output": 20, "reasoning": 5},
        },
    }

    result = build_raw_message_row(row, {"s1": "Demo"})

    assert result["session_title"] == "Demo"
    assert result["day"]
    assert result["cost"] == 0.12
    assert result["provider"] == "openai"
    assert result["model"] == "gpt-4.1-mini"


def test_build_raw_message_row_skips_zero_total_tokens():
    row = {"id": "m2", "session_id": "s1", "time_created": 1710000000000, "data": {"tokens": {"total": 0}}}
    assert build_raw_message_row(row, {}) is None


def test_build_raw_message_row_handles_malformed_json_payload():
    row = {"id": "m3", "session_id": "s1", "time_created": 1710000000000, "data": "{"}
    assert build_raw_message_row(row, {}) is None


def test_build_raw_message_row_defaults_missing_token_and_cost_fields_safely():
    row = {
        "id": "m4",
        "session_id": "s1",
        "time_created": 1710000000000,
        "data": {"providerID": "OpenAI", "modelID": "gpt-4.1-mini", "tokens": {"total": 5}},
    }
    result = build_raw_message_row(row, {})
    assert result["input_tokens"] == 0
    assert result["output_tokens"] == 0
    assert result["cost"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_data_loader.py::test_build_raw_message_row_keeps_positive_token_message tests/test_data_loader.py::test_build_raw_message_row_skips_zero_total_tokens -v`
Expected: FAIL because the parsing helpers and `build_raw_message_row` do not exist yet.

- [ ] **Step 3: Write minimal implementation for safe parsing and row inclusion**

```python
def parse_recorded_cost(value):
    try:
        if value in (None, ""):
            return None
        return float(value)
    except Exception:
        return None


def build_raw_message_row(row, session_title_map):
    data = safe_json_loads(row["data"])
    total_tokens = to_int(get_nested(data, "tokens", "total", default=0))
    if total_tokens <= 0:
        return None
    time_created_text = format_ts_ms_local(row["time_created"])
    provider = _normalize_text(get_nested(data, "providerID", default="") or "")
    model = _normalize_text(get_nested(data, "modelID", default="") or "")
    return {
        "message_id": row["id"],
        "session_id": row["session_id"],
        "session_title": session_title_map.get(row["session_id"], ""),
        "time_created": row["time_created"],
        "time_created_text": time_created_text,
        "day": time_created_text[:10] if time_created_text else "",
        "provider": provider,
        "model": model,
        "role": (get_nested(data, "role", default="") or ""),
        "mode": (get_nested(data, "mode", default="") or ""),
        "cost": parse_recorded_cost(get_nested(data, "cost", default=None)),
        "total_tokens": total_tokens,
        "input_tokens": to_int(get_nested(data, "tokens", "input", default=0)),
        "output_tokens": to_int(get_nested(data, "tokens", "output", default=0)),
        "reasoning_tokens": to_int(get_nested(data, "tokens", "reasoning", default=0)),
        "cache_read": to_int(get_nested(data, "tokens", "cache", "read", default=0)),
        "cache_write": to_int(get_nested(data, "tokens", "cache", "write", default=0)),
    }
```

- [ ] **Step 3a: Normalize provider/model values in the raw row implementation**

```python
provider = _normalize_text(get_nested(data, "providerID", default="") or "")
model = _normalize_text(get_nested(data, "modelID", default="") or "")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_data_loader.py -v`
Expected: PASS for helper and raw-row tests.

- [ ] **Step 5: Commit**

```bash
git add opencode_token_app/data_loader.py tests/test_data_loader.py
git commit -m "test: cover raw message normalization rules"
```

### Task 3: Add failing tests for aggregate token outputs and normalized grouping

**Files:**
- Modify: `opencode_token_app/data_loader.py`
- Modify: `tests/test_data_loader.py`

- [ ] **Step 1: Write the failing test for aggregate datasets**

```python
from opencode_token_app.data_loader import aggregate_usage


def test_aggregate_usage_builds_summary_model_session_and_day():
    raw_rows = [
        {
            "message_id": "m1",
            "session_id": "s1",
            "session_title": "Demo",
            "time_created": 1710000000000,
            "time_created_text": "2024-03-09 16:00:00",
            "day": "2024-03-09",
            "provider": "OpenAI",
            "model": "gpt-4.1-mini",
            "role": "assistant",
            "mode": "chat",
            "cost": 0.1,
            "total_tokens": 30,
            "input_tokens": 10,
            "output_tokens": 20,
            "reasoning_tokens": 0,
            "cache_read": 0,
            "cache_write": 0,
        }
    ]

    result = aggregate_usage(raw_rows)

    assert result["summary"]["message_count"] == 1
    assert result["summary"]["total_tokens"] == 30
    assert result["summary"]["input_tokens"] == 10
    assert result["summary"]["output_tokens"] == 20
    assert result["summary"]["reasoning_tokens"] == 0
    assert result["summary"]["cache_read"] == 0
    assert result["summary"]["cache_write"] == 0
    assert result["summary"]["recorded_cost_total"] == 0.1
    assert result["by_model"][0]["message_count"] == 1
    assert result["by_model"][0]["provider"] == "openai"
    assert result["by_model"][0]["input_tokens"] == 10
    assert result["by_model"][0]["output_tokens"] == 20
    assert result["by_model"][0]["reasoning_tokens"] == 0
    assert result["by_model"][0]["cache_read"] == 0
    assert result["by_model"][0]["cache_write"] == 0
    assert result["by_model"][0]["recorded_cost_total"] == 0.1
    assert result["by_model"][0]["model"] == "gpt-4.1-mini"
    assert result["by_session"][0]["message_count"] == 1
    assert result["by_session"][0]["input_tokens"] == 10
    assert result["by_session"][0]["output_tokens"] == 20
    assert result["by_session"][0]["reasoning_tokens"] == 0
    assert result["by_session"][0]["cache_read"] == 0
    assert result["by_session"][0]["cache_write"] == 0
    assert result["by_session"][0]["recorded_cost_total"] == 0.1
    assert result["by_session"][0]["session_title"] == "Demo"
    assert result["by_day"][0]["message_count"] == 1
    assert result["by_day"][0]["input_tokens"] == 10
    assert result["by_day"][0]["total_tokens"] == 30
    assert result["by_day"][0]["output_tokens"] == 20
    assert result["by_day"][0]["reasoning_tokens"] == 0
    assert result["by_day"][0]["cache_read"] == 0
    assert result["by_day"][0]["cache_write"] == 0
    assert result["by_day"][0]["recorded_cost_total"] == 0.1
    assert result["by_day"][0]["day"] == "2024-03-09"


def test_aggregate_usage_groups_model_rows_by_normalized_provider_and_model():
    raw_rows = [
        {"message_id": "m1", "session_id": "s1", "session_title": "Demo", "time_created": 1, "time_created_text": "2024-03-09 10:00:00", "day": "2024-03-09", "provider": " OpenAI ", "model": "GPT-4.1-MINI", "role": "assistant", "mode": "chat", "cost": None, "total_tokens": 10, "input_tokens": 5, "output_tokens": 5, "reasoning_tokens": 0, "cache_read": 0, "cache_write": 0},
        {"message_id": "m2", "session_id": "s1", "session_title": "Demo", "time_created": 2, "time_created_text": "2024-03-09 10:00:01", "day": "2024-03-09", "provider": "openai", "model": "gpt-4.1-mini", "role": "assistant", "mode": "chat", "cost": None, "total_tokens": 20, "input_tokens": 10, "output_tokens": 10, "reasoning_tokens": 0, "cache_read": 0, "cache_write": 0},
    ]

    result = aggregate_usage(raw_rows)

    assert len(result["by_model"]) == 1
    assert result["by_model"][0]["provider"] == "openai"
    assert result["by_model"][0]["model"] == "gpt-4.1-mini"
    assert result["by_model"][0]["total_tokens"] == 30


def test_aggregate_usage_sorts_day_rows_ascending():
    raw_rows = [
        {"message_id": "m1", "session_id": "s1", "session_title": "Demo", "time_created": 1, "time_created_text": "2024-03-10 10:00:00", "day": "2024-03-10", "provider": "openai", "model": "gpt-4.1-mini", "role": "assistant", "mode": "chat", "cost": None, "total_tokens": 10, "input_tokens": 5, "output_tokens": 5, "reasoning_tokens": 0, "cache_read": 0, "cache_write": 0},
        {"message_id": "m2", "session_id": "s1", "session_title": "Demo", "time_created": 2, "time_created_text": "2024-03-09 10:00:00", "day": "2024-03-09", "provider": "openai", "model": "gpt-4.1-mini", "role": "assistant", "mode": "chat", "cost": None, "total_tokens": 10, "input_tokens": 5, "output_tokens": 5, "reasoning_tokens": 0, "cache_read": 0, "cache_write": 0},
    ]

    result = aggregate_usage(raw_rows)

    assert [row["day"] for row in result["by_day"]] == ["2024-03-09", "2024-03-10"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_data_loader.py::test_aggregate_usage_builds_summary_model_session_and_day -v`
Expected: FAIL because `aggregate_usage` does not exist yet.

- [ ] **Step 3: Write minimal implementation for aggregate usage output**

```python
def aggregate_usage(raw_rows):
    # Build summary, by_model, by_session, by_day with token counts and recorded_cost_total.
    return {
        "summary": summary,
        "by_model": by_model_rows,
        "by_session": by_session_rows,
        "by_day": by_day_rows,
        "raw_messages": sorted_rows,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_data_loader.py -v`
Expected: PASS with aggregate totals matching the spec contract.

- [ ] **Step 5: Commit**

```bash
git add opencode_token_app/data_loader.py tests/test_data_loader.py
git commit -m "test: add aggregate usage datasets"
```

### Task 4: Add failing tests for CSV export contract

**Files:**
- Create: `opencode_token_app/exporter.py`
- Modify: `tests/test_data_loader.py`

- [ ] **Step 1: Write the failing test for backward-compatible filenames**

```python
from opencode_token_app.exporter import export_usage_csvs


def test_export_usage_csvs_writes_legacy_filenames(tmp_path):
    datasets = {
        "summary": {"message_count": 1},
        "by_model": [],
        "by_session": [],
        "by_day": [],
        "raw_messages": [],
    }

    written_dir = export_usage_csvs(tmp_path / "token_export", datasets)

    assert written_dir == (tmp_path / "token_export")
    assert (tmp_path / "token_export" / "summary.csv").exists()
    assert (tmp_path / "token_export" / "by_model.csv").exists()
    assert (tmp_path / "token_export" / "by_session.csv").exists()
    assert (tmp_path / "token_export" / "by_day.csv").exists()
    assert (tmp_path / "token_export" / "raw_messages_with_tokens.csv").exists()
    assert "message_count" in (tmp_path / "token_export" / "summary.csv").read_text(encoding="utf-8-sig")
    assert "provider,model,message_count,total_tokens,input_tokens,output_tokens,reasoning_tokens,cache_read,cache_write,recorded_cost_total" in (tmp_path / "token_export" / "by_model.csv").read_text(encoding="utf-8-sig")
    assert "session_id,session_title,message_count,total_tokens,input_tokens,output_tokens,reasoning_tokens,cache_read,cache_write,recorded_cost_total" in (tmp_path / "token_export" / "by_session.csv").read_text(encoding="utf-8-sig")
    assert "day,message_count,total_tokens,input_tokens,output_tokens,reasoning_tokens,cache_read,cache_write,recorded_cost_total" in (tmp_path / "token_export" / "by_day.csv").read_text(encoding="utf-8-sig")
    assert "session_title" in (tmp_path / "token_export" / "raw_messages_with_tokens.csv").read_text(encoding="utf-8-sig")
    assert ",," in (tmp_path / "token_export" / "raw_messages_with_tokens.csv").read_text(encoding="utf-8-sig")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_data_loader.py::test_export_usage_csvs_writes_legacy_filenames -v`
Expected: FAIL because exporter module/function does not exist yet.

- [ ] **Step 3: Write minimal implementation for CSV export**

```python
CSV_OUTPUTS = {
    "summary": "summary.csv",
    "by_model": "by_model.csv",
    "by_session": "by_session.csv",
    "by_day": "by_day.csv",
    "raw_messages": "raw_messages_with_tokens.csv",
}


def export_usage_csvs(out_dir, datasets):
    # create dir and write CSVs using the filename contract above
    return out_dir
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_data_loader.py -v`
Expected: PASS including export filename assertions.

- [ ] **Step 5: Commit**

```bash
git add opencode_token_app/exporter.py tests/test_data_loader.py
git commit -m "test: preserve legacy csv export filenames"
```

### Task 5: Add failing tests for shared SQLite loading entry point

**Files:**
- Modify: `opencode_token_app/data_loader.py`
- Modify: `tests/test_data_loader.py`

- [ ] **Step 1: Write the failing test for reusable database loading**

```python
from opencode_token_app.data_loader import load_usage_from_db


def test_load_usage_from_db_reads_session_and_message_tables(tmp_path):
    build_test_db(tmp_path / "opencode.db", include_session=True, include_message=True)
    result = load_usage_from_db(tmp_path / "opencode.db")
    assert result["summary"]["message_count"] == 1


def test_load_usage_from_db_continues_when_session_table_is_missing(tmp_path):
    build_test_db(tmp_path / "opencode.db", include_session=False, include_message=True)
    result = load_usage_from_db(tmp_path / "opencode.db")
    assert result["by_session"][0]["session_title"] == ""


def test_load_usage_from_db_fails_when_message_table_is_missing(tmp_path):
    build_test_db(tmp_path / "opencode.db", include_session=True, include_message=False)
    with pytest.raises(Exception):
        load_usage_from_db(tmp_path / "opencode.db")


def test_load_usage_from_db_treats_session_query_failure_as_recoverable(monkeypatch, tmp_path):
    build_test_db(tmp_path / "opencode.db", include_session=True, include_message=True)
    monkeypatch.setattr("opencode_token_app.data_loader.read_session_rows", lambda conn: (_ for _ in ()).throw(RuntimeError("session read failed")))
    result = load_usage_from_db(tmp_path / "opencode.db")
    assert all("session_title" in row for row in result["by_session"])


def test_load_usage_from_db_treats_message_query_failure_as_non_recoverable(monkeypatch, tmp_path):
    build_test_db(tmp_path / "opencode.db", include_session=True, include_message=True)
    monkeypatch.setattr("opencode_token_app.data_loader.read_message_rows", lambda conn: (_ for _ in ()).throw(RuntimeError("message read failed")))
    with pytest.raises(Exception):
        load_usage_from_db(tmp_path / "opencode.db")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_data_loader.py::test_load_usage_from_db_reads_session_and_message_tables -v`
Expected: FAIL because `load_usage_from_db` does not exist yet.

- [ ] **Step 3: Write minimal implementation for shared SQLite loading**

```python
def load_usage_from_db(db_path):
    # open sqlite db, treat missing session as recoverable, missing message as non-recoverable,
    # build normalized raw rows, then aggregate usage
    return datasets
```

- [ ] **Step 4: Run tests to verify it passes**

Run: `pytest tests/test_data_loader.py -v`
Expected: PASS for the reusable SQLite loading path and prior data-layer tests.

- [ ] **Step 5: Commit**

```bash
git add opencode_token_app/data_loader.py tests/test_data_loader.py
git commit -m "test: add reusable sqlite loading pipeline"
```

## Chunk 2: Pricing And CLI Integration

### Task 6: Add failing tests for bundled pricing lookup, deterministic override loading, and normalized matching

**Files:**
- Create: `opencode_token_app/pricing.py`
- Create: `opencode_token_app/prices.json`
- Create: `tests/test_pricing.py`

- [ ] **Step 1: Write the failing tests for pricing file loading, override precedence, and normalized lookup**

```python
from pathlib import Path
from opencode_token_app.pricing import find_local_override_path, load_effective_price_map, load_price_map, merge_price_maps, normalize_price_map


def test_merge_price_maps_prefers_override_values():
    base = normalize_price_map({
        "openai:gpt-4.1-mini": {"provider": "openai", "model": "gpt-4.1-mini", "input_price_per_million": 1.0, "output_price_per_million": 2.0}
    })
    override = normalize_price_map({
        "openai:gpt-4.1-mini": {"provider": "openai", "model": "gpt-4.1-mini", "input_price_per_million": 1.5}
    })

    merged = merge_price_maps(base, override)

    assert merged["openai:gpt-4.1-mini"]["input_price_per_million"] == 1.5
    assert merged["openai:gpt-4.1-mini"]["output_price_per_million"] == 2.0


def test_load_price_map_prefers_prices_local_beside_entry_script(tmp_path):
    bundled = tmp_path / "prices.json"
    bundled.write_text('{"openai:gpt-4.1-mini":{"provider":"openai","model":"gpt-4.1-mini","input_price_per_million":1.0,"output_price_per_million":2.0}}', encoding="utf-8")
    local_override = tmp_path / "prices.local.json"
    local_override.write_text('{"openai:gpt-4.1-mini":{"provider":"openai","model":"gpt-4.1-mini","input_price_per_million":1.5}}', encoding="utf-8")

    loaded = load_price_map(bundled, local_override)

    assert loaded["openai:gpt-4.1-mini"]["input_price_per_million"] == 1.5


def test_normalized_lookup_matches_provider_and_model_variants():
    loaded = normalize_price_map({
        "openai:gpt-4.1-mini": {"provider": "openai", "model": "gpt-4.1-mini", "input_price_per_million": 1.0, "output_price_per_million": 2.0}
    })
    assert "openai:gpt-4.1-mini" in loaded


def test_find_local_override_path_checks_entry_script_directory(tmp_path):
    entry_script = tmp_path / "opencode_token_gui.py"
    entry_script.write_text("# stub", encoding="utf-8")
    (tmp_path / "prices.local.json").write_text("{}", encoding="utf-8")

    assert find_local_override_path(entry_script) == (tmp_path / "prices.local.json")


def test_find_local_override_path_checks_packaged_executable_directory(tmp_path):
    packaged_exe = tmp_path / "opencode_token_gui.exe"
    packaged_exe.write_text("stub", encoding="utf-8")
    (tmp_path / "prices.local.json").write_text("{}", encoding="utf-8")

    assert find_local_override_path(packaged_exe) == (tmp_path / "prices.local.json")


def test_load_effective_price_map_uses_bundled_and_discovered_override(monkeypatch, tmp_path):
    bundled = tmp_path / "prices.json"
    bundled.write_text('{"openai:gpt-4.1-mini":{"provider":"openai","model":"gpt-4.1-mini","input_price_per_million":1.0,"output_price_per_million":2.0}}', encoding="utf-8")
    discovered = tmp_path / "prices.local.json"
    discovered.write_text('{"openai:gpt-4.1-mini":{"provider":"openai","model":"gpt-4.1-mini","input_price_per_million":1.5}}', encoding="utf-8")
    monkeypatch.setattr("opencode_token_app.pricing.BUNDLED_PRICES_PATH", bundled)
    monkeypatch.setattr("opencode_token_app.pricing.find_local_override_path", lambda entry_path: discovered)

    loaded = load_effective_price_map(tmp_path / "opencode_token_gui.py")

    assert loaded["openai:gpt-4.1-mini"]["input_price_per_million"] == 1.5
    assert loaded["openai:gpt-4.1-mini"]["price_source"] == "override"


def test_load_effective_price_map_uses_bundled_prices_when_override_missing(monkeypatch, tmp_path):
    bundled = tmp_path / "prices.json"
    bundled.write_text('{"openai:gpt-4.1-mini":{"provider":"openai","model":"gpt-4.1-mini","input_price_per_million":1.0,"output_price_per_million":2.0}}', encoding="utf-8")
    monkeypatch.setattr("opencode_token_app.pricing.BUNDLED_PRICES_PATH", bundled)
    monkeypatch.setattr("opencode_token_app.pricing.find_local_override_path", lambda entry_path: None)

    loaded = load_effective_price_map(tmp_path / "opencode_token_gui.py")

    assert loaded["openai:gpt-4.1-mini"]["input_price_per_million"] == 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_pricing.py -v`
Expected: FAIL because pricing module/functions do not exist yet.

- [ ] **Step 3: Write minimal implementation for price-map normalization and merge**

```python
def normalize_price_map(raw_map):
    return {canonical_model_key(v.get("provider", ""), v.get("model", "")): dict(v) for v in raw_map.values()}


def merge_price_maps(base, override):
    merged = {k: {**v, "price_source": "bundled"} for k, v in base.items()}
    for key, value in override.items():
        merged[key] = {**merged.get(key, {}), **value, "price_source": "override"}
    return merged
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_pricing.py -v`
Expected: PASS for merge precedence behavior.

- [ ] **Step 5: Commit**

```bash
git add opencode_token_app/pricing.py opencode_token_app/prices.json tests/test_pricing.py
git commit -m "test: add price map loading and override merge"
```

### Task 7: Add failing tests for bundled price data, raw-row estimated cost, cache pricing, and price status

**Files:**
- Modify: `opencode_token_app/pricing.py`
- Modify: `opencode_token_app/prices.json`
- Modify: `tests/test_pricing.py`

- [ ] **Step 1: Write the failing test for message-row pricing**

```python
import json
from pathlib import Path
from opencode_token_app.pricing import enrich_raw_rows_with_pricing


def test_enrich_raw_rows_with_pricing_sets_estimated_cost_and_status():
    rows = [
        {
            "provider": "OpenAI",
            "model": "gpt-4.1-mini",
            "input_tokens": 500000,
            "output_tokens": 250000,
            "cache_read": 100000,
            "cache_write": 50000,
        }
    ]
    price_map = {
        "openai:gpt-4.1-mini": {
            "provider": "openai",
            "model": "gpt-4.1-mini",
            "input_price_per_million": 1.0,
            "output_price_per_million": 2.0,
            "cache_read_price_per_million": 0.1,
            "cache_write_price_per_million": 0.2,
        }
    }

    enriched = enrich_raw_rows_with_pricing(rows, price_map)

    assert enriched[0]["estimated_cache_read_cost"] == 0.01
    assert enriched[0]["estimated_cache_write_cost"] == 0.01
    assert enriched[0]["estimated_cost"] == 1.02
    assert enriched[0]["price_status"] == "priced"
    assert enriched[0]["price_source"] == "bundled"


def test_enrich_raw_rows_with_pricing_marks_override_source_when_override_prices_are_used():
    rows = [{"provider": "OpenAI", "model": "gpt-4.1-mini", "input_tokens": 1_000_000, "output_tokens": 0, "cache_read": 0, "cache_write": 0}]
    price_map = {"openai:gpt-4.1-mini": {"provider": "openai", "model": "gpt-4.1-mini", "input_price_per_million": 1.5, "output_price_per_million": 2.0, "price_source": "override"}}
    enriched = enrich_raw_rows_with_pricing(rows, price_map)
    assert enriched[0]["price_source"] == "override"


def test_enrich_raw_rows_with_pricing_does_not_bill_reasoning_tokens():
    rows = [{"provider": "OpenAI", "model": "gpt-4.1-mini", "input_tokens": 0, "output_tokens": 0, "reasoning_tokens": 999999, "cache_read": 0, "cache_write": 0}]
    price_map = {"openai:gpt-4.1-mini": {"provider": "openai", "model": "gpt-4.1-mini", "input_price_per_million": 1.0, "output_price_per_million": 2.0}}
    enriched = enrich_raw_rows_with_pricing(rows, price_map)
    assert enriched[0]["estimated_cost"] == 0


def test_enrich_raw_rows_with_pricing_only_sets_cache_details_when_cache_prices_exist():
    rows = [{"provider": "OpenAI", "model": "gpt-4.1-mini", "input_tokens": 0, "output_tokens": 0, "cache_read": 100, "cache_write": 100}]
    price_map = {"openai:gpt-4.1-mini": {"provider": "openai", "model": "gpt-4.1-mini", "input_price_per_million": 1.0, "output_price_per_million": 2.0}}
    enriched = enrich_raw_rows_with_pricing(rows, price_map)
    assert enriched[0]["estimated_cache_read_cost"] is None
    assert enriched[0]["estimated_cache_write_cost"] is None


def test_enrich_raw_rows_with_pricing_marks_unknown_models_unpriced():
    rows = [{"provider": "unknown", "model": "x", "input_tokens": 1, "output_tokens": 1, "cache_read": 0, "cache_write": 0}]
    enriched = enrich_raw_rows_with_pricing(rows, {})
    assert enriched[0]["estimated_cost"] is None
    assert enriched[0]["estimated_cache_read_cost"] is None
    assert enriched[0]["estimated_cache_write_cost"] is None
    assert enriched[0]["price_status"] == "unpriced"


def test_enrich_raw_rows_with_pricing_preserves_recorded_cost_field():
    rows = [{"provider": "OpenAI", "model": "gpt-4.1-mini", "cost": 0.5, "input_tokens": 1_000_000, "output_tokens": 0, "cache_read": 0, "cache_write": 0}]
    price_map = {"openai:gpt-4.1-mini": {"provider": "openai", "model": "gpt-4.1-mini", "input_price_per_million": 1.0, "output_price_per_million": 2.0}}
    enriched = enrich_raw_rows_with_pricing(rows, price_map)
    assert enriched[0]["cost"] == 0.5
    assert enriched[0]["estimated_cost"] == 1.0


def test_bundled_prices_json_contains_mainstream_seed_data():
    data = json.loads(Path("opencode_token_app/prices.json").read_text(encoding="utf-8"))
    assert "openai:gpt-4.1-mini" in data
    assert "anthropic:claude-3-5-sonnet" in data or "anthropic:claude-3.5-sonnet" in data
    first_key, first_value = next(iter(data.items()))
    assert ":" in first_key
    assert "input_price_per_million" in first_value
    assert "output_price_per_million" in first_value
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_pricing.py::test_enrich_raw_rows_with_pricing_sets_estimated_cost_and_status -v`
Expected: FAIL because row enrichment, cache-detail fields, and bundled price data are not implemented yet.

- [ ] **Step 3: Write minimal implementation for pricing formula and unpriced handling**

```python
def load_effective_price_map(entry_path=None):
    override_path = find_local_override_path(entry_path)
    return load_price_map(BUNDLED_PRICES_PATH, override_path)


def enrich_raw_rows_with_pricing(rows, price_map):
    enriched = []
    for row in rows:
        key = canonical_model_key(row.get("provider", ""), row.get("model", ""))
        price = price_map.get(key)
        new_row = dict(row)
        if not price:
            new_row.update({"estimated_cost": None, "estimated_cache_read_cost": None, "estimated_cache_write_cost": None, "price_status": "unpriced", "price_source": "missing"})
        else:
            estimated_cache_read_cost = None if "cache_read_price_per_million" not in price else (row.get("cache_read", 0) / 1_000_000) * price.get("cache_read_price_per_million", 0)
            estimated_cache_write_cost = None if "cache_write_price_per_million" not in price else (row.get("cache_write", 0) / 1_000_000) * price.get("cache_write_price_per_million", 0)
            estimated_cost = ((row.get("input_tokens", 0) / 1_000_000) * price["input_price_per_million"]) + ((row.get("output_tokens", 0) / 1_000_000) * price["output_price_per_million"]) + (estimated_cache_read_cost or 0) + (estimated_cache_write_cost or 0)
            new_row.update({"estimated_cost": estimated_cost, "estimated_cache_read_cost": estimated_cache_read_cost, "estimated_cache_write_cost": estimated_cache_write_cost, "price_status": "priced", "price_source": price.get("price_source", "bundled")})
        enriched.append(new_row)
    return enriched
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_pricing.py -v`
Expected: PASS for priced and unpriced row behavior.

- [ ] **Step 5: Commit**

```bash
git add opencode_token_app/pricing.py tests/test_pricing.py
git commit -m "test: price raw message rows"
```

### Task 8: Add failing tests for aggregate pricing overlays

**Files:**
- Modify: `opencode_token_app/pricing.py`
- Modify: `tests/test_pricing.py`

- [ ] **Step 1: Write the failing test for aggregate pricing totals**

```python
from opencode_token_app.pricing import apply_pricing_overlays


def test_apply_pricing_overlays_adds_estimated_cost_totals_and_counts():
    datasets = {
        "summary": {"message_count": 2},
        "by_model": [{"provider": "OpenAI", "model": "gpt-4.1-mini"}],
        "by_session": [{"session_id": "s1", "session_title": "Demo"}],
        "by_day": [{"day": "2024-03-09"}],
        "raw_messages": [
            {"session_id": "s1", "day": "2024-03-09", "provider": "OpenAI", "model": "gpt-4.1-mini", "estimated_cost": 1.0, "price_status": "priced"},
            {"session_id": "s1", "day": "2024-03-09", "provider": "OpenAI", "model": "gpt-4.1-mini", "estimated_cost": None, "price_status": "unpriced"},
        ],
    }

    result = apply_pricing_overlays(datasets)

    assert result["summary"]["estimated_cost_total"] == 1.0
    assert result["summary"]["priced_message_count"] == 1
    assert result["summary"]["unpriced_message_count"] == 1
    assert result["by_model"][0]["estimated_cost_total"] == 1.0
    assert result["by_model"][0]["priced_message_count"] == 1
    assert result["by_model"][0]["unpriced_message_count"] == 1
    assert result["by_session"][0]["estimated_cost_total"] == 1.0
    assert result["by_session"][0]["priced_message_count"] == 1
    assert result["by_session"][0]["unpriced_message_count"] == 1
    assert result["by_day"][0]["estimated_cost_total"] == 1.0
    assert result["by_day"][0]["priced_message_count"] == 1
    assert result["by_day"][0]["unpriced_message_count"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_pricing.py::test_apply_pricing_overlays_adds_estimated_cost_totals_and_counts -v`
Expected: FAIL because aggregate overlays are not implemented yet.

- [ ] **Step 3: Write minimal implementation for pricing overlays**

```python
def apply_pricing_overlays(datasets):
    # sum estimated cost and priced/unpriced counts into summary/by_model/by_session/by_day
    return datasets
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_pricing.py -v`
Expected: PASS with priced/unpriced counts and estimated totals attached.

- [ ] **Step 5: Commit**

```bash
git add opencode_token_app/pricing.py tests/test_pricing.py
git commit -m "test: add aggregate pricing overlays"
```

### Task 9: Refactor CLI entry to shared modules

**Files:**
- Modify: `export_opencode_tokens.py`
- Modify: `opencode_token_app/data_loader.py`
- Modify: `opencode_token_app/exporter.py`
- Modify: `opencode_token_app/pricing.py`
- Test: `tests/test_data_loader.py`
- Test: `tests/test_pricing.py`

- [ ] **Step 1: Write the failing test for end-to-end shared export entry**

```python
from export_opencode_tokens import main


def test_cli_main_preserves_legacy_export_contract(monkeypatch, tmp_path):
    db_path = tmp_path / "opencode.db"
    db_path.write_text("placeholder", encoding="utf-8")
    out_dir = tmp_path / "token_export"

    monkeypatch.setattr("export_opencode_tokens.load_usage_from_db", lambda path: {"summary": {"message_count": 1, "total_tokens": 30, "input_tokens": 10, "output_tokens": 20, "reasoning_tokens": 0, "cache_read": 0, "cache_write": 0, "recorded_cost_total": 0.5}, "by_model": [{"provider": "openai", "model": "gpt-4.1-mini", "message_count": 1, "total_tokens": 30, "input_tokens": 10, "output_tokens": 20, "reasoning_tokens": 0, "cache_read": 0, "cache_write": 0, "recorded_cost_total": 0.5}], "by_session": [{"session_id": "s1", "session_title": "Demo", "message_count": 1, "total_tokens": 30, "input_tokens": 10, "output_tokens": 20, "reasoning_tokens": 0, "cache_read": 0, "cache_write": 0, "recorded_cost_total": 0.5}], "by_day": [{"day": "2024-03-09", "message_count": 1, "total_tokens": 30, "input_tokens": 10, "output_tokens": 20, "reasoning_tokens": 0, "cache_read": 0, "cache_write": 0, "recorded_cost_total": 0.5}], "raw_messages": [{"session_id": "s1", "session_title": "Demo", "day": "2024-03-09", "provider": "openai", "model": "gpt-4.1-mini", "cost": 0.5, "estimated_cost": 1.0, "price_status": "priced", "price_source": "bundled", "total_tokens": 30, "input_tokens": 10, "output_tokens": 20, "reasoning_tokens": 0, "cache_read": 0, "cache_write": 0}]})
    monkeypatch.setattr("export_opencode_tokens.price_loaded_usage", lambda datasets, entry_path=None: {**datasets, "summary": {**datasets["summary"], "estimated_cost_total": 1.0, "priced_message_count": 1, "unpriced_message_count": 0}, "by_model": [{**datasets["by_model"][0], "estimated_cost_total": 1.0, "priced_message_count": 1, "unpriced_message_count": 0}], "by_session": [{**datasets["by_session"][0], "estimated_cost_total": 1.0, "priced_message_count": 1, "unpriced_message_count": 0}], "by_day": [{**datasets["by_day"][0], "estimated_cost_total": 1.0, "priced_message_count": 1, "unpriced_message_count": 0}]})
    monkeypatch.setattr("sys.argv", ["export_opencode_tokens.py", str(db_path), str(out_dir)])

    main()

    assert (out_dir / "summary.csv").exists()
    assert (out_dir / "by_model.csv").exists()
    assert (out_dir / "by_session.csv").exists()
    assert (out_dir / "by_day.csv").exists()
    assert (out_dir / "raw_messages_with_tokens.csv").exists()
    assert "estimated_cost_total" in (out_dir / "summary.csv").read_text(encoding="utf-8-sig")
    assert "priced_message_count" in (out_dir / "summary.csv").read_text(encoding="utf-8-sig")
    assert "unpriced_message_count" in (out_dir / "summary.csv").read_text(encoding="utf-8-sig")
    assert "estimated_cost_total" in (out_dir / "by_model.csv").read_text(encoding="utf-8-sig")
    assert "priced_message_count" in (out_dir / "by_session.csv").read_text(encoding="utf-8-sig")
    assert "price_source" in (out_dir / "raw_messages_with_tokens.csv").read_text(encoding="utf-8-sig")


def test_cli_main_defaults_to_sibling_token_export(monkeypatch, tmp_path):
    db_path = tmp_path / "opencode.db"
    db_path.write_text("placeholder", encoding="utf-8")
    expected_out_dir = tmp_path / "token_export"

    monkeypatch.setattr("export_opencode_tokens.load_usage_from_db", lambda path: {"summary": {"message_count": 0}, "by_model": [], "by_session": [], "by_day": [], "raw_messages": []})
    monkeypatch.setattr("export_opencode_tokens.price_loaded_usage", lambda datasets, entry_path=None: datasets)
    monkeypatch.setattr("sys.argv", ["export_opencode_tokens.py", str(db_path)])

    main()

    assert (expected_out_dir / "summary.csv").exists()
    assert (expected_out_dir / "by_model.csv").exists()
    assert (expected_out_dir / "by_session.csv").exists()
    assert (expected_out_dir / "by_day.csv").exists()
    assert (expected_out_dir / "raw_messages_with_tokens.csv").exists()
    assert "unpriced_message_count" in (expected_out_dir / "by_day.csv").read_text(encoding="utf-8-sig")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_data_loader.py::test_cli_main_preserves_legacy_export_contract -v`
Expected: FAIL until shared pipeline supports empty/minimal datasets correctly.

- [ ] **Step 3: Write minimal implementation to route CLI through shared modules**

```python
def main():
    db_path, out_dir = parse_args(sys.argv)
    datasets = load_usage_from_db(db_path)
    datasets = price_loaded_usage(datasets, entry_path=Path(sys.argv[0]))
    export_usage_csvs(out_dir, datasets)
```

- [ ] **Step 4: Run tests to verify shared CLI path passes**

Run: `pytest tests/test_data_loader.py tests/test_pricing.py -v`
Expected: PASS for the shared pipeline tests.

- [ ] **Step 5: Commit**

```bash
git add export_opencode_tokens.py opencode_token_app/data_loader.py opencode_token_app/exporter.py opencode_token_app/pricing.py tests/test_data_loader.py tests/test_pricing.py
git commit -m "refactor: route cli export through shared modules"
```

## Chunk 3: View Models And Tkinter GUI

### Task 10: Add failing tests for GUI-facing view models

**Files:**
- Create: `opencode_token_app/viewmodels.py`
- Create: `tests/test_gui_viewmodels.py`

- [ ] **Step 1: Write the failing tests for overview, model/day/session tables, and price labels**

```python
from opencode_token_app.viewmodels import build_application_viewmodels, build_overview_viewmodel


def test_build_overview_viewmodel_returns_cards_and_chart_rows():
    datasets = {
        "summary": {"total_tokens": 100, "input_tokens": 40, "output_tokens": 60, "reasoning_tokens": 10, "estimated_cost_total": 1.5, "recorded_cost_total": 1.2},
        "by_model": [{"provider": "OpenAI", "model": "gpt-4.1-mini", "total_tokens": 100, "estimated_cost_total": 1.5}],
        "by_day": [{"day": "2024-03-09", "total_tokens": 100, "estimated_cost_total": 1.5}],
    }

    vm = build_overview_viewmodel(datasets)

    assert vm["cards"]["total_tokens"] == 100
    assert vm["cards"]["input_tokens"] == 40
    assert vm["cards"]["output_tokens"] == 60
    assert vm["cards"]["reasoning_tokens"] == 10
    assert vm["cards"]["estimated_cost_total"] == 1.5
    assert vm["cards"]["recorded_cost_total"] == 1.2
    assert vm["daily_rows"][0]["day"] == "2024-03-09"


def test_build_application_viewmodels_exposes_model_day_session_and_raw_rows():
    datasets = {
        "summary": {"total_tokens": 100, "input_tokens": 40, "output_tokens": 60, "reasoning_tokens": 10, "estimated_cost_total": 1.5, "recorded_cost_total": 1.2},
        "by_model": [{"provider": "OpenAI", "model": "gpt-4.1-mini", "message_count": 2, "total_tokens": 100, "input_tokens": 40, "output_tokens": 60, "estimated_cost_total": 1.5, "recorded_cost_total": 1.2, "priced_message_count": 2, "unpriced_message_count": 0}],
        "by_day": [{"day": "2024-03-09", "message_count": 2, "total_tokens": 100, "input_tokens": 40, "output_tokens": 60, "estimated_cost_total": 1.5, "recorded_cost_total": 1.2}],
        "by_session": [{"session_id": "s1", "session_title": "Demo", "message_count": 2, "total_tokens": 100, "input_tokens": 40, "output_tokens": 60, "estimated_cost_total": 1.5, "recorded_cost_total": 1.2}],
        "raw_messages": [{"day": "2024-03-09", "provider": "OpenAI", "model": "gpt-4.1-mini", "estimated_cost": 1.5, "cost": 1.2, "price_status": "priced"}],
    }

    vm = build_application_viewmodels(datasets)

    assert vm["models"][0]["price_status_label"] == "已定价"
    assert vm["models"][0]["estimated_cost_display"] == "1.50"
    assert vm["models"][0]["recorded_cost_display"] == "1.20"
    assert vm["days"][0]["day"] == "2024-03-09"
    assert vm["days"][0]["message_count"] == 2
    assert vm["days"][0]["estimated_cost_display"] == "1.50"
    assert vm["sessions"][0]["session_title"] == "Demo"
    assert vm["sessions"][0]["message_count"] == 2
    assert vm["sessions"][0]["recorded_cost_display"] == "1.20"
    assert vm["raw_messages"][0]["model"] == "gpt-4.1-mini"


def test_build_application_viewmodels_adds_percentages_and_top_n_rows():
    datasets = {
        "summary": {"total_tokens": 100, "input_tokens": 40, "output_tokens": 60, "reasoning_tokens": 10, "estimated_cost_total": 1.5, "recorded_cost_total": 1.2},
        "by_model": [{"provider": "openai", "model": f"m{i}", "total_tokens": i, "estimated_cost_total": i, "recorded_cost_total": i / 2, "priced_message_count": 1, "unpriced_message_count": 0} for i in range(20, 0, -1)],
        "by_day": [{"day": "2024-03-09", "total_tokens": 100, "estimated_cost_total": 1.5, "recorded_cost_total": 1.2}],
        "by_session": [{"session_id": "s1", "session_title": "Demo", "total_tokens": 100, "estimated_cost_total": 1.5, "recorded_cost_total": 1.2, "price_status": "priced"}],
        "raw_messages": [{"day": "2024-03-09", "provider": "openai", "model": "m1", "price_status": "unpriced"}],
    }

    vm = build_application_viewmodels(datasets)

    assert vm["overview"]["token_percentages"]["input_pct"] == 40
    assert len(vm["overview"]["top_model_rows"]) == 10
    assert vm["raw_messages"][0]["price_status_label"] == "未定价"


def test_build_application_viewmodels_keeps_blank_cost_cells_when_missing():
    datasets = {
        "summary": {"total_tokens": 10, "input_tokens": 5, "output_tokens": 5, "reasoning_tokens": 0, "estimated_cost_total": 0, "recorded_cost_total": 0},
        "by_model": [{"provider": "openai", "model": "m1", "message_count": 1, "total_tokens": 10, "input_tokens": 5, "output_tokens": 5, "estimated_cost_total": None, "recorded_cost_total": None, "priced_message_count": 0, "unpriced_message_count": 1}],
        "by_day": [{"day": "2024-03-09", "message_count": 1, "total_tokens": 10, "input_tokens": 5, "output_tokens": 5, "estimated_cost_total": None, "recorded_cost_total": None}],
        "by_session": [{"session_id": "s1", "session_title": "Demo", "message_count": 1, "total_tokens": 10, "input_tokens": 5, "output_tokens": 5, "estimated_cost_total": None, "recorded_cost_total": None}],
        "raw_messages": [{"day": "2024-03-09", "provider": "openai", "model": "m1", "estimated_cost": None, "cost": None, "price_status": "unpriced"}],
    }

    vm = build_application_viewmodels(datasets)

    assert vm["models"][0]["estimated_cost_display"] == ""
    assert vm["models"][0]["recorded_cost_display"] == ""
    assert vm["raw_messages"][0]["estimated_cost_display"] == ""
    assert vm["raw_messages"][0]["recorded_cost_display"] == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_gui_viewmodels.py -v`
Expected: FAIL because `viewmodels.py` does not exist yet.

- [ ] **Step 3: Write minimal implementation for overview/model/day/session/raw-message view models**

```python
def build_overview_viewmodel(datasets):
    return {
        "cards": datasets["summary"],
        "daily_rows": datasets["by_day"],
        "top_model_rows": datasets["by_model"][:10],
    }


def build_application_viewmodels(datasets):
    # derive overview cards, percentages, top-N rows, aggregate price labels, and raw-message display fields
    return {
        "overview": build_overview_viewmodel(datasets),
        "models": model_rows,
        "days": day_rows,
        "sessions": session_rows,
        "raw_messages": raw_message_rows,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_gui_viewmodels.py -v`
Expected: PASS for overview formatting tests.

- [ ] **Step 5: Commit**

```bash
git add opencode_token_app/viewmodels.py tests/test_gui_viewmodels.py
git commit -m "test: add gui view models"
```

### Task 11: Add failing tests for default DB path and GUI controller load state

**Files:**
- Create: `opencode_token_app/gui.py`
- Create: `opencode_token_gui.py`
- Modify: `tests/test_gui_viewmodels.py`

- [ ] **Step 1: Write the failing test for default path resolution and app state helpers**

```python
from pathlib import Path
from opencode_token_app.gui import default_db_path


def test_default_db_path_uses_userprofile(monkeypatch):
    monkeypatch.setenv("USERPROFILE", r"C:\Users\demo")
    assert default_db_path() == Path(r"C:\Users\demo\.local\share\opencode\opencode.db")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_gui_viewmodels.py::test_default_db_path_uses_userprofile -v`
Expected: FAIL because GUI helper does not exist yet.

- [ ] **Step 3: Write minimal implementation for default path and non-UI controller shell**

```python
def default_db_path() -> Path:
    return Path(os.environ.get("USERPROFILE", "~")).expanduser() / ".local" / "share" / "opencode" / "opencode.db"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_gui_viewmodels.py -v`
Expected: PASS for default path helper tests.

- [ ] **Step 5: Commit**

```bash
git add opencode_token_app/gui.py opencode_token_gui.py tests/test_gui_viewmodels.py
git commit -m "test: add gui bootstrap helpers"
```

### Task 12: Implement charts, notebook tabs, and export action behind smoke coverage

**Files:**
- Create: `opencode_token_app/charts.py`
- Modify: `opencode_token_app/gui.py`
- Modify: `opencode_token_gui.py`
- Modify: `tests/test_gui_viewmodels.py`

- [ ] **Step 1: Write the failing smoke tests for required controls, tabs, filters, and chart placeholders**

```python
def test_gui_app_builds_required_tabs():
    # instantiate app shell or frame factory without mainloop
    # assert notebook tabs include 总览, 模型分析, 按日分析, 会话分析, 明细数据
    ...


def test_gui_app_builds_header_controls_and_raw_filters():
    # assert database path control, browse button, reload button, export button,
    # export directory label, and raw-data filters for day/provider/model
    ...


def test_gui_app_builds_embedded_chart_frames_and_tables_for_analysis_tabs():
    # assert overview/model/day/session tabs each expose a matplotlib-backed chart container and a paired table container
    ...


def test_gui_raw_message_table_supports_sorting_and_filter_actions():
    # assert sortable heading callbacks and filter handlers for day/provider/model exist
    ...


def test_overview_tab_builds_required_chart_types():
    # assert daily token line chart, top-model bar chart, and input-vs-output pie chart are configured
    ...


def test_overview_tab_builds_required_kpi_cards():
    # assert total/input/output/reasoning/estimated-cost/recorded-cost cards are present
    ...


def test_gui_export_action_writes_token_export_beside_selected_db(tmp_path):
    # selecting a db and invoking export should write csv files into sibling token_export/
    ...


def test_raw_message_table_exposes_required_columns():
    # assert provider/model/role/time/token/estimated-cost/recorded-cost/price-status columns are present in the detail table
    ...


def test_analysis_tables_expose_required_token_and_cost_columns():
    # assert model/day/session tables include message count, token totals, estimated cost, recorded cost, and status fields where applicable
    ...


def test_gui_uses_entry_script_location_for_prices_local_override(monkeypatch, tmp_path):
    # assert GUI pricing load passes the GUI entry script or packaged executable path into load_effective_price_map
    ...


def test_gui_uses_packaged_executable_location_for_prices_local_override(monkeypatch, tmp_path):
    # assert bundled executable launches also resolve sibling prices.local.json
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_gui_viewmodels.py -k gui_app_builds_required_tabs -v`
Expected: FAIL because the notebook/tabs are not implemented yet.

- [ ] **Step 3: Write minimal implementation for charts and tabs**

```python
class OpenCodeTokenApp(ttk.Frame):
    def _build_notebook(self):
        # create notebook and tabs listed in the spec
        ...

    def _build_overview_tab(self):
        # embed matplotlib charts for daily token line chart, top-model bar chart, input-vs-output pie chart, and paired table areas
        ...

    def export_current_csvs(self):
        # write token_export beside the selected db path
        ...
```

- [ ] **Step 4: Run targeted tests to verify GUI smoke coverage passes**

Run: `pytest tests/test_gui_viewmodels.py -k gui -v`
Expected: PASS for default path and tab construction smoke tests.

- [ ] **Step 5: Commit**

```bash
git add opencode_token_app/charts.py opencode_token_app/gui.py opencode_token_gui.py tests/test_gui_viewmodels.py
git commit -m "feat: add tkinter notebook and chart scaffolding"
```

### Task 13: Wire full load/analyze/export flow in GUI and run final verification

**Files:**
- Modify: `opencode_token_app/gui.py`
- Modify: `opencode_token_app/viewmodels.py`
- Modify: `tests/test_gui_viewmodels.py`

- [ ] **Step 1: Write the failing integration-oriented tests for controller load flow and GUI error handling**

```python
def test_controller_load_pipeline_returns_viewmodels_for_tabs(tmp_path):
    # stub loader/pricing/viewmodel pipeline and assert GUI controller stores results
    ...


def test_gui_controller_handles_missing_default_db_without_crashing():
    # default path absent should keep app usable for manual browsing
    ...


def test_gui_controller_shows_unpriced_label_for_unknown_models():
    # priced status should surface as 未定价 in the GUI-facing state
    ...


def test_gui_controller_surfaces_sqlite_failure_as_error_state():
    # sqlite open/query failure should not crash the app and should trigger a clear error dialog while keeping the app usable
    ...


def test_gui_controller_handles_missing_session_table_with_blank_titles():
    # missing session table should still load rows with blank titles
    ...


def test_gui_controller_handles_missing_message_table_as_load_error():
    # missing message table should stop the load and surface an error
    ...


def test_gui_chart_render_failure_keeps_table_data_available():
    # chart exception should leave tabular data intact and set a render error message
    ...


def test_gui_controller_export_action_uses_selected_db_sibling_token_export(tmp_path):
    # export button path should resolve to <selected-db-parent>/token_export
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_gui_viewmodels.py -v`
Expected: FAIL on the new GUI pipeline test before wiring is complete.

- [ ] **Step 3: Write minimal implementation for load/analyze/export wiring**

```python
def load_database_into_app(db_path):
    datasets = load_usage_from_db(db_path)
    price_map = load_effective_price_map(gui_entry_path)
    priced = price_datasets(datasets, price_map)
    return build_application_viewmodels(priced)
```

- [ ] **Step 4: Run full verification**

Run: `pytest tests/test_data_loader.py tests/test_pricing.py tests/test_gui_viewmodels.py -v`
Expected: PASS for data, pricing, viewmodel, and smoke-level GUI coverage.

Run: `python export_opencode_tokens.py "%USERPROFILE%\.local\share\opencode\opencode.db"`
Expected: CSV export completes or reports a clear missing-file/database error.

Run: `python opencode_token_gui.py`
Expected: GUI launches with default DB path filled in.

- [ ] **Step 5: Commit**

```bash
git add opencode_token_gui.py opencode_token_app/gui.py opencode_token_app/viewmodels.py tests/test_gui_viewmodels.py
git commit -m "feat: add opencode token desktop app"
```
