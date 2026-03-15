from opencode_token_app.data_loader import (
    aggregate_usage,
    build_raw_message_row,
    canonical_model_key,
    format_ts_ms_local,
    load_usage_from_db,
    parse_recorded_cost,
    safe_json_loads,
)
from opencode_token_app.exporter import export_usage_csvs
import sqlite3

import pytest


def test_canonical_model_key_normalizes_provider_and_model():
    assert canonical_model_key(" OpenAI ", "GPT-4.1  Mini") == "openai:gpt-4.1 mini"


def test_format_ts_ms_local_returns_blank_for_non_positive():
    assert format_ts_ms_local(0) == ""


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


def build_test_db(path, include_session=True, include_message=True):
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    if include_session:
        cur.execute("CREATE TABLE session (id TEXT PRIMARY KEY, title TEXT)")
        cur.execute("INSERT INTO session (id, title) VALUES (?, ?)", ("s1", "Demo"))
    if include_message:
        cur.execute("CREATE TABLE message (id TEXT PRIMARY KEY, session_id TEXT, time_created INTEGER, data TEXT)")
        cur.execute(
            "INSERT INTO message (id, session_id, time_created, data) VALUES (?, ?, ?, ?)",
            (
                "m1",
                "s1",
                1710000000000,
                '{"providerID":"OpenAI","modelID":"gpt-4.1-mini","cost":"0.1","tokens":{"total":30,"input":10,"output":20,"reasoning":0}}',
            ),
        )
    conn.commit()
    conn.close()


def test_aggregate_usage_builds_summary_model_session_and_day():
    raw_rows = [
        {
            "message_id": "m1",
            "session_id": "s1",
            "session_title": "Demo",
            "time_created": 1710000000000,
            "time_created_text": "2024-03-09 16:00:00",
            "day": "2024-03-09",
            "provider": "openai",
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


def test_load_usage_from_db_reads_session_and_message_tables(tmp_path):
    db_path = tmp_path / "opencode.db"
    build_test_db(db_path, include_session=True, include_message=True)
    result = load_usage_from_db(db_path)
    assert result["summary"]["message_count"] == 1


def test_load_usage_from_db_continues_when_session_table_is_missing(tmp_path):
    db_path = tmp_path / "opencode.db"
    build_test_db(db_path, include_session=False, include_message=True)
    result = load_usage_from_db(db_path)
    assert result["by_session"][0]["session_title"] == ""


def test_load_usage_from_db_fails_when_message_table_is_missing(tmp_path):
    db_path = tmp_path / "opencode.db"
    build_test_db(db_path, include_session=True, include_message=False)
    with pytest.raises(Exception):
        load_usage_from_db(db_path)


def test_load_usage_from_db_treats_session_query_failure_as_recoverable(monkeypatch, tmp_path):
    db_path = tmp_path / "opencode.db"
    build_test_db(db_path, include_session=True, include_message=True)
    monkeypatch.setattr("opencode_token_app.data_loader.read_session_rows", lambda conn: (_ for _ in ()).throw(RuntimeError("session read failed")))
    result = load_usage_from_db(db_path)
    assert all("session_title" in row for row in result["by_session"])


def test_load_usage_from_db_treats_message_query_failure_as_non_recoverable(monkeypatch, tmp_path):
    db_path = tmp_path / "opencode.db"
    build_test_db(db_path, include_session=True, include_message=True)
    monkeypatch.setattr("opencode_token_app.data_loader.read_message_rows", lambda conn: (_ for _ in ()).throw(RuntimeError("message read failed")))
    with pytest.raises(Exception):
        load_usage_from_db(db_path)


def test_export_usage_csvs_writes_legacy_filenames(tmp_path):
    datasets = {
        "summary": {
            "message_count": 1,
            "total_tokens": 30,
            "input_tokens": 10,
            "output_tokens": 20,
            "reasoning_tokens": 0,
            "cache_read": 0,
            "cache_write": 0,
            "recorded_cost_total": 0.1,
        },
        "by_model": [{
            "provider": "openai",
            "model": "gpt-4.1-mini",
            "message_count": 1,
            "total_tokens": 30,
            "input_tokens": 10,
            "output_tokens": 20,
            "reasoning_tokens": 0,
            "cache_read": 0,
            "cache_write": 0,
            "recorded_cost_total": 0.1,
        }],
        "by_session": [{
            "session_id": "s1",
            "session_title": "Demo",
            "message_count": 1,
            "total_tokens": 30,
            "input_tokens": 10,
            "output_tokens": 20,
            "reasoning_tokens": 0,
            "cache_read": 0,
            "cache_write": 0,
            "recorded_cost_total": 0.1,
        }],
        "by_day": [{
            "day": "2024-03-09",
            "message_count": 1,
            "total_tokens": 30,
            "input_tokens": 10,
            "output_tokens": 20,
            "reasoning_tokens": 0,
            "cache_read": 0,
            "cache_write": 0,
            "recorded_cost_total": 0.1,
        }],
        "raw_messages": [{
            "message_id": "m1",
            "session_id": "s1",
            "session_title": "Demo",
            "time_created": 1710000000000,
            "time_created_text": "2024-03-09 16:00:00",
            "day": "2024-03-09",
            "provider": "openai",
            "model": "gpt-4.1-mini",
            "role": "assistant",
            "mode": "chat",
            "cost": None,
            "total_tokens": 30,
            "input_tokens": 10,
            "output_tokens": 20,
            "reasoning_tokens": 0,
            "cache_read": 0,
            "cache_write": 0,
        }],
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
