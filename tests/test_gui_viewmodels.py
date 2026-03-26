from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from opencode_token_app import charts
from opencode_token_app import gui as gui_module
from opencode_token_app.gui import ChartRefreshError, OpenCodeTokenApp, default_db_path
import opencode_token_gui
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
    assert vm["cards"]["estimated_cost_total_display"] == "$1.50 USD"
    assert vm["cards"]["recorded_cost_total_display"] == "$1.20 USD"
    assert vm["daily_rows"][0]["total_tokens"] == 1234567
    assert vm["daily_rows"][0]["total_tokens_display"] == "1.23M"


def test_overview_viewmodel_formats_mixed_currency_estimated_totals():
    datasets = {
        "summary": {
            "estimated_cost_total": None,
            "estimated_cost_totals": {"USD": 1.5, "CNY": 2.0},
            "recorded_cost_total": 1.2,
        },
        "by_day": [{"day": "2024-03-09", "estimated_cost_totals": {"USD": 1.5, "CNY": 2.0}}],
    }

    vm = build_overview_viewmodel(datasets)

    assert vm["cards"]["estimated_cost_total_display"] == "¥2.00 CNY / $1.50 USD"
    assert vm["daily_rows"][0]["estimated_cost_display"] == "¥2.00 CNY / $1.50 USD"


def test_overview_viewmodel_formats_zero_and_missing_cost_displays():
    zero_vm = build_overview_viewmodel(
        {"summary": {"estimated_cost_total": 0, "recorded_cost_total": 0}, "by_day": []}
    )
    blank_vm = build_overview_viewmodel(
        {"summary": {"estimated_cost_total": None, "recorded_cost_total": None}, "by_day": []}
    )

    assert zero_vm["cards"]["estimated_cost_total_display"] == "$0.00 USD"
    assert zero_vm["cards"]["recorded_cost_total_display"] == "$0.00 USD"
    assert blank_vm["cards"]["estimated_cost_total_display"] == ""
    assert blank_vm["cards"]["recorded_cost_total_display"] == ""


def test_build_application_viewmodels_exposes_model_day_session_and_raw_rows():
    datasets = {
        "summary": {"total_tokens": 100, "input_tokens": 40, "output_tokens": 60, "reasoning_tokens": 10, "estimated_cost_total": 1.5, "recorded_cost_total": 1.2},
        "by_model": [{"provider": "OpenAI", "model": "gpt-4.1-mini", "message_count": 2, "total_tokens": 100, "input_tokens": 40, "output_tokens": 60, "estimated_cost_total": 1.5, "recorded_cost_total": 1.2, "priced_message_count": 2, "unpriced_message_count": 0}],
        "by_day": [{"day": "2024-03-09", "message_count": 2, "total_tokens": 100, "input_tokens": 40, "output_tokens": 60, "estimated_cost_total": 1.5, "recorded_cost_total": 1.2}],
        "by_session": [{"session_id": "s1", "session_title": "Demo", "message_count": 2, "total_tokens": 100, "input_tokens": 40, "output_tokens": 60, "estimated_cost_total": 1.5, "recorded_cost_total": 1.2}],
        "raw_messages": [{"day": "2024-03-09", "provider": "OpenAI", "model": "gpt-4.1-mini", "estimated_cost": 1.5, "estimated_cost_currency": "USD", "cost": 1.2, "price_status": "priced"}],
    }

    vm = build_application_viewmodels(datasets)

    assert vm["models"][0]["price_status_label"] == "已定价"
    assert vm["models"][0]["estimated_cost_display"] == "$1.50 USD"
    assert vm["models"][0]["recorded_cost_display"] == "$1.20 USD"
    assert vm["days"][0]["day"] == "2024-03-09"
    assert vm["days"][0]["message_count"] == 2
    assert vm["days"][0]["estimated_cost_display"] == "$1.50 USD"
    assert vm["sessions"][0]["session_title"] == "Demo"
    assert vm["sessions"][0]["message_count"] == 2
    assert vm["sessions"][0]["recorded_cost_display"] == "$1.20 USD"
    assert vm["raw_messages"][0]["model"] == "gpt-4.1-mini"
    assert vm["raw_messages"][0]["estimated_cost_display"] == "$1.50 USD"
    assert vm["raw_messages"][0]["recorded_cost_display"] == "$1.20 USD"


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


def test_build_application_viewmodels_formats_cny_estimated_costs():
    datasets = {
        "summary": {"estimated_cost_totals": {"CNY": 3.5}},
        "by_model": [{"provider": "kimi", "model": "kimi-k2.5", "estimated_cost_totals": {"CNY": 3.5}, "priced_message_count": 1, "unpriced_message_count": 0}],
        "by_day": [],
        "by_session": [],
        "raw_messages": [{"provider": "kimi", "model": "kimi-k2.5", "estimated_cost": 3.5, "estimated_cost_currency": "CNY", "price_status": "priced"}],
    }

    vm = build_application_viewmodels(datasets)

    assert vm["overview"]["cards"]["estimated_cost_total_display"] == "¥3.50 CNY"
    assert vm["models"][0]["estimated_cost_display"] == "¥3.50 CNY"
    assert vm["raw_messages"][0]["estimated_cost_display"] == "¥3.50 CNY"


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


def test_create_figure_configures_cjk_font_fallback(monkeypatch):
    class FakeFigure:
        def __init__(self, figsize, dpi):
            self.figsize = figsize
            self.dpi = dpi

    fake_matplotlib = SimpleNamespace(rcParams={})

    monkeypatch.setattr(charts, "matplotlib", fake_matplotlib)
    monkeypatch.setattr(charts, "Figure", FakeFigure)

    figure = charts.create_figure(width=6, height=4)

    assert isinstance(figure, FakeFigure)
    assert figure.figsize == (6, 4)
    assert figure.dpi == 100
    assert fake_matplotlib.rcParams["font.family"] == ["sans-serif"]
    assert fake_matplotlib.rcParams["font.sans-serif"] == charts.CJK_FONT_CANDIDATES
    assert fake_matplotlib.rcParams["axes.unicode_minus"] is False


def test_attach_canvas_returns_none_when_tk_canvas_unavailable(monkeypatch):
    monkeypatch.setattr(charts, "FigureCanvasTkAgg", None)

    assert charts.attach_canvas(object(), master=object()) is None


def test_chart_helpers_no_op_when_figure_unavailable():
    charts.plot_line_chart(None, title="每日 token", labels=[], values=[])
    charts.plot_horizontal_bar_chart(None, title="热门模型", labels=[], values=[])
    charts.plot_pie_chart(None, title="token 构成", labels=[], values=[])


@pytest.mark.skipif(charts.Figure is None, reason="matplotlib unavailable")
def test_line_chart_renders_empty_state_when_no_values():
    figure = charts.create_figure()
    assert figure is not None

    charts.plot_line_chart(figure, title="每日 token", labels=[], values=[])

    axis = figure.axes[0]
    assert axis.get_title() == "每日 token"
    assert axis.texts[0].get_text() == "无数据"


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
        title="token 构成",
        labels=["输入 token", "输出 token", "推理 token"],
        values=[40, 50, 10],
    )

    axis = figure.axes[0]
    assert axis.get_title() == "token 构成"
    labels = [text.get_text() for text in axis.texts if text.get_text() in {"输入 token", "输出 token", "推理 token"}]
    assert labels == ["输入 token", "输出 token", "推理 token"]


@pytest.mark.skipif(charts.Figure is None, reason="matplotlib unavailable")
def test_pie_chart_renders_empty_state_when_all_values_zero():
    figure = charts.create_figure()
    assert figure is not None

    charts.plot_pie_chart(
        figure,
        title="token 构成",
        labels=["输入 token", "输出 token", "推理 token"],
        values=[0, 0, 0],
    )

    axis = figure.axes[0]
    assert axis.get_title() == "token 构成"
    assert axis.texts[0].get_text() == "无数据"


@pytest.mark.skipif(charts.Figure is None, reason="matplotlib unavailable")
def test_line_chart_rejects_mismatched_labels_and_values():
    figure = charts.create_figure()
    assert figure is not None

    with pytest.raises(ValueError, match="same length"):
        charts.plot_line_chart(figure, title="每日 token", labels=["2024-03-09"], values=[])


@pytest.mark.skipif(charts.Figure is None, reason="matplotlib unavailable")
def test_pie_chart_rejects_mismatched_labels_and_values():
    figure = charts.create_figure()
    assert figure is not None

    with pytest.raises(ValueError, match="same length"):
        charts.plot_pie_chart(figure, title="token 构成", labels=["输入 token"], values=[])


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


def test_populate_view_uses_token_display_fields_for_cards_and_tables():
    class FakeLabel:
        def __init__(self):
            self.text = None

        def configure(self, **kwargs):
            self.text = kwargs["text"]

    class FakeTree:
        def __init__(self, columns):
            self.columns = tuple(columns)
            self.rows = []

        def get_children(self):
            return []

        def delete(self, item):
            raise AssertionError("delete should not be called for empty tree")

        def insert(self, parent, index, values):
            self.rows.append(tuple(values))

        def __getitem__(self, key):
            if key != "columns":
                raise KeyError(key)
            return self.columns

    app = cast(Any, OpenCodeTokenApp.__new__(OpenCodeTokenApp))
    app.viewmodels = {
        "overview": {
            "cards": {
                "total_tokens": 1234567,
                "total_tokens_display": "1.23M",
                "input_tokens": 400000,
                "input_tokens_display": "0.40M",
                "output_tokens": 830000,
                "output_tokens_display": "0.83M",
                "reasoning_tokens": 4567,
                "reasoning_tokens_display": "0.00M",
                "estimated_cost_total": "1.50",
                "estimated_cost_total_display": "$1.50 USD",
                "recorded_cost_total": "1.20",
                "recorded_cost_total_display": "$1.20 USD",
            },
            "daily_rows": [
                {
                    "day": "2024-03-09",
                    "total_tokens": 1234567,
                    "total_tokens_display": "1.23M",
                    "estimated_cost_display": "$1.50 USD",
                }
            ],
        },
        "models": [
            {
                "provider": "openai",
                "model": "gpt-4.1-mini",
                "total_tokens": 1234567,
                "total_tokens_display": "1.23M",
                "estimated_cost_display": "$1.50 USD",
                "recorded_cost_display": "$1.20 USD",
            }
        ],
        "days": [
            {
                "day": "2024-03-09",
                "total_tokens": 400000,
                "total_tokens_display": "0.40M",
                "estimated_cost_display": "$1.50 USD",
                "recorded_cost_display": "$1.20 USD",
            }
        ],
        "sessions": [
            {
                "session_id": "s1",
                "session_title": "Demo",
                "total_tokens": 830000,
                "total_tokens_display": "0.83M",
                "estimated_cost_display": "$1.50 USD",
                "recorded_cost_display": "$1.20 USD",
            }
        ],
        "raw_messages": [
            {
                "provider": "openai",
                "model": "gpt-4.1-mini",
                "total_tokens": 4567,
                "total_tokens_display": "0.00M",
                "input_tokens": 400000,
                "input_tokens_display": "0.40M",
                "output_tokens": 830000,
                "output_tokens_display": "0.83M",
                "estimated_cost_display": "$1.50 USD",
                "recorded_cost_display": "$1.20 USD",
            }
        ],
    }
    app.overview_card_labels = {
        "total_tokens": FakeLabel(),
        "input_tokens": FakeLabel(),
        "output_tokens": FakeLabel(),
        "reasoning_tokens": FakeLabel(),
        "estimated_cost_total": FakeLabel(),
        "recorded_cost_total": FakeLabel(),
    }
    app.overview_table = FakeTree(["day", "total_tokens_display", "estimated_cost_display"])
    app.treeviews = {
        "models": FakeTree(["provider", "model", "total_tokens_display", "estimated_cost_display", "recorded_cost_display"]),
        "days": FakeTree(["day", "total_tokens_display", "estimated_cost_display", "recorded_cost_display"]),
        "sessions": FakeTree(["session_id", "session_title", "total_tokens_display", "estimated_cost_display", "recorded_cost_display"]),
        "raw_messages": FakeTree([
            "provider",
            "model",
            "total_tokens_display",
            "input_tokens_display",
            "output_tokens_display",
            "estimated_cost_display",
            "recorded_cost_display",
        ]),
    }
    app._refresh_charts = lambda: []

    app._populate_view()

    assert app.overview_card_labels["total_tokens"].text == "总 token: 1.23M"
    assert app.overview_card_labels["input_tokens"].text == "输入 token: 0.40M"
    assert app.overview_card_labels["output_tokens"].text == "输出 token: 0.83M"
    assert app.overview_card_labels["reasoning_tokens"].text == "推理 token: 0.00M"
    assert app.overview_card_labels["estimated_cost_total"].text == "预估价格: $1.50 USD"
    assert app.overview_card_labels["recorded_cost_total"].text == "已记录价格（美元）: $1.20 USD"
    assert app.overview_table.rows == [("2024-03-09", "1.23M", "$1.50 USD")]
    assert app.treeviews["models"].rows == [
        ("openai", "gpt-4.1-mini", "1.23M", "$1.50 USD", "$1.20 USD")
    ]
    assert app.treeviews["days"].rows == [("2024-03-09", "0.40M", "$1.50 USD", "$1.20 USD")]
    assert app.treeviews["sessions"].rows == [("s1", "Demo", "0.83M", "$1.50 USD", "$1.20 USD")]
    assert app.treeviews["raw_messages"].rows == [
        ("openai", "gpt-4.1-mini", "0.00M", "0.40M", "0.83M", "$1.50 USD", "$1.20 USD")
    ]


def test_reset_raw_message_pagination_sets_first_page_state():
    app = cast(Any, OpenCodeTokenApp.__new__(OpenCodeTokenApp))
    app.raw_message_page_size = 200
    app.viewmodels = {
        "raw_messages": [{"id": idx} for idx in range(450)],
    }

    app._reset_raw_message_pagination()

    assert app.raw_message_page_index == 0
    assert app.raw_message_total_rows == 450
    assert app.raw_message_page_count == 3


def test_current_raw_message_rows_returns_current_page_slice():
    app = cast(Any, OpenCodeTokenApp.__new__(OpenCodeTokenApp))
    app.raw_message_page_size = 200
    app.raw_message_page_index = 1
    app.viewmodels = {
        "raw_messages": [{"id": idx} for idx in range(450)],
    }

    rows = app._current_raw_message_rows()

    assert rows == [{"id": idx} for idx in range(200, 400)]


def test_current_raw_message_rows_clamps_page_index_to_last_page():
    app = cast(Any, OpenCodeTokenApp.__new__(OpenCodeTokenApp))
    app.raw_message_page_size = 200
    app.raw_message_page_index = 99
    app.viewmodels = {
        "raw_messages": [{"id": idx} for idx in range(450)],
    }

    rows = app._current_raw_message_rows()

    assert app.raw_message_page_index == 2
    assert rows == [{"id": idx} for idx in range(400, 450)]


def test_populate_view_preserves_current_raw_message_page_and_refreshes_pagination():
    calls = []
    refresh_calls = []
    raw_rows = [{"id": idx} for idx in range(450)]
    app = cast(Any, OpenCodeTokenApp.__new__(OpenCodeTokenApp))
    app.raw_message_page_size = 200
    app.raw_message_page_index = 2
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
        "raw_messages": raw_rows,
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
    app._refresh_raw_message_pagination = lambda: refresh_calls.append(
        (app.raw_message_page_index, app.raw_message_total_rows, app.raw_message_page_count)
    )
    app._refresh_charts = lambda: []

    app._populate_view()

    assert calls[4] == (app.treeviews["raw_messages"], raw_rows[400:450])
    assert refresh_calls == [(2, 450, 3)]


def test_reset_raw_message_pagination_handles_empty_rows():
    app = cast(Any, OpenCodeTokenApp.__new__(OpenCodeTokenApp))
    app.raw_message_page_size = 200
    app.raw_message_page_index = 5
    app.viewmodels = {
        "raw_messages": [],
    }

    app._reset_raw_message_pagination()

    assert app.raw_message_page_index == 0
    assert app.raw_message_total_rows == 0
    assert app.raw_message_page_count == 0


def test_reset_raw_message_pagination_normalizes_non_positive_page_size():
    app = cast(Any, OpenCodeTokenApp.__new__(OpenCodeTokenApp))
    app.raw_message_page_size = 0
    app.viewmodels = {
        "raw_messages": [{"id": idx} for idx in range(450)],
    }

    app._reset_raw_message_pagination()

    assert app.raw_message_page_size == 200
    assert app.raw_message_page_index == 0
    assert app.raw_message_total_rows == 450
    assert app.raw_message_page_count == 3


def test_refresh_raw_message_pagination_clamps_invalid_page_index_for_widgets():
    class FakeWidget:
        def __init__(self):
            self.values = []

        def configure(self, **kwargs):
            self.values.append(kwargs)

    class FakeStringVar:
        def __init__(self):
            self.value = None

        def set(self, value):
            self.value = value

    app = cast(Any, OpenCodeTokenApp.__new__(OpenCodeTokenApp))
    app.raw_message_page_size = -5
    app.raw_message_page_index = 99
    app.viewmodels = {
        "raw_messages": [{"id": idx} for idx in range(450)],
    }
    app.raw_page_label_var = FakeStringVar()
    app.raw_range_label_var = FakeStringVar()
    app.raw_message_prev_button = FakeWidget()
    app.raw_message_next_button = FakeWidget()

    app._refresh_raw_message_pagination()

    assert app.raw_message_page_size == 200
    assert app.raw_message_page_index == 2
    assert app.raw_message_total_rows == 450
    assert app.raw_message_page_count == 3
    assert app.raw_page_label_var.value == "第 3 / 3 页"
    assert app.raw_range_label_var.value == "显示第 401 - 450 条，共 450 条"
    assert app.raw_message_prev_button.values == [{"state": "normal"}]
    assert app.raw_message_next_button.values == [{"state": "disabled"}]


def test_refresh_raw_message_pagination_updates_labels_and_button_states_for_non_empty_pages():
    class FakeWidget:
        def __init__(self):
            self.values = []

        def configure(self, **kwargs):
            self.values.append(kwargs)

    class FakeStringVar:
        def __init__(self):
            self.value = None

        def set(self, value):
            self.value = value

    app = cast(Any, OpenCodeTokenApp.__new__(OpenCodeTokenApp))
    app.raw_message_page_size = 200
    app.raw_message_page_index = 1
    app.viewmodels = {
        "raw_messages": [{"id": idx} for idx in range(450)],
    }
    app.raw_page_label_var = FakeStringVar()
    app.raw_range_label_var = FakeStringVar()
    app.raw_message_prev_button = FakeWidget()
    app.raw_message_next_button = FakeWidget()

    app._refresh_raw_message_pagination()

    assert app.raw_page_label_var.value == "第 2 / 3 页"
    assert app.raw_range_label_var.value == "显示第 201 - 400 条，共 450 条"
    assert app.raw_message_prev_button.values == [{"state": "normal"}]
    assert app.raw_message_next_button.values == [{"state": "normal"}]


def test_show_next_raw_message_page_advances_until_last_page_and_stops():
    renders = []
    app = cast(Any, OpenCodeTokenApp.__new__(OpenCodeTokenApp))
    app.raw_message_page_size = 200
    app.raw_message_page_index = 0
    app.viewmodels = {
        "raw_messages": [{"id": idx} for idx in range(450)],
    }
    app._render_current_raw_message_page = lambda: renders.append(app.raw_message_page_index)

    app.show_next_raw_message_page()
    app.show_next_raw_message_page()
    app.show_next_raw_message_page()

    assert app.raw_message_page_index == 2
    assert renders == [1, 2, 2]


def test_show_next_raw_message_page_refreshes_ui_on_last_page_no_op():
    refreshes = []
    app = cast(Any, OpenCodeTokenApp.__new__(OpenCodeTokenApp))
    app.raw_message_page_size = 200
    app.raw_message_page_index = 2
    app.viewmodels = {
        "raw_messages": [{"id": idx} for idx in range(450)],
    }
    app._render_current_raw_message_page = lambda: refreshes.append(app.raw_message_page_index)

    app.show_next_raw_message_page()

    assert app.raw_message_page_index == 2
    assert refreshes == [2]


def test_show_previous_raw_message_page_stops_at_first_page():
    renders = []
    app = cast(Any, OpenCodeTokenApp.__new__(OpenCodeTokenApp))
    app.raw_message_page_size = 200
    app.raw_message_page_index = 2
    app.viewmodels = {
        "raw_messages": [{"id": idx} for idx in range(450)],
    }
    app._render_current_raw_message_page = lambda: renders.append(app.raw_message_page_index)

    app.show_previous_raw_message_page()
    app.show_previous_raw_message_page()
    app.show_previous_raw_message_page()

    assert app.raw_message_page_index == 0
    assert renders == [1, 0, 0]


def test_show_previous_raw_message_page_refreshes_ui_on_first_page_no_op():
    refreshes = []
    app = cast(Any, OpenCodeTokenApp.__new__(OpenCodeTokenApp))
    app.raw_message_page_size = 200
    app.raw_message_page_index = 0
    app.viewmodels = {
        "raw_messages": [{"id": idx} for idx in range(450)],
    }
    app._render_current_raw_message_page = lambda: refreshes.append(app.raw_message_page_index)

    app.show_previous_raw_message_page()

    assert app.raw_message_page_index == 0
    assert refreshes == [0]


def test_refresh_raw_message_pagination_uses_explicit_empty_state_text():
    class FakeWidget:
        def __init__(self):
            self.values = []

        def configure(self, **kwargs):
            self.values.append(kwargs)

    class FakeStringVar:
        def __init__(self):
            self.value = None

        def set(self, value):
            self.value = value

    app = cast(Any, OpenCodeTokenApp.__new__(OpenCodeTokenApp))
    app.raw_message_page_size = 200
    app.raw_message_page_index = 5
    app.viewmodels = {"raw_messages": []}
    app.raw_page_label_var = FakeStringVar()
    app.raw_range_label_var = FakeStringVar()
    app.raw_message_prev_button = FakeWidget()
    app.raw_message_next_button = FakeWidget()

    app._refresh_raw_message_pagination()

    assert app.raw_message_page_index == 0
    assert app.raw_message_total_rows == 0
    assert app.raw_message_page_count == 0
    assert app.raw_page_label_var.value == "暂无数据"
    assert app.raw_range_label_var.value == "当前没有可显示的明细"
    assert app.raw_message_prev_button.values == [{"state": "disabled"}]
    assert app.raw_message_next_button.values == [{"state": "disabled"}]


def test_raw_message_pagination_info_returns_named_state():
    app = cast(Any, OpenCodeTokenApp.__new__(OpenCodeTokenApp))
    app.raw_message_page_size = "200"
    app.raw_message_page_index = 1
    app.viewmodels = {
        "raw_messages": [{"id": idx} for idx in range(450)],
    }

    info = app._raw_message_pagination_info()

    assert info == {
        "rows": [{"id": idx} for idx in range(450)],
        "page_index": 1,
        "page_size": 200,
        "total_rows": 450,
        "page_count": 3,
    }


def test_render_raw_message_page_fills_tree_and_refreshes_pagination():
    calls = []
    refresh_calls = []
    app = cast(Any, OpenCodeTokenApp.__new__(OpenCodeTokenApp))
    app.treeviews = {"raw_messages": object()}
    app._current_raw_message_rows = lambda: [{"id": 200}, {"id": 201}]
    app._refresh_raw_message_pagination = lambda: refresh_calls.append("pagination")
    app._fill_tree = lambda tree, rows: calls.append((tree, rows))

    app._render_raw_message_page()

    assert calls == [(app.treeviews["raw_messages"], [{"id": 200}, {"id": 201}])]
    assert refresh_calls == ["pagination"]


def test_refresh_charts_isolates_single_chart_failure():
    calls = []
    app = cast(Any, OpenCodeTokenApp.__new__(OpenCodeTokenApp))
    app.status_var = SimpleNamespace(set=lambda value: calls.append(("status", value)))
    app._refresh_overview_daily_chart = lambda: (_ for _ in ()).throw(ChartRefreshError("boom"))
    app._refresh_overview_peak_days_chart = lambda: calls.append("overview_peak_days")
    app._refresh_overview_models_chart = lambda: calls.append("overview_models")
    app._refresh_overview_composition_chart = lambda: calls.append("overview_composition")
    app._refresh_models_chart = lambda: calls.append("models")
    app._refresh_days_chart = lambda: calls.append("days")
    app._refresh_sessions_chart = lambda: calls.append("sessions")

    app._refresh_charts()

    assert "overview_peak_days" in calls
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
    app._refresh_overview_peak_days_chart = lambda: None
    app._refresh_overview_models_chart = lambda: None
    app._refresh_overview_composition_chart = lambda: None
    app._refresh_models_chart = lambda: (_ for _ in ()).throw(ChartRefreshError("missing"))
    app._refresh_days_chart = lambda: None
    app._refresh_sessions_chart = lambda: None

    warnings = app._refresh_charts()

    assert warnings == ["boom", "missing"]
    assert calls == ["已加载，但图表有警告：图表刷新失败：boom; 图表刷新失败：missing"]


def test_create_treeview_localizes_column_headings(monkeypatch):
    headings = {}

    class FakeTreeview:
        def __init__(self, parent, columns, show, height):
            self.columns = tuple(columns)

        def heading(self, column, text):
            headings[column] = text

        def column(self, column, width, stretch):
            pass

        def pack(self, **kwargs):
            pass

    monkeypatch.setattr(gui_module.ttk, "Treeview", FakeTreeview)
    app = cast(Any, OpenCodeTokenApp.__new__(OpenCodeTokenApp))

    tree = app._create_treeview(object(), [
        "day",
        "provider",
        "model",
        "role",
        "time_created_text",
        "session_id",
        "session_title",
        "message_count",
        "total_tokens_display",
        "input_tokens_display",
        "output_tokens_display",
        "estimated_cost_display",
        "recorded_cost_display",
        "price_status_label",
    ])

    assert tree.columns == (
        "day",
        "provider",
        "model",
        "role",
        "time_created_text",
        "session_id",
        "session_title",
        "message_count",
        "total_tokens_display",
        "input_tokens_display",
        "output_tokens_display",
        "estimated_cost_display",
        "recorded_cost_display",
        "price_status_label",
    )
    assert headings == {
        "day": "日期",
        "provider": "提供方",
        "model": "模型",
        "role": "角色",
        "time_created_text": "时间",
        "session_id": "会话 ID",
        "session_title": "会话标题",
        "message_count": "消息数",
        "total_tokens_display": "总 token",
        "input_tokens_display": "输入 token",
        "output_tokens_display": "输出 token",
        "estimated_cost_display": "预估价格",
        "recorded_cost_display": "已记录价格（美元）",
        "price_status_label": "定价状态",
    }


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

    assert labels == ["03/09", "03/10"]
    assert values == [10, 20]


def test_day_chart_rows_sort_valid_non_zero_padded_days_before_malformed_labels():
    labels, values = gui_module.build_day_chart_data(
        [
            {"day": "2024-3-10", "total_tokens": 20},
            {"day": "bad-day", "total_tokens": 99},
            {"day": "2024-3-9", "total_tokens": 10},
        ]
    )

    assert labels == ["03/09", "03/10", "bad-day"]
    assert values == [10, 20, 99]


@pytest.mark.parametrize(
    ("day", "expected"),
    [
        ("2024-03-09", "03/09"),
        ("2024-12-31", "12/31"),
        ("2024-99-99", "2024-99-99"),
        ("2024/03/09", "2024/03/09"),
        ("bad", "bad"),
        ("", ""),
    ],
)
def test_format_day_label(day, expected):
    assert gui_module.format_day_label(day) == expected


def test_build_recent_day_chart_data_uses_latest_seven_days_sorted_ascending_and_formats_labels():
    labels, values = gui_module.build_recent_day_chart_data(
        [
            {"day": "2024-03-08", "total_tokens": 80},
            {"day": "2024-03-01", "total_tokens": 10},
            {"day": "2024-03-05", "total_tokens": 50},
            {"day": "2024-03-03", "total_tokens": 30},
            {"day": "2024-03-07", "total_tokens": 70},
            {"day": "2024-03-02", "total_tokens": 20},
            {"day": "2024-03-06", "total_tokens": 60},
            {"day": "2024-03-04", "total_tokens": 40},
        ]
    )

    assert labels == ["03/02", "03/03", "03/04", "03/05", "03/06", "03/07", "03/08"]
    assert values == [20, 30, 40, 50, 60, 70, 80]


def test_build_recent_day_chart_data_uses_latest_seven_calendar_days_and_fills_missing_days():
    labels, values = gui_module.build_recent_day_chart_data(
        [
            {"day": "2024-03-08", "total_tokens": 80},
            {"day": "2024-03-06", "total_tokens": 60},
            {"day": "2024-03-03", "total_tokens": 30},
            {"day": "2024-03-02", "total_tokens": 20},
            {"day": "bad-day", "total_tokens": 999},
        ]
    )

    assert labels == ["03/02", "03/03", "03/04", "03/05", "03/06", "03/07", "03/08"]
    assert values == [20, 30, 0, 0, 60, 0, 80]


def test_build_peak_day_chart_data_uses_top_seven_days_with_day_desc_tiebreaker_and_formats_labels():
    labels, values = gui_module.build_peak_day_chart_data(
        [
            {"day": "2024-03-01", "total_tokens": 100},
            {"day": "2024-03-02", "total_tokens": 100},
            {"day": "2024-03-03", "total_tokens": 90},
            {"day": "2024-03-04", "total_tokens": 80},
            {"day": "2024-03-05", "total_tokens": 70},
            {"day": "2024-03-06", "total_tokens": 60},
            {"day": "2024-03-07", "total_tokens": 50},
            {"day": "2024-03-08", "total_tokens": 40},
        ]
    )

    assert labels == ["03/02", "03/01", "03/03", "03/04", "03/05", "03/06", "03/07"]
    assert values == [100, 100, 90, 80, 70, 60, 50]


def test_build_peak_day_chart_data_uses_month_day_only_even_for_cross_year_duplicates():
    labels, values = gui_module.build_peak_day_chart_data(
        [
            {"day": "2025-03-02", "total_tokens": 300},
            {"day": "2024-03-02", "total_tokens": 250},
            {"day": "2024-03-01", "total_tokens": 200},
        ]
    )

    assert labels == ["03/02", "03/02", "03/01"]
    assert values == [300, 250, 200]


def test_overview_composition_chart_uses_input_output_reasoning_cards():
    labels, values = gui_module.build_overview_composition_chart_data(
        {"input_tokens": 40, "output_tokens": 50, "reasoning_tokens": 10}
    )

    assert labels == ["输入 token", "输出 token", "推理 token"]
    assert values == [40, 50, 10]


def test_scale_tokens_to_millions_handles_bad_inputs_and_scales_numbers():
    assert gui_module.scale_tokens_to_millions([2_000_000, None, "bad", 500_000]) == [2.0, 0.0, 0.0, 0.5]


def test_refresh_overview_chart_methods_scale_tokens_to_millions_and_use_expected_labels(monkeypatch):
    calls = []
    app = cast(Any, OpenCodeTokenApp.__new__(OpenCodeTokenApp))
    app.viewmodels = {
        "overview": {
            "cards": {"input_tokens": 400_000, "output_tokens": 500_000, "reasoning_tokens": 100_000},
            "daily_rows": [
                {"day": "2024-03-10", "total_tokens": 2_500_000},
                {"day": "2024-03-09", "total_tokens": 2_000_000},
                {"day": "2024-03-08", "total_tokens": 1_500_000},
                {"day": "2024-03-06", "total_tokens": 500_000},
                {"day": "2024-03-05", "total_tokens": 2_200_000},
                {"day": "2024-03-04", "total_tokens": 1_000_000},
                {"day": "2024-03-03", "total_tokens": 2_400_000},
                {"day": "2024-03-02", "total_tokens": 3_000_000},
                {"day": "2023-03-07", "total_tokens": 2_700_000},
            ],
        },
        "models": [
            {"provider": "openai", "model": "m1", "total_tokens": 1_000_000},
            {"provider": "openai", "model": "m2", "total_tokens": 3_000_000},
        ],
    }
    app.charts = {
        "overview_daily": {"figure": object(), "canvas": None},
        "overview_peak_days": {"figure": object(), "canvas": None},
        "overview_models": {"figure": object(), "canvas": None},
        "overview_composition": {"figure": object(), "canvas": None},
    }

    def record(name):
        return lambda figure, **kwargs: calls.append((name, kwargs))

    monkeypatch.setattr(gui_module, "plot_line_chart", record("line"))
    monkeypatch.setattr(gui_module, "plot_horizontal_bar_chart", record("bar"))
    monkeypatch.setattr(gui_module, "plot_pie_chart", record("pie"))

    app._refresh_overview_daily_chart()
    app._refresh_overview_peak_days_chart()
    app._refresh_overview_models_chart()
    app._refresh_overview_composition_chart()

    assert calls == [
        (
            "line",
            {
                "title": "每日 token",
                "labels": ["03/04", "03/05", "03/06", "03/07", "03/08", "03/09", "03/10"],
                "values": [1.0, 2.2, 0.5, 0.0, 1.5, 2.0, 2.5],
                "ylabel": "token（M）",
            },
        ),
        (
            "bar",
            {
                "title": "最高 token 七天",
                "labels": ["03/02", "03/07", "03/10", "03/03", "03/05", "03/09", "03/08"],
                "values": [3.0, 2.7, 2.5, 2.4, 2.2, 2.0, 1.5],
                "xlabel": "token（M）",
            },
        ),
        (
            "bar",
            {
                "title": "热门模型",
                "labels": ["openai/m2", "openai/m1"],
                "values": [3.0, 1.0],
                "xlabel": "token（M）",
            },
        ),
        (
            "pie",
            {
                "title": "token 构成（M）",
                "labels": ["输入 token", "输出 token", "推理 token"],
                "values": [0.4, 0.5, 0.1],
            },
        ),
    ]


def test_draw_chart_raises_when_chart_is_not_registered():
    app = cast(Any, OpenCodeTokenApp.__new__(OpenCodeTokenApp))
    app.charts = {}

    with pytest.raises(ChartRefreshError, match="not registered"):
        app._draw_chart("missing", lambda figure, **kwargs: None, title="Missing")


def test_refresh_analysis_charts_scale_tokens_to_millions_and_use_m_labels(monkeypatch):
    calls = []
    app = cast(Any, OpenCodeTokenApp.__new__(OpenCodeTokenApp))
    app.viewmodels = {
        "models": [
            {"provider": "openai", "model": "m1", "total_tokens": 1_000_000},
            {"provider": "openai", "model": "m2", "total_tokens": 3_000_000},
        ],
        "days": [
            {"day": "2024-03-10", "total_tokens": 2_500_000},
            {"day": "2024-03-09", "total_tokens": 2_000_000},
        ],
        "sessions": [
            {"session_id": "s1", "session_title": "", "total_tokens": 500_000},
            {"session_id": "s2", "session_title": "Demo", "total_tokens": 2_000_000},
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
                "title": "热门模型",
                "labels": ["openai/m2", "openai/m1"],
                "values": [3.0, 1.0],
                "xlabel": "token（M）",
            },
        ),
        (
            "line",
            {
                "title": "每日 token",
                "labels": ["03/09", "03/10"],
                "values": [2.0, 2.5],
                "ylabel": "token（M）",
            },
        ),
        (
            "bar",
            {
                "title": "热门会话",
                "labels": ["Demo", "s1"],
                "values": [2.0, 0.5],
                "xlabel": "token（M）",
            },
        ),
    ]
    assert calls[1][1]["labels"] == ["03/09", "03/10"]
    assert calls[1][1]["title"] == "每日 token"


def test_refresh_charts_isolates_overview_daily_data_preparation_failures(monkeypatch):
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
        "overview_peak_days": {"figure": object(), "canvas": None},
        "overview_models": {"figure": object(), "canvas": None},
        "overview_composition": {"figure": object(), "canvas": None},
        "models": {"figure": object(), "canvas": None},
        "days": {"figure": object(), "canvas": None},
        "sessions": {"figure": object(), "canvas": None},
    }

    monkeypatch.setattr(gui_module, "build_recent_day_chart_data", lambda rows: (_ for _ in ()).throw(KeyError("bad day")))
    monkeypatch.setattr(gui_module, "build_peak_day_chart_data", lambda rows: (_ for _ in ()).throw(KeyError("bad day")))
    monkeypatch.setattr(gui_module, "plot_line_chart", lambda figure, **kwargs: calls.append("line"))
    monkeypatch.setattr(gui_module, "plot_horizontal_bar_chart", lambda figure, **kwargs: calls.append("bar"))
    monkeypatch.setattr(gui_module, "plot_pie_chart", lambda figure, **kwargs: calls.append("pie"))

    warnings = app._refresh_charts()

    assert warnings == ["overview_daily: 'bad day'", "overview_peak_days: 'bad day'"]
    assert "bar" in calls
    assert "pie" in calls
    assert any(call[0] == "status" and "已加载，但图表有警告：图表刷新失败：'bad day'" in call[1] for call in calls if isinstance(call, tuple))


def test_refresh_charts_isolates_days_data_preparation_failures(monkeypatch):
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
        "overview_peak_days": {"figure": object(), "canvas": None},
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

    assert warnings == ["days: 'bad day'"]
    assert "bar" in calls
    assert "pie" in calls
    assert any(call[0] == "status" and "已加载，但图表有警告：图表刷新失败：'bad day'" in call[1] for call in calls if isinstance(call, tuple))


def test_user_chart_warning_recognizes_overview_peak_days():
    app = cast(Any, OpenCodeTokenApp.__new__(OpenCodeTokenApp))

    assert app._user_chart_warning("overview_peak_days: 'bad day'") == "'bad day'"


def test_refresh_charts_runs_overview_models_refresh_and_surfaces_its_warning():
    calls = []
    app = cast(Any, OpenCodeTokenApp.__new__(OpenCodeTokenApp))
    app.status_var = SimpleNamespace(set=lambda value: calls.append(("status", value)))
    app._refresh_overview_daily_chart = lambda: calls.append("overview_daily")
    app._refresh_overview_peak_days_chart = lambda: calls.append("overview_peak_days")

    def fail_overview_models():
        calls.append("overview_models")
        raise ChartRefreshError("overview_models: boom")

    app._refresh_overview_models_chart = fail_overview_models
    app._refresh_overview_composition_chart = lambda: calls.append("overview_composition")
    app._refresh_models_chart = lambda: calls.append("models")
    app._refresh_days_chart = lambda: calls.append("days")
    app._refresh_sessions_chart = lambda: calls.append("sessions")

    warnings = app._refresh_charts()

    assert warnings == ["overview_models: boom"]
    assert calls[:7] == [
        "overview_daily",
        "overview_peak_days",
        "overview_models",
        "overview_composition",
        "models",
        "days",
        "sessions",
    ]
    assert any(call[0] == "status" and "图表刷新失败：boom" in call[1] for call in calls if isinstance(call, tuple))


def test_build_overview_tab_registers_peak_days_chart_in_stable_2x2_grid(monkeypatch):
    labels = []
    registered = []
    chart_frames = []

    class FakeFrame:
        def __init__(self, parent=None, **kwargs):
            self.parent = parent
            self.kwargs = kwargs
            self.pack_calls = []
            self.grid_calls = []
            self.columnconfigure_calls = []
            self.rowconfigure_calls = []

        def pack(self, **kwargs):
            self.pack_calls.append(kwargs)

        def grid(self, **kwargs):
            self.grid_calls.append(kwargs)

        def columnconfigure(self, index, weight):
            self.columnconfigure_calls.append((index, weight))

        def rowconfigure(self, index, weight):
            self.rowconfigure_calls.append((index, weight))

    class FakeLabel:
        def __init__(self, parent=None, **kwargs):
            self.parent = parent
            self.kwargs = kwargs

        def grid(self, **kwargs):
            pass

    class FakeLabelFrame:
        def __init__(self, parent, text):
            self.parent = parent
            self.text = text
            self.grid_calls = []
            chart_frames.append(self)
            labels.append(text)

        def grid(self, **kwargs):
            self.grid_calls.append(kwargs)

    class FakeStyle:
        def configure(self, *args, **kwargs):
            pass

    class FakeCanvasWidget:
        def pack(self, **kwargs):
            pass

    class FakeCanvas:
        def get_tk_widget(self):
            return FakeCanvasWidget()

    monkeypatch.setattr(gui_module.ttk, "Frame", FakeFrame)
    monkeypatch.setattr(gui_module.ttk, "Label", FakeLabel)
    monkeypatch.setattr(gui_module.ttk, "LabelFrame", FakeLabelFrame)
    monkeypatch.setattr(gui_module.ttk, "Style", FakeStyle)
    monkeypatch.setattr(gui_module, "create_figure", lambda: object())
    monkeypatch.setattr(gui_module, "attach_canvas", lambda figure, master: FakeCanvas())

    app = cast(Any, OpenCodeTokenApp.__new__(OpenCodeTokenApp))
    app.tabs = {"总览": object()}
    app.charts = {}
    app._create_treeview = lambda parent, columns: object()
    app._register_chart = lambda name, figure, canvas: registered.append(name)

    app._build_overview_tab()

    overview_chart_area = app.overview_chart_area

    assert labels == ["每日", "最高 token 七天", "模型", "构成"]
    assert set(registered) == {
        "overview_daily",
        "overview_peak_days",
        "overview_models",
        "overview_composition",
    }
    assert chart_frames[0].grid_calls[0]["row"] == 0 and chart_frames[0].grid_calls[0]["column"] == 0
    assert chart_frames[1].grid_calls[0]["row"] == 0 and chart_frames[1].grid_calls[0]["column"] == 1
    assert chart_frames[2].grid_calls[0]["row"] == 1 and chart_frames[2].grid_calls[0]["column"] == 0
    assert chart_frames[3].grid_calls[0]["row"] == 1 and chart_frames[3].grid_calls[0]["column"] == 1
    assert overview_chart_area.columnconfigure_calls == [(0, 1), (1, 1)]
    assert overview_chart_area.rowconfigure_calls == [(0, 1), (1, 1)]
    assert overview_chart_area.pack_calls[0]["fill"] == "both"
    assert overview_chart_area.pack_calls[0]["expand"] is True


@pytest.mark.skipif(charts.Figure is None, reason="matplotlib unavailable")
def test_bar_chart_inverts_y_axis_so_first_ranked_label_renders_at_top():
    figure = charts.create_figure()
    assert figure is not None

    charts.plot_horizontal_bar_chart(
        figure,
        title="最高 token 七天",
        labels=["03/10", "03/09"],
        values=[2.5, 2.0],
    )

    axis = figure.axes[0]
    assert axis.yaxis_inverted()


@pytest.mark.skipif(charts.Figure is None, reason="matplotlib unavailable")
def test_bar_chart_renders_duplicate_labels_as_distinct_rows():
    figure = charts.create_figure()
    assert figure is not None

    charts.plot_horizontal_bar_chart(
        figure,
        title="最高 token 七天",
        labels=["03/02", "03/02", "03/01"],
        values=[300, 250, 200],
    )

    axis = figure.axes[0]
    assert len(axis.patches) == 3
    assert sorted({round(getattr(patch, "get_y")(), 6) for patch in axis.patches}) == [-0.4, 0.6, 1.6]
    assert [tick.get_text() for tick in axis.get_yticklabels()] == ["03/02", "03/02", "03/01"]


def test_browse_db_localizes_file_dialog(monkeypatch):
    captured = {}
    app = cast(Any, OpenCodeTokenApp.__new__(OpenCodeTokenApp))
    app.db_path_var = SimpleNamespace(set=lambda value: captured.setdefault("db_path", value))
    app.export_dir_var = SimpleNamespace(set=lambda value: captured.setdefault("export_dir", value))

    def fake_askopenfilename(**kwargs):
        captured["dialog"] = kwargs
        return r"C:\demo\opencode.db"

    monkeypatch.setattr(gui_module.filedialog, "askopenfilename", fake_askopenfilename)

    app.browse_db()

    assert captured["dialog"] == {
        "title": "选择 opencode.db",
        "filetypes": [("SQLite 数据库", "*.db"), ("所有文件", "*")],
    }
    assert captured["db_path"] == r"C:\demo\opencode.db"
    assert captured["export_dir"].endswith("token_export")


def test_build_header_uses_single_load_data_action(monkeypatch):
    buttons = []

    class FakeFrame:
        def __init__(self, *args, **kwargs):
            pass

        def pack(self, **kwargs):
            pass

        def columnconfigure(self, index, weight):
            pass

    class FakeLabel:
        def __init__(self, *args, **kwargs):
            pass

        def grid(self, **kwargs):
            pass

    class FakeEntry:
        def __init__(self, *args, **kwargs):
            pass

        def grid(self, **kwargs):
            pass

    class FakeButton:
        def __init__(self, parent, text, command):
            buttons.append({"text": text, "command": command})

        def grid(self, **kwargs):
            pass

    monkeypatch.setattr(gui_module.ttk, "Frame", FakeFrame)
    monkeypatch.setattr(gui_module.ttk, "Label", FakeLabel)
    monkeypatch.setattr(gui_module.ttk, "Entry", FakeEntry)
    monkeypatch.setattr(gui_module.ttk, "Button", FakeButton)

    app = cast(Any, OpenCodeTokenApp.__new__(OpenCodeTokenApp))
    app.db_path_var = object()
    app.export_dir_var = object()
    app.status_var = object()
    app.browse_db = lambda: None
    app.load_and_export_data = lambda: None

    app._build_header()

    button_texts = [button["text"] for button in buttons]
    assert button_texts == ["浏览", "加载数据"]
    assert all(text not in button_texts for text in ["重新加载", "导出 CSV"])
    assert buttons[-1]["command"] is app.load_and_export_data


def test_schedule_initial_load_uses_after_idle_with_load_data_only():
    captured = []
    loads = []
    app = cast(Any, OpenCodeTokenApp.__new__(OpenCodeTokenApp))
    app.master = SimpleNamespace(after_idle=lambda callback: captured.append(callback) or "idle-1")
    app.load_data = lambda: loads.append("load")

    app._schedule_initial_load()

    assert len(captured) == 1
    assert app._initial_load_after_id == "idle-1"
    assert app._initial_load_pending is True
    captured[0]()
    assert loads == ["load"]
    assert app._initial_load_after_id is None
    assert app._initial_load_pending is False


def test_init_registers_one_initial_load_callback_and_invokes_load_once(monkeypatch):
    callbacks = []
    loads = []

    class FakeMaster:
        def after_idle(self, callback):
            callbacks.append(callback)

    monkeypatch.setattr(gui_module.ttk.Frame, "__init__", lambda self, master: None)
    monkeypatch.setattr(gui_module.ttk.Frame, "pack", lambda self, **kwargs: None)
    monkeypatch.setattr(gui_module.tk, "StringVar", lambda value="": SimpleNamespace(get=lambda: value, set=lambda new: None))
    monkeypatch.setattr(gui_module, "default_db_path", lambda: Path(r"C:\demo\opencode.db"))
    monkeypatch.setattr(OpenCodeTokenApp, "_build_header", lambda self: None)
    monkeypatch.setattr(OpenCodeTokenApp, "_build_notebook", lambda self: None)
    monkeypatch.setattr(OpenCodeTokenApp, "load_data", lambda self: loads.append("load"))

    app = OpenCodeTokenApp(FakeMaster())

    assert len(callbacks) == 1
    callbacks[0]()
    assert loads == ["load"]
    assert app.master is not None


def test_init_startup_existing_db_loads_without_export(monkeypatch):
    callbacks = []
    calls = []

    class FakeMaster:
        def after_idle(self, callback):
            callbacks.append(callback)

    monkeypatch.setattr(gui_module.ttk.Frame, "__init__", lambda self, master: None)
    monkeypatch.setattr(gui_module.ttk.Frame, "pack", lambda self, **kwargs: None)
    monkeypatch.setattr(gui_module.tk, "StringVar", lambda value="": SimpleNamespace(get=lambda: value, set=lambda new: calls.append(("status", new))))
    monkeypatch.setattr(gui_module, "default_db_path", lambda: Path(r"C:\demo\opencode.db"))
    monkeypatch.setattr(OpenCodeTokenApp, "_build_header", lambda self: None)
    monkeypatch.setattr(OpenCodeTokenApp, "_build_notebook", lambda self: None)
    monkeypatch.setattr(Path, "exists", lambda self: True)
    monkeypatch.setattr(gui_module, "load_usage_from_db", lambda path: {"summary": {}})
    monkeypatch.setattr(gui_module, "price_loaded_usage", lambda datasets, entry_path=None: datasets)
    monkeypatch.setattr(
        gui_module,
        "build_application_viewmodels",
        lambda datasets: {"overview": {"cards": {}, "daily_rows": []}, "models": [], "days": [], "sessions": [], "raw_messages": []},
    )
    monkeypatch.setattr(gui_module, "export_usage_csvs", lambda out_dir, datasets: calls.append(("export", out_dir)))

    app = OpenCodeTokenApp(FakeMaster())
    app._reset_raw_message_pagination = lambda: None
    app._populate_view = lambda: []
    callbacks[0]()

    assert not any(call[0] == "export" for call in calls)


def test_init_startup_does_not_show_export_failure_dialog_before_user_action(monkeypatch):
    callbacks = []
    calls = []

    class FakeMaster:
        def after_idle(self, callback):
            callbacks.append(callback)

    monkeypatch.setattr(gui_module.ttk.Frame, "__init__", lambda self, master: None)
    monkeypatch.setattr(gui_module.ttk.Frame, "pack", lambda self, **kwargs: None)
    monkeypatch.setattr(gui_module.tk, "StringVar", lambda value="": SimpleNamespace(get=lambda: value, set=lambda new: calls.append(("status", new))))
    monkeypatch.setattr(gui_module, "default_db_path", lambda: Path(r"C:\demo\opencode.db"))
    monkeypatch.setattr(OpenCodeTokenApp, "_build_header", lambda self: None)
    monkeypatch.setattr(OpenCodeTokenApp, "_build_notebook", lambda self: None)
    monkeypatch.setattr(Path, "exists", lambda self: True)
    monkeypatch.setattr(gui_module, "load_usage_from_db", lambda path: {"summary": {}})
    monkeypatch.setattr(gui_module, "price_loaded_usage", lambda datasets, entry_path=None: datasets)
    monkeypatch.setattr(
        gui_module,
        "build_application_viewmodels",
        lambda datasets: {"overview": {"cards": {}, "daily_rows": []}, "models": [], "days": [], "sessions": [], "raw_messages": []},
    )
    monkeypatch.setattr(gui_module, "export_usage_csvs", lambda out_dir, datasets: (_ for _ in ()).throw(RuntimeError("磁盘满了")))
    monkeypatch.setattr(gui_module.messagebox, "showerror", lambda *args: calls.append(("dialog", args)))

    app = OpenCodeTokenApp(FakeMaster())
    app._reset_raw_message_pagination = lambda: None
    app._populate_view = lambda: []
    callbacks[0]()

    assert not any(call[0] == "dialog" for call in calls)


def test_init_startup_missing_default_db_sets_status_without_dialog(monkeypatch):
    callbacks = []
    calls = []

    class FakeMaster:
        def after_idle(self, callback):
            callbacks.append(callback)

    def fake_string_var(value=""):
        current = {"value": value}
        return SimpleNamespace(
            get=lambda: current["value"],
            set=lambda new: current.__setitem__("value", new) or calls.append(("status", new)),
        )

    monkeypatch.setattr(gui_module.ttk.Frame, "__init__", lambda self, master: None)
    monkeypatch.setattr(gui_module.ttk.Frame, "pack", lambda self, **kwargs: None)
    monkeypatch.setattr(gui_module.tk, "StringVar", fake_string_var)
    monkeypatch.setattr(gui_module, "default_db_path", lambda: Path(r"C:\missing\opencode.db"))
    monkeypatch.setattr(OpenCodeTokenApp, "_build_header", lambda self: None)
    monkeypatch.setattr(OpenCodeTokenApp, "_build_notebook", lambda self: None)
    monkeypatch.setattr(gui_module.messagebox, "showerror", lambda *args: calls.append(("dialog", args)))
    monkeypatch.setattr(Path, "exists", lambda self: False)

    OpenCodeTokenApp(FakeMaster())

    assert len(callbacks) == 1
    callbacks[0]()
    assert calls[-1] == ("status", "未找到数据库；请手动选择文件。")
    assert not any(call[0] == "dialog" for call in calls)


def test_manual_load_before_idle_callback_does_not_trigger_second_startup_load(monkeypatch):
    callbacks = {}
    cancelled = []
    loads = []

    class FakeMaster:
        def after_idle(self, callback):
            callbacks["startup"] = callback
            return "idle-1"

        def after_cancel(self, callback_id):
            cancelled.append(callback_id)

    monkeypatch.setattr(gui_module.ttk.Frame, "__init__", lambda self, master: None)
    monkeypatch.setattr(gui_module.ttk.Frame, "pack", lambda self, **kwargs: None)
    monkeypatch.setattr(gui_module.tk, "StringVar", lambda value="": SimpleNamespace(get=lambda: value, set=lambda new: None))
    monkeypatch.setattr(gui_module, "default_db_path", lambda: Path(r"C:\demo\opencode.db"))
    monkeypatch.setattr(OpenCodeTokenApp, "_build_header", lambda self: None)
    monkeypatch.setattr(OpenCodeTokenApp, "_build_notebook", lambda self: None)
    monkeypatch.setattr(gui_module, "load_usage_from_db", lambda path: loads.append("load") or {"summary": {}})
    monkeypatch.setattr(gui_module, "price_loaded_usage", lambda datasets, entry_path=None: datasets)
    monkeypatch.setattr(
        gui_module,
        "build_application_viewmodels",
        lambda datasets: {"overview": {"cards": {}, "daily_rows": []}, "models": [], "days": [], "sessions": [], "raw_messages": []},
    )
    monkeypatch.setattr(gui_module, "export_usage_csvs", lambda out_dir, datasets: out_dir)
    monkeypatch.setattr(Path, "exists", lambda self: True)

    app = OpenCodeTokenApp(FakeMaster())
    app._reset_raw_message_pagination = lambda: None
    app._populate_view = lambda: []

    app.load_and_export_data()
    callbacks["startup"]()

    assert cancelled == ["idle-1"]
    assert loads == ["load"]


def test_load_and_export_data_loads_once_and_reuses_datasets_for_view_and_export(monkeypatch):
    calls = []
    db_path = Path(r"C:\demo\opencode.db")
    datasets = {"summary": {"total_tokens": 1}}
    viewmodels = {"overview": {"cards": {}, "daily_rows": []}, "models": [], "days": [], "sessions": [], "raw_messages": []}
    export_path = Path(r"C:\demo\token_export")
    app = cast(Any, OpenCodeTokenApp.__new__(OpenCodeTokenApp))
    app.db_path_var = SimpleNamespace(get=lambda: str(db_path))
    app.export_dir_var = SimpleNamespace(set=lambda value: calls.append(("export_dir", value)))
    app.status_var = SimpleNamespace(set=lambda value: calls.append(("status", value)))
    app.entry_path = Path("entry.json")
    app.viewmodels = {"existing": True}
    app._reset_raw_message_pagination = lambda: calls.append(("reset_paging", app.viewmodels))
    app._populate_view = lambda: calls.append(("populate", app.viewmodels)) or []

    monkeypatch.setattr(Path, "exists", lambda self: True)
    monkeypatch.setattr(gui_module, "load_usage_from_db", lambda path: calls.append(("load", path)) or datasets)
    monkeypatch.setattr(
        gui_module,
        "price_loaded_usage",
        lambda loaded, entry_path=None: calls.append(("price", loaded, entry_path)) or loaded,
    )
    monkeypatch.setattr(
        gui_module,
        "build_application_viewmodels",
        lambda loaded: calls.append(("build", loaded)) or viewmodels,
    )
    monkeypatch.setattr(
        gui_module,
        "export_usage_csvs",
        lambda out_dir, loaded: calls.append(("export", out_dir, loaded)) or export_path,
    )
    monkeypatch.setattr(gui_module.messagebox, "showerror", lambda *args: calls.append(("dialog", args)))

    app.load_and_export_data()

    assert calls[1] == ("load", db_path)
    assert calls[2] == ("price", datasets, Path("entry.json"))
    assert calls[3] == ("build", datasets)
    assert calls[4] == ("reset_paging", viewmodels)
    assert calls[5] == ("populate", viewmodels)
    assert calls[6] == ("export", db_path.resolve().parent / "token_export", datasets)
    assert app.viewmodels is viewmodels


def test_load_and_export_data_missing_db_sets_status_without_dialog(monkeypatch):
    calls = []
    app = cast(Any, OpenCodeTokenApp.__new__(OpenCodeTokenApp))
    app.db_path_var = SimpleNamespace(get=lambda: r"C:\missing\opencode.db")
    app.export_dir_var = SimpleNamespace(set=lambda value: calls.append(("export_dir", value)))
    app.status_var = SimpleNamespace(set=lambda value: calls.append(("status", value)))
    app.entry_path = None
    app.viewmodels = {"existing": True}

    monkeypatch.setattr(Path, "exists", lambda self: False)
    monkeypatch.setattr(gui_module.messagebox, "showerror", lambda *args: calls.append(("dialog", args)))

    app.load_and_export_data()

    assert calls[-1] == ("status", "未找到数据库；请手动选择文件。")
    assert not any(call[0] == "dialog" for call in calls)
    assert app.viewmodels == {"existing": True}


def test_load_and_export_data_export_failure_keeps_loaded_viewmodels_visible(monkeypatch):
    calls = []
    db_path = Path(r"C:\demo\opencode.db")
    datasets = {"summary": {"total_tokens": 1}}
    new_viewmodels = {"overview": {"cards": {}, "daily_rows": []}, "models": [], "days": [], "sessions": [], "raw_messages": []}
    app = cast(Any, OpenCodeTokenApp.__new__(OpenCodeTokenApp))
    app.db_path_var = SimpleNamespace(get=lambda: str(db_path))
    app.export_dir_var = SimpleNamespace(set=lambda value: calls.append(("export_dir", value)))
    app.status_var = SimpleNamespace(set=lambda value: calls.append(("status", value)))
    app.entry_path = None
    app.viewmodels = {"existing": True}
    app._reset_raw_message_pagination = lambda: calls.append(("reset_paging", app.viewmodels))
    app._populate_view = lambda: calls.append(("populate", app.viewmodels)) or []

    monkeypatch.setattr(Path, "exists", lambda self: True)
    monkeypatch.setattr(gui_module, "load_usage_from_db", lambda path: datasets)
    monkeypatch.setattr(gui_module, "price_loaded_usage", lambda loaded, entry_path=None: loaded)
    monkeypatch.setattr(gui_module, "build_application_viewmodels", lambda loaded: new_viewmodels)
    monkeypatch.setattr(gui_module, "export_usage_csvs", lambda out_dir, loaded: (_ for _ in ()).throw(RuntimeError("磁盘满了")))
    monkeypatch.setattr(gui_module.messagebox, "showerror", lambda *args: calls.append(("dialog", args)))

    app.load_and_export_data()

    assert ("populate", new_viewmodels) in calls
    assert app.viewmodels is new_viewmodels
    assert calls[-2] == ("status", "导出失败：磁盘满了")
    assert calls[-1] == ("dialog", ("导出失败", "导出失败：磁盘满了"))


def test_load_and_export_data_load_failure_preserves_existing_view(monkeypatch):
    calls = []
    app = cast(Any, OpenCodeTokenApp.__new__(OpenCodeTokenApp))
    app.db_path_var = SimpleNamespace(get=lambda: r"C:\demo\opencode.db")
    app.export_dir_var = SimpleNamespace(set=lambda value: calls.append(("export_dir", value)))
    app.status_var = SimpleNamespace(set=lambda value: calls.append(("status", value)))
    app.entry_path = None
    app.viewmodels = {"existing": True}
    app._reset_raw_message_pagination = lambda: calls.append(("reset_paging", app.viewmodels))
    app._populate_view = lambda: calls.append(("populate", app.viewmodels)) or []

    monkeypatch.setattr(Path, "exists", lambda self: True)
    monkeypatch.setattr(gui_module, "load_usage_from_db", lambda path: (_ for _ in ()).throw(RuntimeError("坏了")))
    monkeypatch.setattr(gui_module.messagebox, "showerror", lambda *args: calls.append(("dialog", args)))

    app.load_and_export_data()

    assert app.viewmodels == {"existing": True}
    assert ("populate", {"existing": True}) not in calls
    assert calls[-2] == ("status", "加载失败：坏了")
    assert calls[-1] == ("dialog", ("加载失败", "加载失败：坏了"))


def test_load_and_export_data_success_keeps_chart_warning_status(monkeypatch):
    calls = []
    db_path = Path(r"C:\demo\opencode.db")
    datasets = {"summary": {"total_tokens": 1}}
    new_viewmodels = {"overview": {"cards": {}, "daily_rows": []}, "models": [], "days": [], "sessions": [], "raw_messages": []}
    app = cast(Any, OpenCodeTokenApp.__new__(OpenCodeTokenApp))
    app.db_path_var = SimpleNamespace(get=lambda: str(db_path))
    app.export_dir_var = SimpleNamespace(set=lambda value: calls.append(("export_dir", value)))
    app.status_var = SimpleNamespace(set=lambda value: calls.append(("status", value)))
    app.entry_path = None
    app.viewmodels = None
    app._reset_raw_message_pagination = lambda: None
    app._populate_view = lambda: ["boom"]

    monkeypatch.setattr(Path, "exists", lambda self: True)
    monkeypatch.setattr(gui_module, "load_usage_from_db", lambda path: datasets)
    monkeypatch.setattr(gui_module, "price_loaded_usage", lambda loaded, entry_path=None: loaded)
    monkeypatch.setattr(gui_module, "build_application_viewmodels", lambda loaded: new_viewmodels)
    monkeypatch.setattr(gui_module, "export_usage_csvs", lambda out_dir, loaded: db_path.parent / "token_export")
    monkeypatch.setattr(gui_module.messagebox, "showerror", lambda *args: calls.append(("dialog", args)))

    app.load_and_export_data()

    assert all(call != ("status", f"已加载并导出到 {db_path.parent / 'token_export'}") for call in calls)


def test_main_sets_localized_window_title(monkeypatch):
    calls = []

    class FakeRoot:
        def title(self, value):
            calls.append(("title", value))

        def geometry(self, value):
            calls.append(("geometry", value))

        def mainloop(self):
            calls.append(("mainloop", None))

    fake_root = FakeRoot()
    monkeypatch.setattr(opencode_token_gui.tk, "Tk", lambda: fake_root)
    monkeypatch.setattr(opencode_token_gui, "OpenCodeTokenApp", lambda root, entry_path=None: calls.append(("app", root, entry_path)))

    opencode_token_gui.main()

    assert calls[0] == ("title", "OpenCode Token 图形界面")
