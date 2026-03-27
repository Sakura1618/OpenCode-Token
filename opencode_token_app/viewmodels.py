def _format_cost(value, currency="USD"):
    if value is None:
        return ""
    if currency == "CNY":
        return f"¥{value:.2f} CNY"
    if currency == "USD":
        return f"${value:.2f} USD"
    if currency:
        return f"{value:.2f} {currency}"
    return f"{value:.2f}"


def _format_cost_totals(totals, fallback_value=None, fallback_currency="USD"):
    if isinstance(totals, dict) and totals:
        formatted_parts = [
            _format_cost(value, currency)
            for currency, value in sorted(totals.items())
        ]
        return " / ".join(part for part in formatted_parts if part)
    return _format_cost(fallback_value, fallback_currency)


def format_token_millions(value):
    try:
        tokens = float(value)
    except (TypeError, ValueError):
        tokens = 0.0
    return f"{tokens / 1_000_000:.2f}M"


def _price_status_label_from_counts(priced_count, unpriced_count):
    if unpriced_count:
        return "未定价"
    if priced_count:
        return "已定价"
    return ""


def _price_status_label(status):
    if status == "priced":
        return "已定价"
    if status == "unpriced":
        return "未定价"
    return ""


def build_overview_viewmodel(datasets):
    summary = dict(datasets["summary"])
    for field in ("total_tokens", "input_tokens", "output_tokens", "cache_read", "cache_write", "reasoning_tokens"):
        summary[f"{field}_display"] = format_token_millions(summary.get(field))
    summary["estimated_cost_total_display"] = _format_cost_totals(
        summary.get("estimated_cost_totals"),
        summary.get("estimated_cost_total"),
    )
    summary["recorded_cost_total_display"] = _format_cost(summary.get("recorded_cost_total"))
    return {
        "cards": summary,
        "daily_rows": _decorate_aggregate_rows(datasets.get("by_day", [])),
    }


def _decorate_aggregate_rows(rows):
    decorated = []
    for row in rows:
        new_row = dict(row)
        new_row["total_tokens_display"] = format_token_millions(row.get("total_tokens"))
        new_row["input_tokens_display"] = format_token_millions(row.get("input_tokens"))
        new_row["output_tokens_display"] = format_token_millions(row.get("output_tokens"))
        new_row["cache_read_display"] = format_token_millions(row.get("cache_read"))
        new_row["cache_write_display"] = format_token_millions(row.get("cache_write"))
        new_row["estimated_cost_display"] = _format_cost_totals(
            row.get("estimated_cost_totals"),
            row.get("estimated_cost_total"),
        )
        new_row["recorded_cost_display"] = _format_cost(row.get("recorded_cost_total"))
        new_row["price_status_label"] = _price_status_label_from_counts(
            row.get("priced_message_count", 0),
            row.get("unpriced_message_count", 0),
        )
        decorated.append(new_row)
    return decorated


def _decorate_raw_rows(rows):
    decorated = []
    for row in rows:
        new_row = dict(row)
        new_row["total_tokens_display"] = format_token_millions(row.get("total_tokens"))
        new_row["input_tokens_display"] = format_token_millions(row.get("input_tokens"))
        new_row["output_tokens_display"] = format_token_millions(row.get("output_tokens"))
        new_row["cache_read_display"] = format_token_millions(row.get("cache_read"))
        new_row["cache_write_display"] = format_token_millions(row.get("cache_write"))
        new_row["estimated_cost_display"] = _format_cost(row.get("estimated_cost"), row.get("estimated_cost_currency") or "USD")
        new_row["recorded_cost_display"] = _format_cost(row.get("cost"))
        new_row["price_status_label"] = _price_status_label(row.get("price_status"))
        decorated.append(new_row)
    return decorated


def build_application_viewmodels(datasets):
    return {
        "overview": build_overview_viewmodel(datasets),
        "models": _decorate_aggregate_rows(datasets.get("by_model", [])),
        "days": _decorate_aggregate_rows(datasets.get("by_day", [])),
        "sessions": _decorate_aggregate_rows(datasets.get("by_session", [])),
        "raw_messages": _decorate_raw_rows(datasets.get("raw_messages", [])),
    }
