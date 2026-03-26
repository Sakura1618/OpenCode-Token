import re
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


def _normalize_text(value: Any) -> str:
    value = (value or "").strip().lower()
    return re.sub(r"\s+", " ", value)


def canonical_model_key(provider: str, model: str) -> str:
    return f"{_normalize_text(provider)}:{_normalize_text(model)}"


def format_ts_ms_local(ts):
    ts = int(ts or 0)
    if ts <= 0:
        return ""
    return datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d %H:%M:%S")


def safe_json_loads(text):
    if text is None:
        return {}
    if isinstance(text, dict):
        return text
    try:
        return json.loads(text)
    except Exception:
        return {}


def get_nested(d: Any, *keys: Any, default: Any = 0) -> Any:
    cur = d
    for key in keys:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur if cur is not None else default


def to_int(value, default=0):
    try:
        if value is None or value == "":
            return default
        return int(value)
    except Exception:
        try:
            return int(float(value))
        except Exception:
            return default


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
        "role": get_nested(data, "role", default="") or "",
        "mode": get_nested(data, "mode", default="") or "",
        "cost": parse_recorded_cost(get_nested(data, "cost", default=None)),
        "total_tokens": total_tokens,
        "input_tokens": to_int(get_nested(data, "tokens", "input", default=0)),
        "output_tokens": to_int(get_nested(data, "tokens", "output", default=0)),
        "reasoning_tokens": to_int(get_nested(data, "tokens", "reasoning", default=0)),
        "cache_read": to_int(get_nested(data, "tokens", "cache", "read", default=0)),
        "cache_write": to_int(get_nested(data, "tokens", "cache", "write", default=0)),
    }


def _empty_summary() -> dict[str, Any]:
    return {
        "message_count": 0,
        "total_tokens": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "reasoning_tokens": 0,
        "cache_read": 0,
        "cache_write": 0,
        "recorded_cost_total": 0.0,
    }


def _update_aggregate(target: dict[str, Any], row: dict[str, Any]) -> None:
    target["message_count"] += 1
    target["total_tokens"] += row["total_tokens"]
    target["input_tokens"] += row["input_tokens"]
    target["output_tokens"] += row["output_tokens"]
    target["reasoning_tokens"] += row["reasoning_tokens"]
    target["cache_read"] += row["cache_read"]
    target["cache_write"] += row["cache_write"]
    if row["cost"] is not None:
        target["recorded_cost_total"] += row["cost"]


def aggregate_usage(raw_rows):
    summary = _empty_summary()
    by_model: dict[tuple[str, str], dict[str, Any]] = {}
    by_session: dict[str, dict[str, Any]] = {}
    by_day: dict[str, dict[str, Any]] = {}

    normalized_rows = []
    for raw_row in raw_rows:
        row = dict(raw_row)
        row["provider"] = _normalize_text(row.get("provider", ""))
        row["model"] = _normalize_text(row.get("model", ""))
        normalized_rows.append(row)
        _update_aggregate(summary, row)

        model_key = (row["provider"], row["model"])
        if model_key not in by_model:
            by_model[model_key] = {
                "provider": row["provider"],
                "model": row["model"],
                **_empty_summary(),
            }
        _update_aggregate(by_model[model_key], row)

        if row["session_id"] not in by_session:
            by_session[row["session_id"]] = {
                "session_id": row["session_id"],
                "session_title": row["session_title"],
                **_empty_summary(),
            }
        _update_aggregate(by_session[row["session_id"]], row)

        if row["day"] not in by_day:
            by_day[row["day"]] = {"day": row["day"], **_empty_summary()}
        _update_aggregate(by_day[row["day"]], row)

    normalized_rows.sort(key=lambda item: (item["time_created"], item["message_id"]))
    by_model_rows = sorted(by_model.values(), key=lambda item: item["total_tokens"], reverse=True)
    by_session_rows = sorted(by_session.values(), key=lambda item: item["total_tokens"], reverse=True)
    by_day_rows = sorted(by_day.values(), key=lambda item: item["day"])

    return {
        "summary": summary,
        "by_model": by_model_rows,
        "by_session": by_session_rows,
        "by_day": by_day_rows,
        "raw_messages": normalized_rows,
    }


def read_session_rows(conn: sqlite3.Connection):
    cur = conn.cursor()
    cur.execute("SELECT id, title FROM session")
    return cur.fetchall()


def read_message_rows(conn: sqlite3.Connection):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, session_id, time_created, data
        FROM message
        ORDER BY time_created ASC
        """
    )
    return cur.fetchall()


def load_usage_from_db(db_path):
    path = Path(db_path)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    try:
        session_title_map = {}
        try:
            for row in read_session_rows(conn):
                session_title_map[row["id"]] = row["title"] or ""
        except Exception:
            session_title_map = {}

        message_rows = read_message_rows(conn)
        raw_rows = []
        for row in message_rows:
            built = build_raw_message_row(row, session_title_map)
            if built is not None:
                raw_rows.append(built)
        return aggregate_usage(raw_rows)
    finally:
        conn.close()
