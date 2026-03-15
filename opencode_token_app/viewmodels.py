def _format_cost(value):
    if value is None:
        return ""
    return f"{value:.2f}"


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
    summary = datasets["summary"]
    return {
        "cards": summary,
        "daily_rows": datasets.get("by_day", []),
    }


def _decorate_aggregate_rows(rows):
    decorated = []
    for row in rows:
        new_row = dict(row)
        new_row["estimated_cost_display"] = _format_cost(row.get("estimated_cost_total"))
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
        new_row["estimated_cost_display"] = _format_cost(row.get("estimated_cost"))
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
