import json
from pathlib import Path

from opencode_token_app.data_loader import canonical_model_key


BUNDLED_PRICES_PATH = Path(__file__).with_name("prices.json")


def normalize_price_map(raw_map):
    normalized = {}
    for key, value in raw_map.items():
        entry = dict(value)
        provider = entry.get("provider") or key.split(":", 1)[0]
        model = entry.get("model") or key.split(":", 1)[1]
        entry["provider"] = provider
        entry["model"] = model
        normalized[canonical_model_key(provider, model)] = entry
    return normalized


def merge_price_maps(base, override):
    merged = {key: {**value, "price_source": "bundled"} for key, value in base.items()}
    for key, value in override.items():
        merged[key] = {**merged.get(key, {}), **value, "price_source": "override"}
    return merged


def load_price_map(bundled_path, local_override_path=None):
    bundled = {}
    override = {}
    if bundled_path and Path(bundled_path).exists():
        bundled = normalize_price_map(json.loads(Path(bundled_path).read_text(encoding="utf-8")))
    if local_override_path and Path(local_override_path).exists():
        override = normalize_price_map(json.loads(Path(local_override_path).read_text(encoding="utf-8")))
    return merge_price_maps(bundled, override)


def find_local_override_path(entry_path):
    if not entry_path:
        return None
    path = Path(entry_path)
    candidate = path.with_name("prices.local.json")
    return candidate if candidate.exists() else None


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
            new_row.update({
                "estimated_cost": None,
                "estimated_cache_read_cost": None,
                "estimated_cache_write_cost": None,
                "price_status": "unpriced",
                "price_source": "missing",
            })
        else:
            estimated_cache_read_cost = None if "cache_read_price_per_million" not in price else round((row.get("cache_read", 0) / 1_000_000) * price.get("cache_read_price_per_million", 0), 10)
            estimated_cache_write_cost = None if "cache_write_price_per_million" not in price else round((row.get("cache_write", 0) / 1_000_000) * price.get("cache_write_price_per_million", 0), 10)
            estimated_cost = (
                (row.get("input_tokens", 0) / 1_000_000) * price["input_price_per_million"]
                + (row.get("output_tokens", 0) / 1_000_000) * price["output_price_per_million"]
                + (estimated_cache_read_cost or 0)
                + (estimated_cache_write_cost or 0)
            )
            estimated_cost = round(estimated_cost, 10)
            new_row.update({
                "estimated_cost": estimated_cost,
                "estimated_cache_read_cost": estimated_cache_read_cost,
                "estimated_cache_write_cost": estimated_cache_write_cost,
                "price_status": "priced",
                "price_source": price.get("price_source", "bundled"),
            })
        enriched.append(new_row)
    return enriched


def _overlay_defaults(row):
    row.setdefault("estimated_cost_total", 0)
    row.setdefault("priced_message_count", 0)
    row.setdefault("unpriced_message_count", 0)


def apply_pricing_overlays(datasets):
    summary = dict(datasets["summary"])
    _overlay_defaults(summary)
    by_model = [dict(row) for row in datasets["by_model"]]
    by_session = [dict(row) for row in datasets["by_session"]]
    by_day = [dict(row) for row in datasets["by_day"]]
    for row in by_model + by_session + by_day:
        _overlay_defaults(row)

    model_index = {(row["provider"], row["model"]): row for row in by_model}
    session_index = {row["session_id"]: row for row in by_session}
    day_index = {row["day"]: row for row in by_day}

    for row in datasets["raw_messages"]:
        status = row.get("price_status")
        estimated_cost = row.get("estimated_cost")
        if estimated_cost is not None:
            summary["estimated_cost_total"] += estimated_cost
        if status == "priced":
            summary["priced_message_count"] += 1
        else:
            summary["unpriced_message_count"] += 1

        model_row = model_index.get((canonical_model_key(row.get("provider", ""), row.get("model", "")).split(":", 1)[0], canonical_model_key(row.get("provider", ""), row.get("model", "")).split(":", 1)[1]))
        # use normalized provider/model directly if available
        if model_row is None:
            model_row = model_index.get((row.get("provider"), row.get("model")))
        session_row = session_index.get(row.get("session_id"))
        day_row = day_index.get(row.get("day"))
        for target in [model_row, session_row, day_row]:
            if not target:
                continue
            if estimated_cost is not None:
                target["estimated_cost_total"] += estimated_cost
            if status == "priced":
                target["priced_message_count"] += 1
            else:
                target["unpriced_message_count"] += 1

    return {
        **datasets,
        "summary": summary,
        "by_model": by_model,
        "by_session": by_session,
        "by_day": by_day,
    }


def price_loaded_usage(datasets, entry_path=None):
    price_map = load_effective_price_map(entry_path)
    raw_messages = enrich_raw_rows_with_pricing(datasets["raw_messages"], price_map)
    return apply_pricing_overlays({**datasets, "raw_messages": raw_messages})
