try:
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
except ImportError:  # pragma: no cover
    Figure = None
    FigureCanvasTkAgg = None


def create_figure(width=5, height=3):
    if Figure is None:
        return None
    return Figure(figsize=(width, height), dpi=100)


def attach_canvas(figure, master):
    if figure is None or FigureCanvasTkAgg is None:
        return None
    canvas = FigureCanvasTkAgg(figure, master=master)
    canvas.draw()
    return canvas


def clear_figure(figure):
    if figure is None:
        return None
    try:
        figure.clear()
        return figure.add_subplot(111)
    except (AttributeError, TypeError, ValueError):  # pragma: no cover
        return None


def _validate_xy_series(labels, values):
    if len(labels) != len(values):
        raise ValueError("labels and values must be the same length")


def _validate_pie_series(labels, values):
    if len(labels) != len(values):
        raise ValueError("labels and values must be the same length")


def show_empty_state(axis, title, message="No data"):
    axis.set_title(title)
    axis.text(0.5, 0.5, message, ha="center", va="center", transform=axis.transAxes)
    axis.set_xticks([])
    axis.set_yticks([])


def plot_line_chart(figure, title, labels, values, ylabel=""):
    axis = clear_figure(figure)
    if axis is None:
        return
    _validate_xy_series(labels, values)
    if not labels or not values:
        show_empty_state(axis, title)
        figure.tight_layout()
        return
    axis.plot(labels, values, marker="o")
    axis.set_title(title)
    if ylabel:
        axis.set_ylabel(ylabel)
    figure.tight_layout()


def plot_horizontal_bar_chart(figure, title, labels, values, xlabel=""):
    axis = clear_figure(figure)
    if axis is None:
        return
    _validate_xy_series(labels, values)
    if not labels or not values:
        show_empty_state(axis, title)
        figure.tight_layout()
        return
    axis.barh(labels, values)
    axis.set_title(title)
    if xlabel:
        axis.set_xlabel(xlabel)
    figure.tight_layout()


def plot_pie_chart(figure, title, labels, values):
    axis = clear_figure(figure)
    if axis is None:
        return
    _validate_pie_series(labels, values)
    filtered = [(label, value) for label, value in zip(labels, values) if value]
    if not filtered:
        show_empty_state(axis, title)
        figure.tight_layout()
        return
    filtered_labels, filtered_values = zip(*filtered)
    axis.pie(filtered_values, labels=filtered_labels, autopct="%1.0f%%")
    axis.set_title(title)
    figure.tight_layout()
