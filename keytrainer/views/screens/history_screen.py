"""History screen: summary, chart and table of sessions (Figma: рисунок 9)."""

import subprocess
import sys
import tkinter as tk
from collections.abc import Callable, Sequence
from datetime import datetime
from tkinter import ttk

try:  # the chart needs matplotlib; without it the program still works
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.dates import DateFormatter, date2num
    from matplotlib.figure import Figure

    HAS_MATPLOTLIB = True
except ImportError:  # pragma: no cover - depends on the installation
    HAS_MATPLOTLIB = False


from keytrainer.data.models import Session
from keytrainer.engine.history_service import ChartData, HistorySummary
from keytrainer.labels import MODE_TITLES, format_duration, format_number
from keytrainer.utils.background import run_in_background
from keytrainer.views.animation import Animator, ease_in_out, mix_colors
from keytrainer.views.display import FONTS_DIR, px, scale
from keytrainer.views.theme import Palette, ThemeManager
from keytrainer.views.widgets.message import show_animated_message
from keytrainer.views.widgets.slim_scrollbar import SlimScrollbar
from keytrainer.views.widgets.text_button import TextButton


def _load_matplotlib() -> bool:
    """Import matplotlib after it was installed while the program runs.

    Returns:
        ``True`` if the import succeeded.
    """
    global HAS_MATPLOTLIB, FigureCanvasTkAgg, DateFormatter, date2num, Figure
    try:
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        from matplotlib.dates import DateFormatter, date2num
        from matplotlib.figure import Figure
    except ImportError:
        return False
    HAS_MATPLOTLIB = True
    return True


def install_matplotlib() -> None:
    """Install matplotlib with pip into the Python that runs the program.

    Raises:
        RuntimeError: pip finished with an error.
    """
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "matplotlib"],
        capture_output=True,
        text=True,
        creationflags=flags,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip().splitlines()[-1:] or "pip error")


def use_bundled_font() -> None:
    """Draw chart labels with JetBrains Mono, like the rest of the window."""
    from matplotlib import font_manager, rcParams

    for path in FONTS_DIR.glob("*.ttf"):
        font_manager.fontManager.addfont(str(path))
    rcParams["font.family"] = ["JetBrains Mono", "DejaVu Sans Mono", "monospace"]


COLUMNS = {
    "started_at": ("дата и время", 190),
    "exercise_mode": ("режим", 230),
    "wpm": ("wpm", 110),
    "error_rate": ("% ошибок", 130),
    "duration_sec": ("длительность", 130),
}
INSERT_CHUNK = 400
TABLE_ROWS = 9
CHART_MS = 650
CHART_FRAME_MS = 33


class HistoryScreen(tk.Frame):
    """Passive view of the history tab."""

    def __init__(self, parent: tk.Misc, theme: ThemeManager) -> None:
        """Build the widgets.

        Args:
            parent: Content area of the main window.
            theme: Theme manager.
        """
        super().__init__(parent, bd=0)
        self.theme = theme
        theme.style(self, bg="bg")
        self.callbacks: dict[str, Callable] = {}
        self._chart_data: ChartData | None = None
        self._insert_job: str | None = None
        self._progress = 1.0
        self.animator = Animator(self)
        body = theme.frame(self)
        body.place(relx=0.5, rely=0.47, anchor="center")
        self._build_summary(body)
        self._build_chart(body)
        self._build_table(body)
        buttons = theme.frame(body)
        buttons.pack(pady=px((24, 0)))
        TextButton(
            buttons,
            theme,
            "удалить выбранную",
            lambda: self._emit("delete"),
            role="error",
            hover_role="error",
        ).pack(side="left", padx=px(70))
        TextButton(
            buttons, theme, "экспорт в csv", lambda: self._emit("export"), role="text"
        ).pack(side="left", padx=px(70))
        self.message = theme.label(body, "", role="muted", font="small")
        self.message.pack(pady=px((12, 0)))
        theme.on_change(self._on_theme)
        self._on_theme(theme.palette)

    def _emit(self, name: str, *args) -> None:
        """Call a controller callback.

        Args:
            name: Callback name.
            *args: Arguments.
        """
        callback = self.callbacks.get(name)
        if callback:
            callback(*args)

    # ------------------------------------------------------------ build
    def _build_summary(self, parent: tk.Misc) -> None:
        """Create "всего сессий / рекорд / среднее за 10".

        Args:
            parent: Container.
        """
        row = self.theme.frame(parent)
        row.pack(pady=px((0, 14)))
        self.summary_values = {}
        for key, caption in (
            ("total", "всего сессий"),
            ("best", "рекорд"),
            ("avg", "среднее за 10"),
        ):
            self.theme.label(row, caption, role="muted").pack(
                side="left", padx=px((30, 14))
            )
            value = self.theme.label(row, "—")
            value.pack(side="left")
            self.summary_values[key] = value

    def _build_chart(self, parent: tk.Misc) -> None:
        """Create the matplotlib chart embedded with FigureCanvasTkAgg.

        Without matplotlib a placeholder offers to install it in one click.

        Args:
            parent: Container.
        """
        self.chart_holder = self.theme.frame(parent)
        self.chart_holder.pack()
        self.figure = None
        if HAS_MATPLOTLIB:
            self._create_figure()
        else:
            self._build_chart_placeholder()

    def _create_figure(self) -> None:
        """Create the figure inside the chart holder (in the interface font)."""
        use_bundled_font()
        # the screen scale is applied here once; matplotlib's own correction
        # on <Map> is switched off, otherwise the chart is scaled twice
        self.figure = Figure(figsize=(8.6, 2.3), dpi=round(100 * scale()))
        self.axis_wpm = self.figure.add_subplot(111)
        self.axis_errors = self.axis_wpm.twinx()
        self.canvas = FigureCanvasTkAgg(self.figure, master=self.chart_holder)
        widget = self.canvas.get_tk_widget()
        widget.unbind("<Map>")
        widget.configure(highlightthickness=0, bd=0)
        widget.pack()

    def _build_chart_placeholder(self) -> None:
        """Explain that the chart needs matplotlib and offer to install it."""
        box = self.theme.frame(self.chart_holder)
        box.pack(pady=px(40))
        self.chart_note = self.theme.label(
            box, "для графика нужна библиотека matplotlib", role="muted"
        )
        self.chart_note.pack()
        if not getattr(sys, "frozen", False):
            self.install_button = TextButton(
                box, self.theme, "установить", self._install, role="text"
            )
            self.install_button.pack(pady=px((10, 0)))

    def _install(self) -> None:
        """Install matplotlib in the background and show the chart."""
        self.install_button.set_state(enabled=False)
        self.chart_note.configure(text="установка matplotlib… (около минуты)")

        def done(_result: object) -> None:
            if not _load_matplotlib():
                failed(RuntimeError("не удалось загрузить"))
                return
            for child in self.chart_holder.winfo_children():
                child.destroy()
            self._create_figure()
            self._on_theme(self.theme.palette)
            if self._chart_data is not None:
                self.show_chart(self._chart_data)

        def failed(error: Exception) -> None:
            self.chart_note.configure(
                text=f"не получилось: {error}\nкоманда: py -m pip install matplotlib"
            )
            self.install_button.set_state(enabled=True)

        run_in_background(self, install_matplotlib, done, failed)

    def _build_table(self, parent: tk.Misc) -> None:
        """Create the table of sessions with sortable headings.

        Args:
            parent: Container.
        """
        holder = self.theme.frame(parent)
        holder.pack(pady=px((18, 0)), fill="x")
        self.table = ttk.Treeview(
            holder,
            columns=list(COLUMNS),
            show="headings",
            height=TABLE_ROWS,
            selectmode="extended",
            style="History.Treeview",
            takefocus=False,
        )
        for column, (title, width) in COLUMNS.items():
            self.table.heading(
                column,
                text=title,
                anchor="w",
                command=lambda c=column: self._emit("sort", c),
            )
            self.table.column(column, width=px(width), anchor="w", stretch=False)
        scroll = SlimScrollbar(holder, self.theme, self.table.yview)
        self.table.configure(yscrollcommand=scroll.set)
        self.table.pack(side="left")
        scroll.pack(side="left", fill="y", padx=px((6, 0)))
        self._hover_row = ""
        self.table.bind("<Motion>", self._on_row_motion)
        self.table.bind("<Leave>", lambda _e: self._set_hover(""))

    def _on_row_motion(self, event: tk.Event) -> None:
        """Highlight the row under the mouse.

        Args:
            event: Tk motion event.
        """
        self._set_hover(self.table.identify_row(event.y))

    def _set_hover(self, row: str) -> None:
        """Move the hover highlight to another row.

        Args:
            row: Row id, empty string for none.
        """
        if row == self._hover_row:
            return
        for iid, tags in ((self._hover_row, ()), (row, ("hover",))):
            if iid and self.table.exists(iid):
                old = tuple(t for t in self.table.item(iid, "tags") if t != "hover")
                self.table.item(iid, tags=old + tags)
        self._hover_row = row

    # ------------------------------------------------------------ theme
    def _on_theme(self, palette: Palette) -> None:
        """Color the table and redraw the chart for the new theme.

        Args:
            palette: New palette.
        """
        style = ttk.Style(self)
        if style.theme_use() != "clam":
            style.theme_use("clam")
        # only the rows area: no field border, no focus frame
        style.layout("History.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
        style.layout(
            "History.Treeview.Heading",
            [
                (
                    "Treeheading.cell",
                    {
                        "sticky": "nswe",
                        "children": [
                            (
                                "Treeheading.padding",
                                {
                                    "sticky": "nswe",
                                    "children": [
                                        ("Treeheading.text", {"sticky": "we"})
                                    ],
                                },
                            )
                        ],
                    },
                )
            ],
        )
        flat = {
            "bordercolor": palette.bg,
            "lightcolor": palette.bg,
            "darkcolor": palette.bg,
            "borderwidth": 0,
            "relief": "flat",
        }
        style.configure(
            "History.Treeview",
            background=palette.bg,
            fieldbackground=palette.bg,
            foreground=palette.muted,
            rowheight=px(36),
            font=self.theme.fonts["ui"],
            **flat,
        )
        style.map(
            "History.Treeview",
            background=[("selected", palette.surface_active)],
            foreground=[("selected", palette.text)],
        )
        style.configure(
            "History.Treeview.Heading",
            background=palette.bg,
            foreground=palette.dim,
            font=self.theme.fonts["small"],
            padding=(px(4), px(8)),
            **flat,
        )
        style.map(
            "History.Treeview.Heading",
            background=[("active", palette.bg)],
            foreground=[("active", palette.text)],
        )
        self.table.tag_configure(
            "hover", background=palette.surface, foreground=palette.text
        )
        if self.figure is None:
            return
        self.figure.set_facecolor(palette.bg)
        self.canvas.get_tk_widget().configure(bg=palette.bg)
        self._draw_chart()

    # ----------------------------------------------------------- update
    def show_summary(self, summary: HistorySummary) -> None:
        """Fill the numbers above the chart.

        Args:
            summary: History summary.
        """
        self.summary_values["total"].configure(text=str(summary.total_sessions))
        for key, value in (("best", summary.best_wpm), ("avg", summary.avg_wpm_last)):
            text = "—" if value is None else f"{value:.0f} wpm"
            self.summary_values[key].configure(text=text)

    def show_chart(self, data: ChartData) -> None:
        """Draw the WPM line and the dashed error rate line.

        Args:
            data: Smoothed series.
        """
        self._chart_data = data

        def step(t: float) -> None:
            self._progress = t
            self._draw_chart()

        self.animator.run(
            "chart", CHART_MS, step, easing=ease_in_out, frame_ms=CHART_FRAME_MS
        )

    def _draw_chart(self) -> None:
        """Draw the chart with the colors of the current theme."""
        if self.figure is None:
            return
        palette = self.theme.palette
        wpm_axis, err_axis = self.axis_wpm, self.axis_errors
        for axis in (wpm_axis, err_axis):
            axis.clear()
            axis.set_facecolor(palette.bg)
            axis.tick_params(colors=palette.dim, labelsize=7, length=0)
            for spine in axis.spines.values():
                spine.set_visible(False)
        wpm_axis.grid(axis="y", color=palette.border, linewidth=0.6)
        data = self._chart_data
        if data and data.dates:
            dates, wpm, errors = grow_series(data, self._progress)
            wpm_axis.plot(
                dates,
                wpm,
                color=palette.text,
                linewidth=1.4,
                marker="o",
                markersize=3,
                label="wpm",
            )
            err_axis.plot(
                dates,
                errors,
                color=palette.muted,
                linewidth=1.1,
                linestyle="--",
                marker="o",
                markersize=2,
                label="% ошибок",
            )
            wpm_axis.set_ylim(0, max(data.wpm) * 1.15 or 1)
            err_axis.set_ylim(0, max(data.error_rate) * 1.15 or 1)
            if len(data.dates) > 1:
                wpm_axis.set_xlim(data.dates[0], data.dates[-1])
            wpm_axis.xaxis.set_major_formatter(DateFormatter("%d.%m"))
            wpm_axis.text(
                1.06,
                1.0,
                "wpm\n% ошибок (пунктир)",
                color=palette.muted,
                fontsize=7,
                transform=wpm_axis.transAxes,
                va="top",
            )
        else:
            wpm_axis.text(
                0.5,
                0.5,
                "нет завершенных сессий",
                color=palette.dim,
                ha="center",
                va="center",
                transform=wpm_axis.transAxes,
            )
        self.figure.subplots_adjust(left=0.05, right=0.8, top=0.95, bottom=0.14)
        self.canvas.draw_idle()

    def show_sessions(self, sessions: Sequence[Session]) -> None:
        """Fill the table in chunks so 10 000 rows do not freeze the window.

        Args:
            sessions: Sessions in display order.
        """
        if self._insert_job is not None:
            self.after_cancel(self._insert_job)
        self.table.delete(*self.table.get_children())
        self._insert_chunk(list(sessions), 0)
        palette = self.theme.palette

        def step(t: float) -> None:
            self.table.tag_configure(
                "fresh", foreground=mix_colors(palette.bg, palette.muted, t)
            )

        def done() -> None:
            for iid in self.table.get_children():
                self.table.item(iid, tags=())

        step(0)
        self.animator.run("rows", 420, step, done, delay_ms=120)

    def _insert_chunk(self, sessions: list[Session], start: int) -> None:
        """Insert the next chunk of rows.

        Args:
            sessions: All sessions.
            start: Index of the first row of the chunk.
        """
        for session in sessions[start : start + INSERT_CHUNK]:
            self.table.insert(
                "",
                "end",
                iid=str(session.id),
                values=row_values(session),
                tags=("fresh",) if start == 0 else (),
            )
        start += INSERT_CHUNK
        self._insert_job = (
            self.after(1, self._insert_chunk, sessions, start)
            if start < len(sessions)
            else None
        )

    def show_sort(self, column: str, descending: bool) -> None:
        """Put an arrow on the sorted column.

        Args:
            column: Sorted column.
            descending: Direction.
        """
        for name, (title, _width) in COLUMNS.items():
            arrow = (" ↓" if descending else " ↑") if name == column else ""
            self.table.heading(name, text=title + arrow)

    def selected_ids(self) -> list[int]:
        """Ids of the selected sessions.

        Returns:
            Session ids.
        """
        return [int(iid) for iid in self.table.selection()]

    def show_message(self, text: str, is_error: bool = False) -> None:
        """Show a message under the buttons.

        Args:
            text: Message.
            is_error: Color as an error.
        """
        show_animated_message(self.message, self.theme, text, is_error)


def row_values(session: Session) -> tuple[str, ...]:
    """Format a session for the table.

    Args:
        session: Session.

    Returns:
        Cell texts in the order of :data:`COLUMNS`.
    """
    started = datetime.fromisoformat(session.started_at).strftime("%d.%m.%Y %H:%M")
    mode = MODE_TITLES[session.exercise_mode]
    if not session.is_completed:
        mode += " (прервано)"
    return (
        started,
        mode,
        f"{session.wpm:.0f}",
        f"{format_number(session.error_rate)} %",
        format_duration(session.duration_sec or 0),
    )


def grow_series(data: ChartData, progress: float) -> tuple[list, list, list]:
    """Cut the chart lines at ``progress`` so they grow from left to right.

    The last point is interpolated between two sessions, so the line moves
    smoothly instead of jumping from point to point.

    Args:
        data: Full series.
        progress: Part of the line to show, from 0 to 1.

    Returns:
        X values (matplotlib date numbers), WPM and error rate.
    """
    xs = [date2num(d) for d in data.dates]
    if len(xs) < 2 or progress >= 1:
        return xs, list(data.wpm), list(data.error_rate)
    position = (len(xs) - 1) * max(progress, 0.0)
    whole = int(position)
    part = position - whole

    def cut(values: list[float]) -> list[float]:
        head = list(values[: whole + 1])
        if part > 0:
            head.append(values[whole] + (values[whole + 1] - values[whole]) * part)
        return head

    return cut(xs), cut(list(data.wpm)), cut(list(data.error_rate))
