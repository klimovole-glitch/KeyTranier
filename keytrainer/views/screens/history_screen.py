"""History screen: summary, chart and table of sessions (Figma: рисунок 9)."""

import tkinter as tk
from collections.abc import Callable, Sequence
from datetime import datetime
from tkinter import ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.dates import DateFormatter
from matplotlib.figure import Figure

from keytrainer.data.models import Session
from keytrainer.engine.history_service import ChartData, HistorySummary
from keytrainer.labels import MODE_TITLES, format_duration, format_number
from keytrainer.views.theme import Palette, ThemeManager
from keytrainer.views.widgets.text_button import TextButton

COLUMNS = {
    "started_at": ("дата и время", 190),
    "exercise_mode": ("режим", 230),
    "wpm": ("wpm", 110),
    "error_rate": ("% ошибок", 130),
    "duration_sec": ("длительность", 130),
}
INSERT_CHUNK = 400
TABLE_ROWS = 9


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
        body = theme.frame(self)
        body.place(relx=0.5, rely=0.47, anchor="center")
        self._build_summary(body)
        self._build_chart(body)
        self._build_table(body)
        buttons = theme.frame(body)
        buttons.pack(pady=(24, 0))
        TextButton(
            buttons,
            theme,
            "удалить выбранную",
            lambda: self._emit("delete"),
            role="error",
            hover_role="error",
        ).pack(side="left", padx=70)
        TextButton(
            buttons, theme, "экспорт в csv", lambda: self._emit("export"), role="text"
        ).pack(side="left", padx=70)
        self.message = theme.label(body, "", role="muted", font="small")
        self.message.pack(pady=(12, 0))
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
        row.pack(pady=(0, 14))
        self.summary_values = {}
        for key, caption in (
            ("total", "всего сессий"),
            ("best", "рекорд"),
            ("avg", "среднее за 10"),
        ):
            self.theme.label(row, caption, role="muted").pack(
                side="left", padx=(30, 14)
            )
            value = self.theme.label(row, "—")
            value.pack(side="left")
            self.summary_values[key] = value

    def _build_chart(self, parent: tk.Misc) -> None:
        """Create the matplotlib chart embedded with FigureCanvasTkAgg.

        Args:
            parent: Container.
        """
        self.figure = Figure(figsize=(8.6, 2.3), dpi=100)
        self.axis_wpm = self.figure.add_subplot(111)
        self.axis_errors = self.axis_wpm.twinx()
        self.canvas = FigureCanvasTkAgg(self.figure, master=parent)
        self.canvas.get_tk_widget().configure(highlightthickness=0, bd=0)
        self.canvas.get_tk_widget().pack()

    def _build_table(self, parent: tk.Misc) -> None:
        """Create the table of sessions with sortable headings.

        Args:
            parent: Container.
        """
        holder = self.theme.frame(parent)
        holder.pack(pady=(14, 0))
        self.table = ttk.Treeview(
            holder,
            columns=list(COLUMNS),
            show="headings",
            height=TABLE_ROWS,
            selectmode="extended",
            style="History.Treeview",
        )
        for column, (title, width) in COLUMNS.items():
            self.table.heading(
                column, text=title, command=lambda c=column: self._emit("sort", c)
            )
            self.table.column(column, width=width, anchor="w")
        scroll = ttk.Scrollbar(
            holder,
            orient="vertical",
            command=self.table.yview,
            style="History.Vertical.TScrollbar",
        )
        self.table.configure(yscrollcommand=scroll.set)
        self.table.pack(side="left")
        scroll.pack(side="left", fill="y")

    # ------------------------------------------------------------ theme
    def _on_theme(self, palette: Palette) -> None:
        """Color the table and redraw the chart for the new theme.

        Args:
            palette: New palette.
        """
        style = ttk.Style(self)
        if style.theme_use() != "clam":
            style.theme_use("clam")
        flat = {
            "bordercolor": palette.bg,
            "lightcolor": palette.bg,
            "darkcolor": palette.bg,
            "borderwidth": 0,
        }
        style.configure(
            "History.Treeview",
            background=palette.bg,
            fieldbackground=palette.bg,
            foreground=palette.muted,
            rowheight=30,
            font=self.theme.fonts["small"],
            **flat,
        )
        style.map(
            "History.Treeview",
            background=[("selected", palette.selection)],
            foreground=[("selected", palette.text)],
        )
        style.configure(
            "History.Treeview.Heading",
            background=palette.bg,
            foreground=palette.dim,
            relief="flat",
            font=self.theme.fonts["tiny"],
            **flat,
        )
        style.map("History.Treeview.Heading", background=[("active", palette.bg)])
        style.configure(
            "History.Vertical.TScrollbar",
            background=palette.surface,
            troughcolor=palette.bg,
            arrowcolor=palette.muted,
            gripcount=0,
            **flat,
        )
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
        self._draw_chart()

    def _draw_chart(self) -> None:
        """Draw the chart with the colors of the current theme."""
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
            wpm_axis.plot(
                data.dates,
                data.wpm,
                color=palette.text,
                linewidth=1.4,
                marker="o",
                markersize=3,
                label="wpm",
            )
            err_axis.plot(
                data.dates,
                data.error_rate,
                color=palette.muted,
                linewidth=1.1,
                linestyle="--",
                marker="o",
                markersize=2,
                label="% ошибок",
            )
            wpm_axis.set_ylim(bottom=0)
            err_axis.set_ylim(bottom=0)
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

    def _insert_chunk(self, sessions: list[Session], start: int) -> None:
        """Insert the next chunk of rows.

        Args:
            sessions: All sessions.
            start: Index of the first row of the chunk.
        """
        for session in sessions[start : start + INSERT_CHUNK]:
            self.table.insert(
                "", "end", iid=str(session.id), values=row_values(session)
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
        palette = self.theme.palette
        self.message.configure(
            text=text, fg=palette.error if is_error else palette.muted
        )


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
