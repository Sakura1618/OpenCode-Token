from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from opencode_token_app import charts
from opencode_token_app import gui as gui_module
from opencode_token_app.gui import ChartRefreshError, OpenCodeTokenApp, default_db_path
from opencode_token_app.viewmodels import (
    build_application_viewmodels,
    build_overview_viewmodel,
    format_token_millions,
)


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


def test_overview_viewmodel_adds_token_display_fields():
    datasets = {
        "summary": {
            "total_tokens": 1234567,
            "input_tokens": 400000,
            "output_tokens": 830000,
            "reasoning_tokens": 4567,
            "estimated_cost_total": 1.5,
            "recorded_cost_total": 1.2,
        },
        "by_day": [{"day": "2024-03-09", "total_tokens": 1234567}],
    }

    vm = build_overview_viewmodel(datasets)

    assert vm["cards"]["total_tokens"] == 1234567
    assert vm["cards"]["input_tokens"] == 400000
    assert vm["cards"]["output_tokens"] == 830000
    assert vm["cards"]["reasoning_tokens"] == 4567
    assert vm["cards"]["total_tokens_display"] == "1.23M"
    assert vm["cards"]["input_tokens_display"] == "0.40M"
    assert vm["cards"]["output_tokens_display"] == "0.83M"
    assert vm["cards"]["reasoning_tokens_display"] == "0.00M"
    assert vm["daily_rows"][0]["total_tokens"] == 1234567
    assert vm["daily_rows"][0]["total_tokens_display"] == "1.23M"


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


def test_build_application_viewmodels_adds_display_fields_for_visible_token_columns():
    datasets = {
        "summary": {"total_tokens": 0, "input_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0},
        "by_model": [{"provider": "OpenAI", "model": "gpt-4.1-mini", "total_tokens": 1234567}],
        "by_day": [{"day": "2024-03-09", "total_tokens": 400000}],
        "by_session": [{"session_id": "s1", "session_title": "Demo", "total_tokens": 830000}],
        "raw_messages": [{"day": "2024-03-09", "provider": "OpenAI", "model": "gpt-4.1-mini", "total_tokens": 4567, "input_tokens": 400000, "output_tokens": 830000}],
    }

    vm = build_application_viewmodels(datasets)

    assert vm["models"][0]["total_tokens"] == 1234567
    assert vm["models"][0]["total_tokens_display"] == "1.23M"
    assert vm["days"][0]["total_tokens"] == 400000
    assert vm["days"][0]["total_tokens_display"] == "0.40M"
    assert vm["sessions"][0]["total_tokens"] == 830000
    assert vm["sessions"][0]["total_tokens_display"] == "0.83M"
    assert vm["raw_messages"][0]["total_tokens"] == 4567
    assert vm["raw_messages"][0]["total_tokens_display"] == "0.00M"
    assert vm["raw_messages"][0]["input_tokens"] == 400000
    assert vm["raw_messages"][0]["input_tokens_display"] == "0.40M"
    assert vm["raw_messages"][0]["output_tokens"] == 830000
    assert vm["raw_messages"][0]["output_tokens_display"] == "0.83M"


def test_build_application_viewmodels_marks_unpriced_rows():
    datasets = {
        "summary": {"total_tokens": 100, "input_tokens": 40, "output_tokens": 60, "reasoning_tokens": 10, "estimated_cost_total": 1.5, "recorded_cost_total": 1.2},
        "by_model": [{"provider": "openai", "model": f"m{i}", "total_tokens": i, "estimated_cost_total": i, "recorded_cost_total": i / 2, "priced_message_count": 1, "unpriced_message_count": 0} for i in range(20, 0, -1)],
        "by_day": [{"day": "2024-03-09", "total_tokens": 100, "estimated_cost_total": 1.5, "recorded_cost_total": 1.2}],
        "by_session": [{"session_id": "s1", "session_title": "Demo", "total_tokens": 100, "estimated_cost_total": 1.5, "recorded_cost_total": 1.2, "message_count": 1}],
        "raw_messages": [{"day": "2024-03-09", "provider": "openai", "model": "m1", "price_status": "unpriced"}],
    }

    vm = build_application_viewmodels(datasets)

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


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, "0.00M"),
        ("bad", "0.00M"),
        (1234567, "1.23M"),
    ],
)
def test_token_display_formatter(value, expected):
    assert format_token_millions(value) == expected


def test_default_db_path_uses_userprofile(monkeypatch):
    monkeypatch.setenv("USERPROFILE", r"C:\Users\demo")
    assert default_db_path() == Path(r"C:\Users\demo\.local\share\opencode\opencode.db")


def test_create_figure_returns_none_when_matplotlib_unavailable(monkeypatch):
    monkeypatch.setattr(charts, "Figure", None)

    assert charts.create_figure() is None


def test_attach_canvas_returns_none_when_tk_canvas_unavailable(monkeypatch):
    monkeypatch.setattr(charts, "FigureCanvasTkAgg", None)

    assert charts.attach_canvas(object(), master=object()) is None


def test_chart_helpers_no_op_when_figure_unavailable():
    charts.plot_line_chart(None, title="Daily Tokens", labels=[], values=[])
    charts.plot_horizontal_bar_chart(None, title="Top Models", labels=[], values=[])
    charts.plot_pie_chart(None, title="Token Composition", labels=[], values=[])


@pytest.mark.skipif(charts.Figure is None, reason="matplotlib unavailable")
def test_line_chart_renders_empty_state_when_no_values():
    figure = charts.create_figure()
    assert figure is not None

    charts.plot_line_chart(figure, title="Daily Tokens", labels=[], values=[])

    axis = figure.axes[0]
    assert axis.get_title() == "Daily Tokens"
    assert axis.texts[0].get_text() == "No data"


@pytest.mark.skipif(charts.Figure is None, reason="matplotlib unavailable")
def test_bar_chart_uses_expected_labels_and_values():
    figure = charts.create_figure()
    assert figure is not None

    charts.plot_horizontal_bar_chart(
        figure,
        title="Top Models",
        labels=["openai/gpt-4.1-mini", "openai/o3"],
        values=[100, 80],
    )

    axis = figure.axes[0]
    assert axis.get_title() == "Top Models"
    assert [tick.get_text() for tick in axis.get_yticklabels()] == [
        "openai/gpt-4.1-mini",
        "openai/o3",
    ]


@pytest.mark.skipif(charts.Figure is None, reason="matplotlib unavailable")
def test_pie_chart_sets_labels_for_token_composition():
    figure = charts.create_figure()
    assert figure is not None

    charts.plot_pie_chart(
        figure,
        title="Token Composition",
        labels=["Input", "Output", "Reasoning"],
        values=[40, 50, 10],
    )

    axis = figure.axes[0]
    assert axis.get_title() == "Token Composition"
    labels = [text.get_text() for text in axis.texts if text.get_text() in {"Input", "Output", "Reasoning"}]
    assert labels == ["Input", "Output", "Reasoning"]


@pytest.mark.skipif(charts.Figure is None, reason="matplotlib unavailable")
def test_pie_chart_renders_empty_state_when_all_values_zero():
    figure = charts.create_figure()
    assert figure is not None

    charts.plot_pie_chart(
        figure,
        title="Token Composition",
        labels=["Input", "Output", "Reasoning"],
        values=[0, 0, 0],
    )

    axis = figure.axes[0]
    assert axis.get_title() == "Token Composition"
    assert axis.texts[0].get_text() == "No data"


@pytest.mark.skipif(charts.Figure is None, reason="matplotlib unavailable")
def test_line_chart_rejects_mismatched_labels_and_values():
    figure = charts.create_figure()
    assert figure is not None

    with pytest.raises(ValueError, match="same length"):
        charts.plot_line_chart(figure, title="Daily Tokens", labels=["2024-03-09"], values=[])


@pytest.mark.skipif(charts.Figure is None, reason="matplotlib unavailable")
def test_pie_chart_rejects_mismatched_labels_and_values():
    figure = charts.create_figure()
    assert figure is not None

    with pytest.raises(ValueError, match="same length"):
        charts.plot_pie_chart(figure, title="Token Composition", labels=["Input"], values=[])


def test_populate_view_refreshes_tables_and_charts():
    calls = []
    app = cast(Any, OpenCodeTokenApp.__new__(OpenCodeTokenApp))
    app.viewmodels = {
        "overview": {
            "cards": {
                "total_tokens": 100,
                "input_tokens": 40,
                "output_tokens": 50,
                "reasoning_tokens": 10,
            },
            "daily_rows": [{"day": "2024-03-09", "total_tokens": 100}],
        },
        "models": [{"provider": "openai", "model": "gpt-4.1-mini", "total_tokens": 100}],
        "days": [{"day": "2024-03-09", "total_tokens": 100}],
        "sessions": [{"session_id": "s1", "session_title": "Demo", "total_tokens": 100}],
        "raw_messages": [],
    }
    app.overview_card_labels = {
        "total_tokens": SimpleNamespace(configure=lambda **kwargs: None),
        "input_tokens": SimpleNamespace(configure=lambda **kwargs: None),
        "output_tokens": SimpleNamespace(configure=lambda **kwargs: None),
        "reasoning_tokens": SimpleNamespace(configure=lambda **kwargs: None),
    }
    app.overview_table = object()
    app.treeviews = {
        "models": object(),
        "days": object(),
        "sessions": object(),
        "raw_messages": object(),
    }
    app._fill_tree = lambda tree, rows: calls.append((tree, rows))
    app._refresh_charts = lambda: calls.append("charts")

    app._populate_view()

    assert calls[-1] == "charts"
    assert len([call for call in calls if call != "charts"]) == 5


def test_refresh_charts_isolates_single_chart_failure():
    calls = []
    app = cast(Any, OpenCodeTokenApp.__new__(OpenCodeTokenApp))
    app.status_var = SimpleNamespace(set=lambda value: calls.append(("status", value)))
    app._refresh_overview_daily_chart = lambda: (_ for _ in ()).throw(ChartRefreshError("boom"))
    app._refresh_overview_models_chart = lambda: calls.append("overview_models")
    app._refresh_overview_composition_chart = lambda: calls.append("overview_composition")
    app._refresh_models_chart = lambda: calls.append("models")
    app._refresh_days_chart = lambda: calls.append("days")
    app._refresh_sessions_chart = lambda: calls.append("sessions")

    app._refresh_charts()

    assert "overview_models" in calls
    assert "overview_composition" in calls
    assert "models" in calls
    assert "days" in calls
    assert "sessions" in calls
    assert any(call[0] == "status" and "boom" in call[1] for call in calls if isinstance(call, tuple))


def test_refresh_charts_aggregates_multiple_warnings():
    calls = []
    app = cast(Any, OpenCodeTokenApp.__new__(OpenCodeTokenApp))
    app.status_var = SimpleNamespace(set=lambda value: calls.append(value))
    app._refresh_overview_daily_chart = lambda: (_ for _ in ()).throw(ChartRefreshError("boom"))
    app._refresh_overview_models_chart = lambda: None
    app._refresh_overview_composition_chart = lambda: None
    app._refresh_models_chart = lambda: (_ for _ in ()).throw(ChartRefreshError("missing"))
    app._refresh_days_chart = lambda: None
    app._refresh_sessions_chart = lambda: None

    warnings = app._refresh_charts()

    assert warnings == ["boom", "missing"]
    assert calls == ["Loaded with chart warnings: boom; missing"]


def test_model_chart_rows_are_sorted_descending_and_trimmed_to_top_10():
    rows = [{"provider": "openai", "model": f"m{i}", "total_tokens": i} for i in range(1, 15)]

    labels, values = gui_module.build_top_model_chart_data(rows)

    assert len(labels) == 10
    assert labels[0] == "openai/m14"
    assert values[0] == 14
    assert labels[-1] == "openai/m5"
    assert values[-1] == 5


def test_overview_top_model_chart_uses_descending_total_tokens():
    labels, values = gui_module.build_top_model_chart_data(
        [
            {"provider": "openai", "model": "m1", "total_tokens": 10},
            {"provider": "openai", "model": "m2", "total_tokens": 30},
            {"provider": "openai", "model": "m3", "total_tokens": 20},
        ]
    )

    assert labels == ["openai/m2", "openai/m3", "openai/m1"]
    assert values == [30, 20, 10]


def test_session_chart_uses_session_id_when_title_missing():
    labels, values = gui_module.build_top_session_chart_data(
        [{"session_id": "s1", "session_title": "", "total_tokens": 7}]
    )

    assert labels == ["s1"]
    assert values == [7]


def test_day_chart_rows_are_sorted_ascending():
    labels, values = gui_module.build_day_chart_data(
        [
            {"day": "2024-03-10", "total_tokens": 20},
            {"day": "2024-03-09", "total_tokens": 10},
        ]
    )

    assert labels == ["2024-03-09", "2024-03-10"]
    assert values == [10, 20]


def test_overview_composition_chart_uses_input_output_reasoning_cards():
    labels, values = gui_module.build_overview_composition_chart_data(
        {"input_tokens": 40, "output_tokens": 50, "reasoning_tokens": 10}
    )

    assert labels == ["Input", "Output", "Reasoning"]
    assert values == [40, 50, 10]


def test_refresh_overview_chart_methods_pass_expected_data_to_plotters(monkeypatch):
    calls = []
    app = cast(Any, OpenCodeTokenApp.__new__(OpenCodeTokenApp))
    app.viewmodels = {
        "overview": {
            "cards": {"input_tokens": 40, "output_tokens": 50, "reasoning_tokens": 10},
            "daily_rows": [
                {"day": "2024-03-10", "total_tokens": 20},
                {"day": "2024-03-09", "total_tokens": 10},
            ],
        },
        "models": [
            {"provider": "openai", "model": "m1", "total_tokens": 10},
            {"provider": "openai", "model": "m2", "total_tokens": 30},
        ],
    }
    app.charts = {
        "overview_daily": {"figure": object(), "canvas": None},
        "overview_models": {"figure": object(), "canvas": None},
        "overview_composition": {"figure": object(), "canvas": None},
    }

    def record(name):
        return lambda figure, **kwargs: calls.append((name, kwargs))

    monkeypatch.setattr(gui_module, "plot_line_chart", record("line"))
    monkeypatch.setattr(gui_module, "plot_horizontal_bar_chart", record("bar"))
    monkeypatch.setattr(gui_module, "plot_pie_chart", record("pie"))

    app._refresh_overview_daily_chart()
    app._refresh_overview_models_chart()
    app._refresh_overview_composition_chart()

    assert calls == [
        (
            "line",
            {
                "title": "Daily Tokens",
                "labels": ["2024-03-09", "2024-03-10"],
                "values": [10, 20],
                "ylabel": "Tokens",
            },
        ),
        (
            "bar",
            {
                "title": "Top Models",
                "labels": ["openai/m2", "openai/m1"],
                "values": [30, 10],
                "xlabel": "Tokens",
            },
        ),
        (
            "pie",
            {
                "title": "Token Composition",
                "labels": ["Input", "Output", "Reasoning"],
                "values": [40, 50, 10],
            },
        ),
    ]


def test_draw_chart_raises_when_chart_is_not_registered():
    app = cast(Any, OpenCodeTokenApp.__new__(OpenCodeTokenApp))
    app.charts = {}

    with pytest.raises(ChartRefreshError, match="not registered"):
        app._draw_chart("missing", lambda figure, **kwargs: None, title="Missing")


def test_refresh_analysis_charts_pass_expected_data_to_plotters(monkeypatch):
    calls = []
    app = cast(Any, OpenCodeTokenApp.__new__(OpenCodeTokenApp))
    app.viewmodels = {
        "models": [
            {"provider": "openai", "model": "m1", "total_tokens": 10},
            {"provider": "openai", "model": "m2", "total_tokens": 30},
        ],
        "days": [
            {"day": "2024-03-10", "total_tokens": 20},
            {"day": "2024-03-09", "total_tokens": 10},
        ],
        "sessions": [
            {"session_id": "s1", "session_title": "", "total_tokens": 5},
            {"session_id": "s2", "session_title": "Demo", "total_tokens": 8},
        ],
    }
    app.charts = {
        "models": {"figure": object(), "canvas": None},
        "days": {"figure": object(), "canvas": None},
        "sessions": {"figure": object(), "canvas": None},
    }

    def record(name):
        return lambda figure, **kwargs: calls.append((name, kwargs))

    monkeypatch.setattr(gui_module, "plot_horizontal_bar_chart", record("bar"))
    monkeypatch.setattr(gui_module, "plot_line_chart", record("line"))

    app._refresh_models_chart()
    app._refresh_days_chart()
    app._refresh_sessions_chart()

    assert calls == [
        (
            "bar",
            {
                "title": "Top Models",
                "labels": ["openai/m2", "openai/m1"],
                "values": [30, 10],
                "xlabel": "Tokens",
            },
        ),
        (
            "line",
            {
                "title": "Daily Tokens",
                "labels": ["2024-03-09", "2024-03-10"],
                "values": [10, 20],
                "ylabel": "Tokens",
            },
        ),
        (
            "bar",
            {
                "title": "Top Sessions",
                "labels": ["Demo", "s1"],
                "values": [8, 5],
                "xlabel": "Tokens",
            },
        ),
    ]


def test_refresh_charts_isolates_chart_data_preparation_failures(monkeypatch):
    calls = []
    app = cast(Any, OpenCodeTokenApp.__new__(OpenCodeTokenApp))
    app.status_var = SimpleNamespace(set=lambda value: calls.append(("status", value)))
    app.viewmodels = {
        "overview": {"cards": {}, "daily_rows": []},
        "models": [],
        "days": [{"day": "2024-03-09", "total_tokens": 10}],
        "sessions": [],
    }
    app.charts = {
        "overview_daily": {"figure": object(), "canvas": None},
        "overview_models": {"figure": object(), "canvas": None},
        "overview_composition": {"figure": object(), "canvas": None},
        "models": {"figure": object(), "canvas": None},
        "days": {"figure": object(), "canvas": None},
        "sessions": {"figure": object(), "canvas": None},
    }

    monkeypatch.setattr(gui_module, "build_day_chart_data", lambda rows: (_ for _ in ()).throw(KeyError("bad day")))
    monkeypatch.setattr(gui_module, "plot_line_chart", lambda figure, **kwargs: calls.append("line"))
    monkeypatch.setattr(gui_module, "plot_horizontal_bar_chart", lambda figure, **kwargs: calls.append("bar"))
    monkeypatch.setattr(gui_module, "plot_pie_chart", lambda figure, **kwargs: calls.append("pie"))

    warnings = app._refresh_charts()

    assert warnings == ["overview_daily: 'bad day'", "days: 'bad day'"]
    assert "bar" in calls
    assert "pie" in calls
    assert any(call[0] == "status" and "overview_daily: 'bad day'" in call[1] for call in calls if isinstance(call, tuple))
