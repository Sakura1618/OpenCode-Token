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


def _pricing_mode_for_entry(price):
    return price.get("pricing_mode", "flat")


def _group_key_for_session_tiering(row):
    session_id = row.get("session_id")
    if session_id in (None, ""):
        return None
    return (canonical_model_key(row.get("provider", ""), row.get("model", "")), session_id)


def _mark_unpriced_row(new_row, price_source):
    new_row.update({
        "estimated_cost": None,
        "estimated_cache_read_cost": None,
        "estimated_cache_write_cost": None,
        "price_status": "unpriced",
        "price_source": price_source,
        "pricing_mode": new_row.get("pricing_mode", ""),
        "pricing_tier": new_row.get("pricing_tier", ""),
    })


def _mark_priced_row(new_row, estimated_cost, estimated_cache_read_cost, estimated_cache_write_cost, price, pricing_mode, pricing_tier):
    new_row.update({
        "estimated_cost": estimated_cost,
        "estimated_cache_read_cost": estimated_cache_read_cost,
        "estimated_cache_write_cost": estimated_cache_write_cost,
        "price_status": "priced",
        "price_source": price.get("price_source", "bundled"),
        "pricing_mode": pricing_mode,
        "pricing_tier": pricing_tier,
    })


def _validate_session_tiering(price):
    config = price.get("session_tiering") or {}
    if config.get("scope") != "session":
        return False
    if not config.get("metric"):
        return False
    if config.get("trigger") != "any_row":
        return False
    if config.get("comparison") != "gt":
        return False
    try:
        float(config["threshold"])
    except (KeyError, TypeError, ValueError):
        return False
    tiers = price.get("tiers", {})
    if config.get("default_tier") not in tiers:
        return False
    if config.get("triggered_tier") not in tiers:
        return False
    return True


def _rate_set_is_complete(rate_set):
    return bool(rate_set) and "input_price_per_million" in rate_set and "output_price_per_million" in rate_set


def _coerce_metric_value(row, field_name):
    value = row.get(field_name, 0)
    if value in (None, ""):
        return 0
    return float(value)


def derive_session_pricing_context(rows, price_map):
    grouped_rows = {}
    invalid_groups = set()
    for row in rows:
        key = canonical_model_key(row.get("provider", ""), row.get("model", ""))
        price = price_map.get(key)
        if not price or _pricing_mode_for_entry(price) != "session_tiered":
            continue
        if not _validate_session_tiering(price):
            group_key = _group_key_for_session_tiering(row)
            if group_key is not None:
                invalid_groups.add(group_key)
            continue
        group_key = _group_key_for_session_tiering(row)
        if group_key is None:
            continue
        grouped_rows.setdefault(group_key, []).append(row)

    resolved = {}
    for group_key, group in grouped_rows.items():
        if group_key in invalid_groups:
            continue
        price = price_map[group_key[0]]
        config = price["session_tiering"]
        threshold = float(config["threshold"])
        triggered = False
        for row in group:
            try:
                metric_value = _coerce_metric_value(row, config["metric"])
            except (TypeError, ValueError):
                invalid_groups.add(group_key)
                triggered = False
                break
            if metric_value > threshold:
                triggered = True
        if group_key not in invalid_groups:
            resolved[group_key] = config["triggered_tier"] if triggered else config["default_tier"]
    return resolved, invalid_groups


def _active_rate_set_for_row(row, price, session_context, invalid_groups):
    mode = _pricing_mode_for_entry(price)
    if mode == "flat":
        return mode, "", price
    group_key = _group_key_for_session_tiering(row)
    if group_key is None or group_key in invalid_groups:
        return mode, "", None
    tier_name = session_context.get(group_key)
    if not tier_name:
        return mode, "", None
    return mode, tier_name, price.get("tiers", {}).get(tier_name)


def enrich_raw_rows_with_pricing(rows, price_map):
    session_context, invalid_groups = derive_session_pricing_context(rows, price_map)
    enriched = []
    for row in rows:
        key = canonical_model_key(row.get("provider", ""), row.get("model", ""))
        price = price_map.get(key)
        new_row = dict(row)
        if not price:
            _mark_unpriced_row(new_row, "missing")
            enriched.append(new_row)
            continue

        pricing_mode, pricing_tier, rate_set = _active_rate_set_for_row(row, price, session_context, invalid_groups)
        new_row["pricing_mode"] = pricing_mode
        new_row["pricing_tier"] = pricing_tier
        if not _rate_set_is_complete(rate_set):
            _mark_unpriced_row(new_row, price.get("price_source", "bundled"))
            enriched.append(new_row)
            continue
        assert rate_set is not None

        estimated_cache_read_cost = None if "cache_read_price_per_million" not in rate_set else round((row.get("cache_read", 0) / 1_000_000) * rate_set.get("cache_read_price_per_million", 0), 10)
        estimated_cache_write_cost = None if "cache_write_price_per_million" not in rate_set else round((row.get("cache_write", 0) / 1_000_000) * rate_set.get("cache_write_price_per_million", 0), 10)
        estimated_cost = (
            (row.get("input_tokens", 0) / 1_000_000) * rate_set["input_price_per_million"]
            + (row.get("output_tokens", 0) / 1_000_000) * rate_set["output_price_per_million"]
            + (estimated_cache_read_cost or 0)
            + (estimated_cache_write_cost or 0)
        )
        estimated_cost = round(estimated_cost, 10)
        _mark_priced_row(
            new_row,
            estimated_cost,
            estimated_cache_read_cost,
            estimated_cache_write_cost,
            price,
            pricing_mode,
            pricing_tier,
        )
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
