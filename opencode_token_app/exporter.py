import csv
from pathlib import Path


CSV_OUTPUTS = {
    "summary": ("summary.csv", [
        "message_count",
        "total_tokens",
        "input_tokens",
        "output_tokens",
        "reasoning_tokens",
        "cache_read",
        "cache_write",
        "recorded_cost_total",
        "estimated_cost_total",
        "priced_message_count",
        "unpriced_message_count",
    ]),
    "by_model": ("by_model.csv", [
        "provider",
        "model",
        "message_count",
        "total_tokens",
        "input_tokens",
        "output_tokens",
        "reasoning_tokens",
        "cache_read",
        "cache_write",
        "recorded_cost_total",
        "estimated_cost_total",
        "priced_message_count",
        "unpriced_message_count",
    ]),
    "by_session": ("by_session.csv", [
        "session_id",
        "session_title",
        "message_count",
        "total_tokens",
        "input_tokens",
        "output_tokens",
        "reasoning_tokens",
        "cache_read",
        "cache_write",
        "recorded_cost_total",
        "estimated_cost_total",
        "priced_message_count",
        "unpriced_message_count",
    ]),
    "by_day": ("by_day.csv", [
        "day",
        "message_count",
        "total_tokens",
        "input_tokens",
        "output_tokens",
        "reasoning_tokens",
        "cache_read",
        "cache_write",
        "recorded_cost_total",
        "estimated_cost_total",
        "priced_message_count",
        "unpriced_message_count",
    ]),
    "raw_messages": ("raw_messages_with_tokens.csv", [
        "message_id",
        "session_id",
        "session_title",
        "time_created",
        "time_created_text",
        "day",
        "provider",
        "model",
        "role",
        "mode",
        "cost",
        "estimated_cost",
        "estimated_cache_read_cost",
        "estimated_cache_write_cost",
        "price_status",
        "price_source",
        "total_tokens",
        "input_tokens",
        "output_tokens",
        "reasoning_tokens",
        "cache_read",
        "cache_write",
    ]),
}


def _write_csv(path: Path, rows, fieldnames):
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _raw_message_fieldnames(rows, fieldnames):
    resolved = list(fieldnames)
    for row in rows:
        for key in row:
            if key not in resolved:
                resolved.append(key)
    return resolved


def export_usage_csvs(out_dir, datasets):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, (filename, fieldnames) in CSV_OUTPUTS.items():
        rows = datasets[name]
        if isinstance(rows, dict):
            rows = [rows]
        if name == "raw_messages":
            fieldnames = _raw_message_fieldnames(rows, fieldnames)
        _write_csv(out_dir / filename, rows, fieldnames)
    return out_dir
