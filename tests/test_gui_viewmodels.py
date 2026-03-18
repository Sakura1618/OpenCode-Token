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
        "raw_messages": [{"day": "2024-03-09", "provider": "OpenAI", "model": "gpt-4.1-mini", "estimated_cost": 1.5, "cost": 1.2, "price_status": "priced"}],
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
    assert app.overview_card_labels["estimated_cost_total"].text == "预估价格（美元）: $1.50 USD"
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
        "estimated_cost_display": "预估价格（美元）",
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

    assert labels == ["2024-03-09", "2024-03-10"]
    assert values == [10, 20]


def test_overview_composition_chart_uses_input_output_reasoning_cards():
    labels, values = gui_module.build_overview_composition_chart_data(
        {"input_tokens": 40, "output_tokens": 50, "reasoning_tokens": 10}
    )

    assert labels == ["输入 token", "输出 token", "推理 token"]
    assert values == [40, 50, 10]


def test_scale_tokens_to_millions_handles_bad_inputs_and_scales_numbers():
    assert gui_module.scale_tokens_to_millions([2_000_000, None, "bad", 500_000]) == [2.0, 0.0, 0.0, 0.5]


def test_refresh_overview_chart_methods_scale_tokens_to_millions_and_use_m_labels(monkeypatch):
    calls = []
    app = cast(Any, OpenCodeTokenApp.__new__(OpenCodeTokenApp))
    app.viewmodels = {
        "overview": {
            "cards": {"input_tokens": 400_000, "output_tokens": 500_000, "reasoning_tokens": 100_000},
            "daily_rows": [
                {"day": "2024-03-10", "total_tokens": 2_500_000},
                {"day": "2024-03-09", "total_tokens": 2_000_000},
            ],
        },
        "models": [
            {"provider": "openai", "model": "m1", "total_tokens": 1_000_000},
            {"provider": "openai", "model": "m2", "total_tokens": 3_000_000},
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
                "title": "每日 token",
                "labels": ["2024-03-09", "2024-03-10"],
                "values": [2.0, 2.5],
                "ylabel": "token（M）",
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
                "labels": ["2024-03-09", "2024-03-10"],
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
    assert any(call[0] == "status" and "已加载，但图表有警告：图表刷新失败：'bad day'" in call[1] for call in calls if isinstance(call, tuple))


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
