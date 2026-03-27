from datetime import datetime, timedelta
import os
from pathlib import Path
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import TypeAlias

from opencode_token_app.charts import (
    attach_canvas,
    create_figure,
    plot_stacked_bar_chart,
    plot_stacked_horizontal_bar_chart,
    plot_pie_chart,
)
from opencode_token_app.data_loader import load_usage_from_db
from opencode_token_app.exporter import export_usage_csvs
from opencode_token_app.pricing import price_loaded_usage
from opencode_token_app.viewmodels import build_application_viewmodels


LABEL_TEXT = {
    "db_path": "数据库路径",
    "browse": "浏览",
    "load_data": "加载数据",
    "export_dir": "导出目录",
    "filter_day": "日期",
    "filter_provider": "提供方",
    "filter_model": "模型",
    "previous_page": "上一页",
    "next_page": "下一页",
    "chart": "图表",
    "daily": "每日",
    "peak_days": "最高 token 七天",
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
    "cache_read": "缓存输入 token",
    "cache_write": "缓存输出 token",
    "reasoning_tokens": "推理 token",
    "total_tokens_display": "总 token",
    "input_tokens_display": "输入 token",
    "output_tokens_display": "输出 token",
    "cache_read_display": "缓存输入 token",
    "cache_write_display": "缓存输出 token",
    "estimated_cost_total": "预估价格",
    "estimated_cost_total_display": "预估价格",
    "recorded_cost_total": "已记录价格（美元）",
    "recorded_cost_total_display": "已记录价格（美元）",
    "estimated_cost_display": "预估价格",
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


TOKEN_BREAKDOWN_FIELDS = (
    "input_tokens",
    "output_tokens",
    "cache_read",
    "cache_write",
)

PaddingValue: TypeAlias = float | str | tuple[float | str, float | str]


def build_token_breakdown_series(rows, labels, *, reverse=False):
    working_rows = list(rows)
    if reverse:
        working_rows.reverse()
    return {
        field: scale_tokens_to_millions([row.get(field, 0) or 0 for row in working_rows])
        for field in TOKEN_BREAKDOWN_FIELDS
    }


def _parsed_day(day):
    if isinstance(day, str):
        try:
            return datetime.strptime(day, "%Y-%m-%d")
        except ValueError:
            return None
    return None


def _ascending_day_sort_key(day):
    parsed = _parsed_day(day)
    if parsed is not None:
        return (0, parsed)
    return (1, day or "")


def _descending_day_sort_key(day):
    parsed = _parsed_day(day)
    if parsed is not None:
        return (1, parsed)
    return (0, day or "")


def build_top_model_chart_data(rows):
    sorted_rows = sorted(rows, key=lambda row: row.get("total_tokens", 0) or 0, reverse=True)[:10]
    labels = []
    for row in sorted_rows:
        provider = row.get("provider", "") or ""
        model = row.get("model", "") or ""
        labels.append(f"{provider}/{model}" if provider and model else provider or model)
    return labels, build_token_breakdown_series(sorted_rows, labels)


def build_day_chart_data(rows):
    sorted_rows = sorted(rows, key=lambda row: _ascending_day_sort_key(row.get("day", "") or ""))
    labels = [format_day_label(row.get("day", "") or "") for row in sorted_rows]
    return labels, build_token_breakdown_series(sorted_rows, labels)


def format_day_label(day):
    if isinstance(day, str):
        try:
            return datetime.strptime(day, "%Y-%m-%d").strftime("%m/%d")
        except ValueError:
            pass
    return day


def build_recent_day_chart_data(rows):
    valid_rows = []
    malformed_rows = []
    for row in rows:
        day = row.get("day", "") or ""
        if _parsed_day(day) is not None:
            valid_rows.append(row)
        else:
            malformed_rows.append(row)

    if valid_rows:
        rows_by_day = {row.get("day", "") or "": row for row in valid_rows}
        parsed_days = [parsed for day in rows_by_day if (parsed := _parsed_day(day)) is not None]
        latest_day = max(parsed_days)
        recent_rows = []
        for offset in range(6, -1, -1):
            current_day = latest_day - timedelta(days=offset)
            day_key = current_day.strftime("%Y-%m-%d")
            source_row = rows_by_day.get(day_key)
            if source_row is None:
                recent_rows.append({"day": day_key, "total_tokens": 0})
            else:
                recent_rows.append({"day": day_key, **source_row})
    else:
        recent_rows = []

    if not valid_rows and len(recent_rows) < 7:
        remaining = 7 - len(recent_rows)
        recent_rows.extend(
            sorted(malformed_rows, key=lambda row: row.get("day", "") or "")[:remaining]
        )

    labels = [format_day_label(row.get("day", "") or "") for row in recent_rows]
    return labels, build_token_breakdown_series(recent_rows, labels)


def build_peak_day_chart_data(rows):
    sorted_rows = sorted(
        rows,
        key=lambda row: (
            row.get("total_tokens", 0) or 0,
            _descending_day_sort_key(row.get("day", "") or ""),
        ),
        reverse=True,
    )[:7]
    labels = [format_day_label(row.get("day", "") or "") for row in sorted_rows]
    return labels, build_token_breakdown_series(sorted_rows, labels)


def build_top_session_chart_data(rows):
    sorted_rows = sorted(rows, key=lambda row: row.get("total_tokens", 0) or 0, reverse=True)[:10]
    labels = [
        (row.get("session_title", "") or row.get("session_id", "") or "")
        for row in sorted_rows
    ]
    return labels, build_token_breakdown_series(sorted_rows, labels)


def build_overview_composition_chart_data(cards):
    return ["输入 token", "输出 token", "缓存输入 token", "缓存输出 token"], [
        cards.get("input_tokens", 0) or 0,
        cards.get("output_tokens", 0) or 0,
        cards.get("cache_read", 0) or 0,
        cards.get("cache_write", 0) or 0,
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
        self.raw_message_page_size = 200
        self.raw_message_page_index = 0
        self.raw_message_total_rows = 0
        self.raw_message_page_count = 0
        self._initial_load_after_id = None
        self._initial_load_pending = False
        self._initial_load_thread = None
        self._initial_load_result = None
        self.pack(fill="both", expand=True)
        self._build_header()
        self._build_notebook()
        self._schedule_initial_load()

    def _schedule_initial_load(self):
        if getattr(self, "_initial_load_pending", False):
            return
        self._initial_load_pending = True

        def run_initial_load():
            if not self._initial_load_pending:
                return
            self._initial_load_after_id = None
            self._initial_load_pending = False
            self._start_initial_load_thread()

        self._initial_load_after_id = self.master.after(10, run_initial_load)

    def _start_initial_load_thread(self):
        if self._initial_load_thread is not None and self._initial_load_thread.is_alive():
            return
        request = self._current_load_request()
        self._initial_load_result = None

        def run_background_load():
            self._initial_load_result = self._load_data_for_display(request)

        thread = threading.Thread(
            target=run_background_load,
            name="opencode-initial-load",
            daemon=True,
        )
        self._initial_load_thread = thread
        thread.start()
        self._poll_initial_load_thread(thread)

    def _poll_initial_load_thread(self, thread):
        if self._initial_load_thread is not thread:
            return
        if thread.is_alive():
            self.master.after(10, lambda: self._poll_initial_load_thread(thread))
            return
        result = self._initial_load_result
        self._initial_load_thread = None
        self._initial_load_result = None
        if result is not None:
            self._apply_load_data_result(result)

    def _clear_initial_load_schedule(self):
        if not getattr(self, "_initial_load_pending", False):
            return
        after_id = getattr(self, "_initial_load_after_id", None)
        self._initial_load_after_id = None
        self._initial_load_pending = False
        if after_id is not None and hasattr(self.master, "after_cancel"):
            self.master.after_cancel(after_id)

    def _build_header(self):
        header = ttk.Frame(self)
        header.pack(fill="x", padx=8, pady=8)
        ttk.Label(header, text=ui_text("db_path")).grid(row=0, column=0, sticky="w")
        ttk.Entry(header, textvariable=self.db_path_var, width=80).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Button(header, text=ui_text("browse"), command=self.browse_db).grid(row=0, column=2, padx=4)
        ttk.Button(header, text=ui_text("load_data"), command=self.load_and_export_data).grid(row=0, column=3, padx=4)
        ttk.Label(header, text=ui_text("export_dir")).grid(row=1, column=0, sticky="w")
        ttk.Label(header, textvariable=self.export_dir_var).grid(row=1, column=1, columnspan=3, sticky="w", padx=6)
        ttk.Label(header, textvariable=self.status_var).grid(row=2, column=0, columnspan=4, sticky="w")
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
        self.overview_cards.pack(fill="x", padx=8, pady=(8, 4))
        self.overview_card_labels = {}
        for idx, key in enumerate(["total_tokens", "input_tokens", "output_tokens", "cache_read", "cache_write", "reasoning_tokens", "estimated_cost_total", "recorded_cost_total"]):
            label = ttk.Label(self.overview_cards, text=f"{ui_text(key)}: -")
            row, column = divmod(idx, 4)
            label.grid(row=row, column=column, padx=4, sticky="w")
            self.overview_card_labels[key] = label

        self.overview_table = self._create_treeview(
            frame,
            ["day", "total_tokens_display", "estimated_cost_display"],
            height=5,
            expand=False,
            pady=(0, 4),
        )

        self.overview_chart_area = ttk.Frame(frame)
        self.overview_chart_area.pack(fill="both", expand=True, padx=8, pady=(4, 8))
        overview_chart_specs = [
            ("overview_daily", "daily"),
            ("overview_peak_days", "peak_days"),
            ("overview_models", "models"),
            ("overview_composition", "composition"),
        ]
        for column in range(2):
            self.overview_chart_area.columnconfigure(column, weight=1)
        for row in range(2):
            self.overview_chart_area.rowconfigure(row, weight=1)
        for index, (chart_name, label_key) in enumerate(overview_chart_specs):
            row, column = divmod(index, 2)
            chart_frame = ttk.LabelFrame(self.overview_chart_area, text=ui_text(label_key))
            chart_frame.grid(row=row, column=column, sticky="nsew", padx=4, pady=4)
            figure = create_figure()
            canvas = attach_canvas(figure, chart_frame)
            self._register_chart(chart_name, figure, canvas)
            if canvas is not None:
                canvas.get_tk_widget().pack(fill="both", expand=True)

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
            columns = ["provider", "model", "message_count", "total_tokens_display", "input_tokens_display", "output_tokens_display", "cache_read_display", "cache_write_display", "estimated_cost_display", "recorded_cost_display", "price_status_label"]
        elif key == "days":
            columns = ["day", "message_count", "total_tokens_display", "input_tokens_display", "output_tokens_display", "cache_read_display", "cache_write_display", "estimated_cost_display", "recorded_cost_display"]
        else:
            columns = ["session_id", "session_title", "message_count", "total_tokens_display", "input_tokens_display", "output_tokens_display", "cache_read_display", "cache_write_display", "estimated_cost_display", "recorded_cost_display"]
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
        controls = ttk.Frame(frame)
        controls.pack(fill="x", padx=8, pady=(0, 4))
        self.raw_page_label_var = tk.StringVar(value="暂无数据")
        self.raw_range_label_var = tk.StringVar(value="当前没有可显示的明细")
        self.raw_message_prev_button = ttk.Button(
            controls,
            text=ui_text("previous_page"),
            command=self.show_previous_raw_message_page,
            state="disabled",
        )
        self.raw_message_prev_button.pack(side="left")
        self.raw_message_next_button = ttk.Button(
            controls,
            text=ui_text("next_page"),
            command=self.show_next_raw_message_page,
            state="disabled",
        )
        self.raw_message_next_button.pack(side="left", padx=(4, 8))
        ttk.Label(controls, textvariable=self.raw_page_label_var).pack(side="left")
        ttk.Label(controls, textvariable=self.raw_range_label_var).pack(side="left", padx=(8, 0))
        columns = ["provider", "model", "role", "time_created_text", "total_tokens_display", "input_tokens_display", "output_tokens_display", "cache_read_display", "cache_write_display", "estimated_cost_display", "recorded_cost_display", "price_status_label"]
        self.treeviews["raw_messages"] = self._create_treeview(frame, columns)

    def _create_treeview(self, parent, columns, *, height=8, expand=True, padx: PaddingValue = 8, pady: PaddingValue = 8):
        tree = ttk.Treeview(parent, columns=columns, show="headings", height=height)
        for column in columns:
            tree.heading(column, text=ui_text(column))
            tree.column(column, width=120, stretch=True)
        tree.pack(fill="both", expand=expand, padx=padx, pady=pady)
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
        self.load_and_export_data()

    def load_data(self):
        self._load_data(should_export=False)

    def load_and_export_data(self):
        self._load_data(should_export=True)

    def _load_data(self, should_export):
        self._clear_initial_load_schedule()
        self._initial_load_thread = None
        self._initial_load_result = None
        result = self._load_data_for_display(self._current_load_request())
        self._apply_load_data_result(result, should_export=should_export)

    def _current_load_request(self):
        db_path = Path(self.db_path_var.get()).expanduser()
        return {
            "db_path": db_path,
            "export_dir": db_path.resolve().parent / "token_export",
        }

    def _load_data_for_display(self, request):
        db_path = request["db_path"]
        export_dir = request["export_dir"]
        if not db_path.exists():
            return {"export_dir": export_dir, "missing": True}

        try:
            datasets = load_usage_from_db(db_path)
            datasets = price_loaded_usage(datasets, entry_path=self.entry_path)
            viewmodels = build_application_viewmodels(datasets)
        except Exception as exc:  # pragma: no cover
            return {"export_dir": export_dir, "error": exc}

        return {
            "export_dir": export_dir,
            "datasets": datasets,
            "viewmodels": viewmodels,
        }

    def _apply_load_data_result(self, result, should_export=False):
        export_dir = result["export_dir"]
        self.export_dir_var.set(str(export_dir))
        if result.get("missing"):
            self.status_var.set("未找到数据库；请手动选择文件。")
            return
        if result.get("error") is not None:
            exc = result["error"]
            self.status_var.set(f"加载失败：{exc}")
            messagebox.showerror("加载失败", f"加载失败：{exc}")
            return

        datasets = result["datasets"]
        viewmodels = result["viewmodels"]

        self.viewmodels = viewmodels
        self._reset_raw_message_pagination()
        warnings = self._populate_view()

        if should_export:
            try:
                out_dir = export_usage_csvs(export_dir, datasets)
                self.export_dir_var.set(str(out_dir))
            except Exception as exc:  # pragma: no cover
                self.status_var.set(f"导出失败：{exc}")
                messagebox.showerror("导出失败", f"导出失败：{exc}")
                return
            if not warnings:
                self.status_var.set(f"已加载并导出到 {out_dir}")
            return

        if not warnings:
            self.status_var.set("已加载数据")

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
        self._render_current_raw_message_page()
        return self._refresh_charts()

    def _raw_message_pagination_info(self, reset_index=False):
        rows = []
        if self.viewmodels is not None:
            rows = self.viewmodels.get("raw_messages", [])

        page_size = getattr(self, "raw_message_page_size", 200)
        try:
            page_size = int(page_size)
        except (TypeError, ValueError):
            page_size = 200
        if page_size <= 0:
            page_size = 200

        total_rows = len(rows)
        page_count = (total_rows + page_size - 1) // page_size if total_rows else 0

        if reset_index:
            page_index = 0
        else:
            page_index = getattr(self, "raw_message_page_index", 0)
            try:
                page_index = int(page_index)
            except (TypeError, ValueError):
                page_index = 0

        if page_count == 0:
            page_index = 0
        else:
            page_index = min(max(page_index, 0), page_count - 1)

        self.raw_message_page_size = page_size
        self.raw_message_page_index = page_index
        self.raw_message_total_rows = total_rows
        self.raw_message_page_count = page_count
        return {
            "rows": rows,
            "page_index": page_index,
            "page_size": page_size,
            "total_rows": total_rows,
            "page_count": page_count,
        }

    def _reset_raw_message_pagination(self):
        self._raw_message_pagination_info(reset_index=True)

    def _current_raw_message_rows(self):
        pagination = self._raw_message_pagination_info()
        start = pagination["page_index"] * pagination["page_size"]
        end = start + pagination["page_size"]
        return pagination["rows"][start:end]

    def _render_current_raw_message_page(self):
        self._fill_tree(self.treeviews["raw_messages"], self._current_raw_message_rows())
        self._refresh_raw_message_pagination()

    def _render_raw_message_page(self):
        self._render_current_raw_message_page()

    def _change_raw_message_page(self, delta):
        self._raw_message_pagination_info()
        target_index = self.raw_message_page_index
        try:
            target_index += int(delta)
        except (TypeError, ValueError):
            pass
        if self.raw_message_page_count == 0:
            target_index = 0
        else:
            target_index = min(max(target_index, 0), self.raw_message_page_count - 1)
        self.raw_message_page_index = target_index
        self._render_current_raw_message_page()

    def _refresh_raw_message_pagination(self):
        self._raw_message_pagination_info()
        page_label_var = getattr(self, "raw_page_label_var", None)
        range_label_var = getattr(self, "raw_range_label_var", None)
        prev_button = getattr(self, "raw_message_prev_button", None)
        next_button = getattr(self, "raw_message_next_button", None)
        if page_label_var is None and range_label_var is None and prev_button is None and next_button is None:
            return
        if self.raw_message_page_count:
            start = self.raw_message_page_index * self.raw_message_page_size + 1
            end = min(start + self.raw_message_page_size - 1, self.raw_message_total_rows)
            page_text = f"第 {self.raw_message_page_index + 1} / {self.raw_message_page_count} 页"
            range_text = f"显示第 {start} - {end} 条，共 {self.raw_message_total_rows} 条"
        else:
            page_text = "暂无数据"
            range_text = "当前没有可显示的明细"
        if page_label_var is not None:
            page_label_var.set(page_text)
        if range_label_var is not None:
            range_label_var.set(range_text)
        if prev_button is not None:
            prev_button.configure(state="normal" if self.raw_message_page_index > 0 else "disabled")
        if next_button is not None:
            has_next_page = self.raw_message_page_index + 1 < self.raw_message_page_count
            next_button.configure(state="normal" if has_next_page else "disabled")

    def show_previous_raw_message_page(self):
        self._change_raw_message_page(-1)

    def show_next_raw_message_page(self):
        self._change_raw_message_page(1)

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
        if prefix in {"overview_daily", "overview_peak_days", "overview_models", "overview_composition", "models", "days", "sessions"} and remainder:
            return remainder
        return warning

    def _refresh_charts(self):
        warnings = []
        for refresh in (
            self._refresh_overview_daily_chart,
            self._refresh_overview_peak_days_chart,
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
            day_labels, day_series = build_recent_day_chart_data(overview.get("daily_rows", []))
            self._draw_chart(
                "overview_daily",
                plot_stacked_bar_chart,
                title="每日 token",
                labels=day_labels,
                series=day_series,
                ylabel="token（M）",
            )
        except ChartRefreshError:
            raise
        except Exception as exc:
            raise ChartRefreshError(f"overview_daily: {exc}") from exc

    def _refresh_overview_peak_days_chart(self):
        try:
            viewmodels = self.viewmodels
            if viewmodels is None:
                return
            overview = viewmodels["overview"]
            model_labels, model_series = build_peak_day_chart_data(overview.get("daily_rows", []))
            self._draw_chart(
                "overview_peak_days",
                plot_stacked_horizontal_bar_chart,
                title="最高 token 七天",
                labels=model_labels,
                series=model_series,
                xlabel="token（M）",
            )
        except ChartRefreshError:
            raise
        except Exception as exc:
            raise ChartRefreshError(f"overview_peak_days: {exc}") from exc

    def _refresh_overview_models_chart(self):
        try:
            viewmodels = self.viewmodels
            if viewmodels is None:
                return
            labels, series = build_top_model_chart_data(viewmodels.get("models", []))
            self._draw_chart(
                "overview_models",
                plot_stacked_horizontal_bar_chart,
                title="热门模型",
                labels=labels,
                series=series,
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
            labels, series = build_top_model_chart_data(viewmodels.get("models", []))
            self._draw_chart(
                "models",
                plot_stacked_horizontal_bar_chart,
                title="热门模型",
                labels=labels,
                series=series,
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
            labels, series = build_day_chart_data(viewmodels.get("days", []))
            self._draw_chart(
                "days",
                plot_stacked_bar_chart,
                title="每日 token",
                labels=labels,
                series=series,
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
            labels, series = build_top_session_chart_data(viewmodels.get("sessions", []))
            self._draw_chart(
                "sessions",
                plot_stacked_horizontal_bar_chart,
                title="热门会话",
                labels=labels,
                series=series,
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
        self.load_and_export_data()
