import os
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from opencode_token_app.charts import (
    attach_canvas,
    create_figure,
    plot_horizontal_bar_chart,
    plot_line_chart,
    plot_pie_chart,
)
from opencode_token_app.data_loader import load_usage_from_db
from opencode_token_app.exporter import export_usage_csvs
from opencode_token_app.pricing import price_loaded_usage
from opencode_token_app.viewmodels import build_application_viewmodels


LABEL_TEXT = {
    "db_path": "数据库路径",
    "browse": "浏览",
    "reload": "重新加载",
    "export_csv": "导出 CSV",
    "export_dir": "导出目录",
    "filter_day": "日期",
    "filter_provider": "提供方",
    "filter_model": "模型",
    "chart": "图表",
    "daily": "每日",
    "models": "模型",
    "composition": "构成",
    "day": "日期",
    "provider": "提供方",
    "model": "模型",
    "role": "角色",
    "time_created_text": "时间",
    "session_id": "会话 ID",
    "session_title": "会话标题",
    "message_count": "消息数",
    "total_tokens": "总 token",
    "input_tokens": "输入 token",
    "output_tokens": "输出 token",
    "reasoning_tokens": "推理 token",
    "total_tokens_display": "总 token",
    "input_tokens_display": "输入 token",
    "output_tokens_display": "输出 token",
    "estimated_cost_total": "预估价格（美元）",
    "estimated_cost_total_display": "预估价格（美元）",
    "recorded_cost_total": "已记录价格（美元）",
    "recorded_cost_total_display": "已记录价格（美元）",
    "estimated_cost_display": "预估价格（美元）",
    "recorded_cost_display": "已记录价格（美元）",
    "price_status_label": "定价状态",
}


def default_db_path() -> Path:
    return Path(os.environ.get("USERPROFILE", "~")).expanduser() / ".local" / "share" / "opencode" / "opencode.db"


class ChartRefreshError(RuntimeError):
    pass


def ui_text(key: str) -> str:
    return LABEL_TEXT.get(key) or key


def scale_tokens_to_millions(values):
    scaled = []
    for value in values:
        try:
            scaled.append(float(value) / 1_000_000)
        except (TypeError, ValueError):
            scaled.append(0.0)
    return scaled


def build_top_model_chart_data(rows):
    sorted_rows = sorted(rows, key=lambda row: row.get("total_tokens", 0) or 0, reverse=True)[:10]
    labels = []
    values = []
    for row in sorted_rows:
        provider = row.get("provider", "") or ""
        model = row.get("model", "") or ""
        labels.append(f"{provider}/{model}" if provider and model else provider or model)
        values.append(row.get("total_tokens", 0) or 0)
    return labels, values


def build_day_chart_data(rows):
    sorted_rows = sorted(rows, key=lambda row: row.get("day", "") or "")
    labels = [row.get("day", "") or "" for row in sorted_rows]
    values = [row.get("total_tokens", 0) or 0 for row in sorted_rows]
    return labels, values


def build_top_session_chart_data(rows):
    sorted_rows = sorted(rows, key=lambda row: row.get("total_tokens", 0) or 0, reverse=True)[:10]
    labels = [
        (row.get("session_title", "") or row.get("session_id", "") or "")
        for row in sorted_rows
    ]
    values = [row.get("total_tokens", 0) or 0 for row in sorted_rows]
    return labels, values


def build_overview_composition_chart_data(cards):
    return ["输入 token", "输出 token", "推理 token"], [
        cards.get("input_tokens", 0) or 0,
        cards.get("output_tokens", 0) or 0,
        cards.get("reasoning_tokens", 0) or 0,
    ]


class OpenCodeTokenApp(ttk.Frame):
    def __init__(self, master, entry_path=None):
        super().__init__(master)
        self.master = master
        self.entry_path = entry_path
        self.db_path_var = tk.StringVar(value=str(default_db_path()))
        self.export_dir_var = tk.StringVar(value=str(default_db_path().parent / "token_export"))
        self.status_var = tk.StringVar(value="就绪")
        self.viewmodels = None
        self.treeviews = {}
        self.charts = {}
        self.pack(fill="both", expand=True)
        self._build_header()
        self._build_notebook()

    def _build_header(self):
        header = ttk.Frame(self)
        header.pack(fill="x", padx=8, pady=8)
        ttk.Label(header, text=ui_text("db_path")).grid(row=0, column=0, sticky="w")
        ttk.Entry(header, textvariable=self.db_path_var, width=80).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Button(header, text=ui_text("browse"), command=self.browse_db).grid(row=0, column=2, padx=4)
        ttk.Button(header, text=ui_text("reload"), command=self.load_current_db).grid(row=0, column=3, padx=4)
        ttk.Button(header, text=ui_text("export_csv"), command=self.export_current_csvs).grid(row=0, column=4, padx=4)
        ttk.Label(header, text=ui_text("export_dir")).grid(row=1, column=0, sticky="w")
        ttk.Label(header, textvariable=self.export_dir_var).grid(row=1, column=1, columnspan=4, sticky="w", padx=6)
        ttk.Label(header, textvariable=self.status_var).grid(row=2, column=0, columnspan=5, sticky="w")
        header.columnconfigure(1, weight=1)

    def _build_notebook(self):
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.tabs = {}
        for title in ["总览", "模型分析", "按日分析", "会话分析", "明细数据"]:
            frame = ttk.Frame(self.notebook)
            self.notebook.add(frame, text=title)
            self.tabs[title] = frame
        self._build_overview_tab()
        self._build_analysis_tab("模型分析", "models")
        self._build_analysis_tab("按日分析", "days")
        self._build_analysis_tab("会话分析", "sessions")
        self._build_raw_tab()

    def _build_overview_tab(self):
        frame = self.tabs["总览"]
        self.overview_cards = ttk.Frame(frame)
        self.overview_cards.pack(fill="x", padx=8, pady=8)
        self.overview_card_labels = {}
        for idx, key in enumerate(["total_tokens", "input_tokens", "output_tokens", "reasoning_tokens", "estimated_cost_total", "recorded_cost_total"]):
            label = ttk.Label(self.overview_cards, text=f"{ui_text(key)}: -")
            label.grid(row=0, column=idx, padx=4, sticky="w")
            self.overview_card_labels[key] = label

        self.overview_chart_area = ttk.Frame(frame)
        self.overview_chart_area.pack(fill="both", expand=False, padx=8, pady=8)
        for name in ["daily", "models", "composition"]:
            chart_frame = ttk.LabelFrame(self.overview_chart_area, text=ui_text(name))
            chart_frame.pack(side="left", fill="both", expand=True, padx=4)
            figure = create_figure()
            canvas = attach_canvas(figure, chart_frame)
            self._register_chart(f"overview_{name}", figure, canvas)
            if canvas is not None:
                canvas.get_tk_widget().pack(fill="both", expand=True)

        self.overview_table = self._create_treeview(frame, ["day", "total_tokens_display", "estimated_cost_display"])

    def _build_analysis_tab(self, title, key):
        frame = self.tabs[title]
        chart_frame = ttk.LabelFrame(frame, text=ui_text("chart"))
        chart_frame.pack(fill="both", expand=False, padx=8, pady=8)
        figure = create_figure()
        canvas = attach_canvas(figure, chart_frame)
        self._register_chart(key, figure, canvas)
        if canvas is not None:
            canvas.get_tk_widget().pack(fill="both", expand=True)
        if key == "models":
            columns = ["provider", "model", "message_count", "total_tokens_display", "estimated_cost_display", "recorded_cost_display", "price_status_label"]
        elif key == "days":
            columns = ["day", "message_count", "total_tokens_display", "estimated_cost_display", "recorded_cost_display"]
        else:
            columns = ["session_id", "session_title", "message_count", "total_tokens_display", "estimated_cost_display", "recorded_cost_display"]
        self.treeviews[key] = self._create_treeview(frame, columns)

    def _build_raw_tab(self):
        frame = self.tabs["明细数据"]
        filters = ttk.Frame(frame)
        filters.pack(fill="x", padx=8, pady=8)
        ttk.Label(filters, text=ui_text("filter_day")).grid(row=0, column=0, padx=4)
        ttk.Entry(filters).grid(row=0, column=1, padx=4)
        ttk.Label(filters, text=ui_text("filter_provider")).grid(row=0, column=2, padx=4)
        ttk.Entry(filters).grid(row=0, column=3, padx=4)
        ttk.Label(filters, text=ui_text("filter_model")).grid(row=0, column=4, padx=4)
        ttk.Entry(filters).grid(row=0, column=5, padx=4)
        columns = ["provider", "model", "role", "time_created_text", "total_tokens_display", "input_tokens_display", "output_tokens_display", "estimated_cost_display", "recorded_cost_display", "price_status_label"]
        self.treeviews["raw_messages"] = self._create_treeview(frame, columns)

    def _create_treeview(self, parent, columns):
        tree = ttk.Treeview(parent, columns=columns, show="headings", height=8)
        for column in columns:
            tree.heading(column, text=ui_text(column))
            tree.column(column, width=120, stretch=True)
        tree.pack(fill="both", expand=True, padx=8, pady=8)
        return tree

    def browse_db(self):
        selected = filedialog.askopenfilename(
            title="选择 opencode.db",
            filetypes=[("SQLite 数据库", "*.db"), ("所有文件", "*")],
        )
        if selected:
            self.db_path_var.set(selected)
            self.export_dir_var.set(str(Path(selected).resolve().parent / "token_export"))

    def load_current_db(self):
        db_path = Path(self.db_path_var.get()).expanduser()
        self.export_dir_var.set(str(db_path.resolve().parent / "token_export"))
        if not db_path.exists():
            self.status_var.set("未找到数据库；请手动选择文件。")
            return
        try:
            datasets = load_usage_from_db(db_path)
            datasets = price_loaded_usage(datasets, entry_path=self.entry_path)
            self.viewmodels = build_application_viewmodels(datasets)
            warnings = self._populate_view()
            if not warnings:
                self.status_var.set("已加载")
        except Exception as exc:  # pragma: no cover
            self.status_var.set(f"加载失败：{exc}")
            messagebox.showerror("加载失败", f"加载失败：{exc}")

    def _populate_view(self):
        viewmodels = self.viewmodels
        if viewmodels is None:
            return []
        overview = viewmodels["overview"]
        for key, label in self.overview_card_labels.items():
            display_key = f"{key}_display"
            value = overview["cards"].get(display_key, overview["cards"].get(key, ""))
            label.configure(text=f"{ui_text(key)}: {value}")
        self._fill_tree(self.overview_table, overview["daily_rows"])
        self._fill_tree(self.treeviews["models"], viewmodels["models"])
        self._fill_tree(self.treeviews["days"], viewmodels["days"])
        self._fill_tree(self.treeviews["sessions"], viewmodels["sessions"])
        self._fill_tree(self.treeviews["raw_messages"], viewmodels["raw_messages"])
        return self._refresh_charts()

    def _register_chart(self, name, figure, canvas):
        self.charts[name] = {"figure": figure, "canvas": canvas}

    def _chart_refs(self, name):
        return self.charts.get(name, {})

    def _draw_chart(self, name, plotter, *args, **kwargs):
        chart = self._chart_refs(name)
        if not chart:
            raise ChartRefreshError(f"Chart '{name}' is not registered")
        figure = chart.get("figure")
        canvas = chart.get("canvas")
        try:
            plotter(figure, *args, **kwargs)
            if canvas is not None:
                canvas.draw()
        except Exception as exc:
            raise ChartRefreshError(f"{name}: {exc}") from exc

    def _set_chart_warning_status(self, warnings):
        if warnings:
            localized = [f"图表刷新失败：{self._user_chart_warning(warning)}" for warning in warnings]
            self.status_var.set(f"已加载，但图表有警告：{'; '.join(localized)}")

    def _user_chart_warning(self, warning):
        prefix, _, remainder = warning.partition(": ")
        if prefix in {"overview_daily", "overview_models", "overview_composition", "models", "days", "sessions"} and remainder:
            return remainder
        return warning

    def _refresh_charts(self):
        warnings = []
        for refresh in (
            self._refresh_overview_daily_chart,
            self._refresh_overview_models_chart,
            self._refresh_overview_composition_chart,
            self._refresh_models_chart,
            self._refresh_days_chart,
            self._refresh_sessions_chart,
        ):
            try:
                refresh()
            except ChartRefreshError as exc:
                warnings.append(str(exc))
        self._set_chart_warning_status(warnings)
        return warnings

    def _refresh_overview_daily_chart(self):
        try:
            viewmodels = self.viewmodels
            if viewmodels is None:
                return
            overview = viewmodels["overview"]
            day_labels, day_values = build_day_chart_data(overview.get("daily_rows", []))
            self._draw_chart(
                "overview_daily",
                plot_line_chart,
                title="每日 token",
                labels=day_labels,
                values=scale_tokens_to_millions(day_values),
                ylabel="token（M）",
            )
        except ChartRefreshError:
            raise
        except Exception as exc:
            raise ChartRefreshError(f"overview_daily: {exc}") from exc

    def _refresh_overview_models_chart(self):
        try:
            viewmodels = self.viewmodels
            if viewmodels is None:
                return
            model_labels, model_values = build_top_model_chart_data(viewmodels.get("models", []))
            self._draw_chart(
                "overview_models",
                plot_horizontal_bar_chart,
                title="热门模型",
                labels=model_labels,
                values=scale_tokens_to_millions(model_values),
                xlabel="token（M）",
            )
        except ChartRefreshError:
            raise
        except Exception as exc:
            raise ChartRefreshError(f"overview_models: {exc}") from exc

    def _refresh_overview_composition_chart(self):
        try:
            viewmodels = self.viewmodels
            if viewmodels is None:
                return
            overview = viewmodels["overview"]
            composition_labels, composition_values = build_overview_composition_chart_data(
                overview.get("cards", {})
            )
            self._draw_chart(
                "overview_composition",
                plot_pie_chart,
                title="token 构成（M）",
                labels=composition_labels,
                values=scale_tokens_to_millions(composition_values),
            )
        except ChartRefreshError:
            raise
        except Exception as exc:
            raise ChartRefreshError(f"overview_composition: {exc}") from exc

    def _refresh_models_chart(self):
        try:
            viewmodels = self.viewmodels
            if viewmodels is None:
                return
            labels, values = build_top_model_chart_data(viewmodels.get("models", []))
            self._draw_chart(
                "models",
                plot_horizontal_bar_chart,
                title="热门模型",
                labels=labels,
                values=scale_tokens_to_millions(values),
                xlabel="token（M）",
            )
        except ChartRefreshError:
            raise
        except Exception as exc:
            raise ChartRefreshError(f"models: {exc}") from exc

    def _refresh_days_chart(self):
        try:
            viewmodels = self.viewmodels
            if viewmodels is None:
                return
            labels, values = build_day_chart_data(viewmodels.get("days", []))
            self._draw_chart(
                "days",
                plot_line_chart,
                title="每日 token",
                labels=labels,
                values=scale_tokens_to_millions(values),
                ylabel="token（M）",
            )
        except ChartRefreshError:
            raise
        except Exception as exc:
            raise ChartRefreshError(f"days: {exc}") from exc

    def _refresh_sessions_chart(self):
        try:
            viewmodels = self.viewmodels
            if viewmodels is None:
                return
            labels, values = build_top_session_chart_data(viewmodels.get("sessions", []))
            self._draw_chart(
                "sessions",
                plot_horizontal_bar_chart,
                title="热门会话",
                labels=labels,
                values=scale_tokens_to_millions(values),
                xlabel="token（M）",
            )
        except ChartRefreshError:
            raise
        except Exception as exc:
            raise ChartRefreshError(f"sessions: {exc}") from exc

    def _fill_tree(self, tree, rows):
        for item in tree.get_children():
            tree.delete(item)
        columns = tree["columns"]
        for row in rows:
            tree.insert("", "end", values=[row.get(column, "") for column in columns])

    def export_current_csvs(self):
        db_path = Path(self.db_path_var.get()).expanduser()
        if not db_path.exists():
            self.status_var.set("未找到数据库；无法导出。")
            return
        try:
            datasets = load_usage_from_db(db_path)
            datasets = price_loaded_usage(datasets, entry_path=self.entry_path)
            out_dir = export_usage_csvs(db_path.resolve().parent / "token_export", datasets)
            self.export_dir_var.set(str(out_dir))
            self.status_var.set(f"已导出到 {out_dir}")
        except Exception as exc:  # pragma: no cover
            self.status_var.set(f"导出失败：{exc}")
            messagebox.showerror("导出失败", f"导出失败：{exc}")
