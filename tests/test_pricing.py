import json
from pathlib import Path

from export_opencode_tokens import main
from opencode_token_app.pricing import (
    apply_pricing_overlays,
    enrich_raw_rows_with_pricing,
    find_local_override_path,
    load_effective_price_map,
    load_price_map,
    merge_price_maps,
    normalize_price_map,
    price_loaded_usage,
)


def price_map_for_gpt54():
    return {
        "openai:gpt-5.4": {
            "provider": "openai",
            "model": "gpt-5.4",
            "pricing_mode": "session_tiered",
            "session_tiering": {
                "scope": "session",
                "metric": "input_tokens",
                "threshold": 272000,
                "comparison": "gt",
                "trigger": "any_row",
                "default_tier": "short_context",
                "triggered_tier": "long_context",
            },
            "tiers": {
                "short_context": {
                    "input_price_per_million": 2.5,
                    "cache_read_price_per_million": 0.25,
                    "output_price_per_million": 15.0,
                },
                "long_context": {
                    "input_price_per_million": 5.0,
                    "cache_read_price_per_million": 0.5,
                    "output_price_per_million": 22.5,
                },
            },
        }
    }


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


def test_enrich_raw_rows_with_flat_pricing_sets_flat_metadata_and_existing_costs():
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

    assert enriched[0]["estimated_cost"] == 1.02
    assert enriched[0]["pricing_mode"] == "flat"
    assert enriched[0]["pricing_tier"] == ""


def test_enrich_raw_rows_with_session_tiered_pricing_uses_short_context_rates():
    rows = [
        {
            "session_id": "s1",
            "provider": "OpenAI",
            "model": "gpt-5.4",
            "input_tokens": 200000,
            "output_tokens": 100000,
            "cache_read": 100000,
            "cache_write": 0,
        }
    ]

    enriched = enrich_raw_rows_with_pricing(rows, price_map_for_gpt54())

    assert enriched[0]["estimated_cost"] == 2.025
    assert enriched[0]["pricing_mode"] == "session_tiered"
    assert enriched[0]["pricing_tier"] == "short_context"


def test_enrich_raw_rows_with_session_tiered_pricing_reprices_full_session_when_later_row_crosses_threshold():
    rows = [
        {
            "session_id": "s1",
            "provider": "OpenAI",
            "model": "gpt-5.4",
            "input_tokens": 200000,
            "output_tokens": 100000,
            "cache_read": 100000,
            "cache_write": 0,
        },
        {
            "session_id": "s1",
            "provider": "OpenAI",
            "model": "gpt-5.4",
            "input_tokens": 300000,
            "output_tokens": 0,
            "cache_read": 0,
            "cache_write": 0,
        },
    ]

    enriched = enrich_raw_rows_with_pricing(rows, price_map_for_gpt54())

    assert enriched[0]["estimated_cost"] == 3.3
    assert enriched[0]["pricing_tier"] == "long_context"
    assert enriched[1]["pricing_tier"] == "long_context"


def test_session_tiered_pricing_keeps_exact_threshold_in_short_context():
    rows = [
        {
            "session_id": "s1",
            "provider": "OpenAI",
            "model": "gpt-5.4",
            "input_tokens": 272000,
            "output_tokens": 0,
            "cache_read": 0,
            "cache_write": 0,
        }
    ]

    enriched = enrich_raw_rows_with_pricing(rows, price_map_for_gpt54())

    assert enriched[0]["pricing_tier"] == "short_context"


def test_session_tiered_pricing_does_not_leak_between_sessions():
    rows = [
        {"session_id": "s1", "provider": "OpenAI", "model": "gpt-5.4", "input_tokens": 300000, "output_tokens": 0, "cache_read": 0, "cache_write": 0},
        {"session_id": "s2", "provider": "OpenAI", "model": "gpt-5.4", "input_tokens": 200000, "output_tokens": 0, "cache_read": 0, "cache_write": 0},
    ]

    enriched = enrich_raw_rows_with_pricing(rows, price_map_for_gpt54())

    assert enriched[0]["pricing_tier"] == "long_context"
    assert enriched[1]["pricing_tier"] == "short_context"


def test_session_tiered_pricing_marks_row_unpriced_when_session_id_missing():
    rows = [{"provider": "OpenAI", "model": "gpt-5.4", "input_tokens": 200000, "output_tokens": 0, "cache_read": 0, "cache_write": 0}]

    enriched = enrich_raw_rows_with_pricing(rows, price_map_for_gpt54())

    assert enriched[0]["price_status"] == "unpriced"


def test_session_tiered_pricing_treats_missing_metric_as_zero():
    rows = [{"session_id": "s1", "provider": "OpenAI", "model": "gpt-5.4", "output_tokens": 0, "cache_read": 0, "cache_write": 0}]

    enriched = enrich_raw_rows_with_pricing(rows, price_map_for_gpt54())

    assert enriched[0]["pricing_tier"] == "short_context"


def test_session_tiered_pricing_marks_row_unpriced_for_non_numeric_metric():
    rows = [{"session_id": "s1", "provider": "OpenAI", "model": "gpt-5.4", "input_tokens": "abc", "output_tokens": 0, "cache_read": 0, "cache_write": 0}]

    enriched = enrich_raw_rows_with_pricing(rows, price_map_for_gpt54())

    assert enriched[0]["price_status"] == "unpriced"


def test_session_tiered_pricing_marks_row_unpriced_for_unsupported_config():
    rows = [{"session_id": "s1", "provider": "OpenAI", "model": "gpt-5.4", "input_tokens": 1, "output_tokens": 0, "cache_read": 0, "cache_write": 0}]
    price_map = {
        "openai:gpt-5.4": {
            "provider": "openai",
            "model": "gpt-5.4",
            "pricing_mode": "session_tiered",
            "session_tiering": {"scope": "session", "metric": "input_tokens", "threshold": 272000, "comparison": "gte", "trigger": "any_row", "default_tier": "short_context", "triggered_tier": "long_context"},
            "tiers": {
                "short_context": {"input_price_per_million": 2.5, "output_price_per_million": 15.0},
                "long_context": {"input_price_per_million": 5.0, "output_price_per_million": 22.5},
            },
        }
    }

    enriched = enrich_raw_rows_with_pricing(rows, price_map)

    assert enriched[0]["price_status"] == "unpriced"


def test_session_tiered_pricing_marks_row_unpriced_for_missing_metric_config():
    rows = [{"session_id": "s1", "provider": "OpenAI", "model": "gpt-5.4", "input_tokens": 1, "output_tokens": 0, "cache_read": 0, "cache_write": 0}]
    price_map = {
        "openai:gpt-5.4": {
            "provider": "openai",
            "model": "gpt-5.4",
            "pricing_mode": "session_tiered",
            "session_tiering": {"scope": "session", "threshold": 272000, "comparison": "gt", "trigger": "any_row", "default_tier": "short_context", "triggered_tier": "long_context"},
            "tiers": {
                "short_context": {"input_price_per_million": 2.5, "output_price_per_million": 15.0},
                "long_context": {"input_price_per_million": 5.0, "output_price_per_million": 22.5},
            },
            "price_source": "override",
        }
    }

    enriched = enrich_raw_rows_with_pricing(rows, price_map)

    assert enriched[0]["price_status"] == "unpriced"
    assert enriched[0]["price_source"] == "override"


def test_session_tiered_pricing_marks_row_unpriced_for_non_numeric_threshold():
    rows = [{"session_id": "s1", "provider": "OpenAI", "model": "gpt-5.4", "input_tokens": 1, "output_tokens": 0, "cache_read": 0, "cache_write": 0}]
    price_map = {
        "openai:gpt-5.4": {
            "provider": "openai",
            "model": "gpt-5.4",
            "pricing_mode": "session_tiered",
            "session_tiering": {"scope": "session", "metric": "input_tokens", "threshold": "abc", "comparison": "gt", "trigger": "any_row", "default_tier": "short_context", "triggered_tier": "long_context"},
            "tiers": {
                "short_context": {"input_price_per_million": 2.5, "output_price_per_million": 15.0},
                "long_context": {"input_price_per_million": 5.0, "output_price_per_million": 22.5},
            },
        }
    }

    enriched = enrich_raw_rows_with_pricing(rows, price_map)

    assert enriched[0]["price_status"] == "unpriced"


def test_session_tiered_pricing_marks_row_unpriced_when_required_rate_field_missing():
    rows = [{"session_id": "s1", "provider": "OpenAI", "model": "gpt-5.4", "input_tokens": 1, "output_tokens": 0, "cache_read": 0, "cache_write": 0}]
    price_map = {
        "openai:gpt-5.4": {
            "provider": "openai",
            "model": "gpt-5.4",
            "pricing_mode": "session_tiered",
            "session_tiering": {"scope": "session", "metric": "input_tokens", "threshold": 272000, "comparison": "gt", "trigger": "any_row", "default_tier": "short_context", "triggered_tier": "long_context"},
            "tiers": {
                "short_context": {"input_price_per_million": 2.5},
                "long_context": {"input_price_per_million": 5.0, "output_price_per_million": 22.5},
            },
        }
    }

    enriched = enrich_raw_rows_with_pricing(rows, price_map)

    assert enriched[0]["price_status"] == "unpriced"


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


def test_bundled_prices_json_contains_session_tiered_gpt54_config():
    data = json.loads(Path("opencode_token_app/prices.json").read_text(encoding="utf-8"))

    entry = data["openai:gpt-5.4"]

    assert entry["pricing_mode"] == "session_tiered"
    assert entry["session_tiering"]["threshold"] == 272000
    assert entry["tiers"]["short_context"]["input_price_per_million"] == 2.5
    assert entry["tiers"]["long_context"]["output_price_per_million"] == 22.5


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


def test_price_loaded_usage_applies_bundled_gpt54_session_tier_to_export_data(monkeypatch):
    monkeypatch.setattr("opencode_token_app.pricing.BUNDLED_PRICES_PATH", Path("opencode_token_app/prices.json"))
    datasets = {
        "summary": {"message_count": 2},
        "by_model": [{"provider": "openai", "model": "gpt-5.4"}],
        "by_session": [{"session_id": "s1", "session_title": "Demo"}],
        "by_day": [{"day": "2026-03-18"}],
        "raw_messages": [
            {"session_id": "s1", "day": "2026-03-18", "provider": "openai", "model": "gpt-5.4", "input_tokens": 200000, "output_tokens": 100000, "cache_read": 100000, "cache_write": 0, "reasoning_tokens": 0},
            {"session_id": "s1", "day": "2026-03-18", "provider": "openai", "model": "gpt-5.4", "input_tokens": 300000, "output_tokens": 0, "cache_read": 0, "cache_write": 0, "reasoning_tokens": 0},
        ],
    }

    priced = price_loaded_usage(datasets)

    assert priced["raw_messages"][0]["pricing_tier"] == "long_context"
    assert priced["summary"]["estimated_cost_total"] == 4.8


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
