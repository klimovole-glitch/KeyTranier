"""Statistics screen: heatmap and problem keys (Figma: рисунок 8)."""

import tkinter as tk
from collections.abc import Callable

from keytrainer.data.keyboard_layouts import FINGER_NAMES, LAYOUT_EN, LAYOUT_RU
from keytrainer.data.models import Key
from keytrainer.engine.analytics_engine import (
    HeatmapData,
    KeyCell,
    Metric,
    Period,
    heat_color,
)
from keytrainer.labels import format_number
from keytrainer.views.animation import Animator
from keytrainer.views.theme import ThemeManager
from keytrainer.views.widgets.heatmap_canvas import HeatmapCanvas
from keytrainer.views.widgets.text_button import TextButton
from keytrainer.views.widgets.tooltip import Tooltip

METRIC_TITLES = {Metric.ERROR_RATE: "% ошибок", Metric.LATENCY: "время реакции"}
METRIC_LONG_TITLES = {
    Metric.ERROR_RATE: "процент ошибок",
    Metric.LATENCY: "время реакции",
}
PERIOD_TITLES = {
    Period.LAST_SESSION: "последняя сессия",
    Period.DAYS_7: "7 дней",
    Period.DAYS_30: "30 дней",
    Period.ALL: "всё время",
}

LEGEND_WIDTH = 230
LEGEND_STEPS = 46


class StatsScreen(tk.Frame):
    """Passive view of the statistics tab."""

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
        self.data: HeatmapData | None = None
        self.animator = Animator(self)
        body = theme.frame(self)
        body.place(relx=0.5, rely=0.46, anchor="center")
        left = theme.frame(body)
        left.grid(row=0, column=0, sticky="n")
        right = theme.frame(body)
        right.grid(row=0, column=1, sticky="n", padx=(70, 0), pady=(150, 0))

        self.metric_buttons = self._option_row(
            left, "метрика:", METRIC_TITLES, "metric"
        )
        self.period_buttons = self._option_row(left, "период:", PERIOD_TITLES, "period")
        self.layout_buttons = self._option_row(
            left, "раскладка:", {LAYOUT_RU: "RU", LAYOUT_EN: "EN"}, "layout"
        )
        self.title = theme.label(left, "", role="muted", font="small")
        self.title.pack(pady=(26, 14))
        self.heatmap = HeatmapCanvas(left, theme)
        self.heatmap.pack()
        self.heatmap.on_hover = self._on_hover
        self._build_legend(left)
        self.status = theme.label(left, "", role="muted", font="small")
        self.status.pack(anchor="w", pady=(10, 0))
        self._build_top(right)
        self.tooltip = Tooltip(self, theme)
        theme.on_change(lambda _p: self._redraw_legend())

    # ------------------------------------------------------------ build
    def _emit(self, name: str, *args) -> None:
        """Call a controller callback.

        Args:
            name: Callback name.
            *args: Arguments.
        """
        callback = self.callbacks.get(name)
        if callback:
            callback(*args)

    def _option_row(
        self, parent: tk.Misc, caption: str, options: dict, event: str
    ) -> dict:
        """Create a row "caption: option option option".

        Args:
            parent: Container.
            caption: Row caption.
            options: Value -> title.
            event: Callback name called with the chosen value.

        Returns:
            Value -> button.
        """
        row = self.theme.frame(parent)
        row.pack(pady=3)
        self.theme.label(row, caption, role="muted").pack(side="left", padx=(0, 20))
        buttons = {}
        for value, title in options.items():
            button = TextButton(
                row, self.theme, title, lambda v=value: self._emit(event, v)
            )
            button.pack(side="left", padx=12)
            buttons[value] = button
        return buttons

    def _build_legend(self, parent: tk.Misc) -> None:
        """Create the color scale and the grey key explanation.

        Args:
            parent: Container.
        """
        row = self.theme.frame(parent)
        row.pack(anchor="w", pady=(18, 0))
        self.legend_low = self.theme.label(row, "0 %", role="muted", font="tiny")
        self.legend_low.pack(side="left")
        self.legend = tk.Canvas(
            row, width=LEGEND_WIDTH, height=8, bd=0, highlightthickness=0
        )
        self.theme.style(self.legend, bg="bg")
        self.legend.pack(side="left", padx=8)
        self.legend_high = self.theme.label(row, "30 %+", role="muted", font="tiny")
        self.legend_high.pack(side="left")
        self.grey_box = tk.Frame(row, width=10, height=10)
        self.theme.style(self.grey_box, bg="heat_empty")
        self.grey_box.pack(side="left", padx=(40, 8))
        self.theme.label(
            row, "меньше 5 нажатий — недостаточно данных", role="muted", font="tiny"
        ).pack(side="left")
        self._redraw_legend()

    def _redraw_legend(self) -> None:
        """Paint the gradient of the color scale."""
        palette = self.theme.palette
        self.legend.delete("all")
        step = LEGEND_WIDTH / LEGEND_STEPS
        for index in range(LEGEND_STEPS):
            color = heat_color(
                index / (LEGEND_STEPS - 1),
                palette.heat_saturation,
                palette.heat_value,
            )
            self.legend.create_rectangle(
                index * step, 0, (index + 1) * step + 1, 8, fill=color, width=0
            )

    def _build_top(self, parent: tk.Misc) -> None:
        """Create the list of problem keys and the training button.

        Args:
            parent: Container.
        """
        self.theme.label(parent, "проблемные клавиши", role="muted", font="small").pack(
            anchor="w"
        )
        self.top_frame = self.theme.frame(parent)
        self.top_frame.pack(anchor="w", pady=(12, 30))
        self.train_button = TextButton(
            parent,
            self.theme,
            "тренировать слабые клавиши",
            lambda: self._emit("train"),
            role="text",
        )
        self.train_button.pack(anchor="w")

    # ----------------------------------------------------------- update
    def show_filters(self, metric: Metric, period: Period, layout_name: str) -> None:
        """Underline the chosen filters.

        Args:
            metric: Chosen metric.
            period: Chosen period.
            layout_name: Chosen layout.
        """
        for groups, chosen in (
            (self.metric_buttons, metric),
            (self.period_buttons, period),
            (self.layout_buttons, layout_name),
        ):
            for value, button in groups.items():
                button.set_state(selected=value == chosen)

    def show_loading(self) -> None:
        """Show that the statistics are being calculated."""
        self.status.configure(text="расчет статистики…")

    def show_error(self, text: str) -> None:
        """Show an error instead of the heatmap.

        Args:
            text: Error text.
        """
        self.status.configure(text=text, fg=self.theme.palette.error)

    def show_data(self, data: HeatmapData, keys: list[Key]) -> None:
        """Draw the heatmap and the problem keys.

        Args:
            data: Heatmap data.
            keys: Keys of the layout.
        """
        self.data = data
        metric_title = METRIC_LONG_TITLES[data.metric]
        self.title.configure(
            text=f"тепловая карта клавиатуры — {metric_title}, "
            f"{PERIOD_TITLES[data.period]}"
        )
        self.heatmap.show(data, keys)
        if data.metric == Metric.ERROR_RATE:
            low, high = "0 %", f"{data.scale_max:.0f} %+"
        else:
            low, high = f"{data.scale_min:.0f} мс", f"{data.scale_max:.0f} мс"
        self.legend_low.configure(text=low)
        self.legend_high.configure(text=high)
        self.status.configure(
            text="" if data.sessions_found else "за этот период тренировок нет",
            fg=self.theme.palette.muted,
        )
        self._show_top(data)

    def _show_top(self, data: HeatmapData) -> None:
        """Fill the list of problem keys.

        Args:
            data: Heatmap data.
        """
        for child in self.top_frame.winfo_children():
            child.destroy()
        if not data.top:
            self.theme.label(
                self.top_frame, "недостаточно данных", role="dim", font="small"
            ).pack(anchor="w")
        for rank, cell in enumerate(data.top, start=1):
            row = self.theme.frame(self.top_frame)
            row.pack(anchor="w", pady=6)
            self.theme.label(row, str(rank), role="muted", font="small").pack(
                side="left", padx=(0, 16)
            )
            box = tk.Label(
                row,
                text=cell.key.key_char,
                width=3,
                height=1,
                font=self.theme.fonts["key"],
                bg=self.heatmap.color_for(cell, self.theme.palette),
                fg=self.theme.palette.text,
            )
            box.pack(side="left", ipady=8)
            info = self.theme.frame(row)
            info.pack(side="left", padx=(16, 0))
            self.theme.label(info, f"{format_number(cell.error_rate)} %").pack(
                anchor="w"
            )
            latency = cell.avg_latency_ms
            self.theme.label(
                info,
                f"реакция {latency:.0f} мс" if latency else "реакция —",
                role="muted",
                font="tiny",
            ).pack(anchor="w")
            self._fade_row(row, rank)

    def _fade_row(self, row: tk.Misc, rank: int) -> None:
        """Let a row of the problem keys appear after the previous one.

        Args:
            row: Row frame.
            rank: Place in the top (1 — first).
        """
        palette = self.theme.palette
        delay = 260 + rank * 90
        stack = [row]
        while stack:
            widget = stack.pop()
            stack.extend(widget.winfo_children())
            if isinstance(widget, tk.Label):
                for option in ("fg", "bg"):
                    end = widget.cget(option)
                    if end != palette.bg:
                        self.animator.fade(
                            f"top{id(widget)}{option}",
                            widget,
                            option,
                            palette.bg,
                            end,
                            320,
                            delay,
                        )

    def _on_hover(self, cell: KeyCell | None, x: int, y: int) -> None:
        """Show or hide the tooltip of a key.

        Args:
            cell: Key under the pointer.
            x: Pointer X (screen).
            y: Pointer Y (screen).
        """
        if cell is None:
            self.tooltip.hide()
            return
        self.tooltip.show(x, y, tooltip_text(cell))


def tooltip_text(cell: KeyCell) -> str:
    """Text of the key tooltip (ТЗ, п. 4.2.1).

    Args:
        cell: Key statistics.

    Returns:
        Multi-line text.
    """
    name = "пробел" if cell.key.key_char == " " else f"«{cell.key.key_char}»"
    latency = f"{cell.avg_latency_ms:.0f} мс" if cell.avg_latency_ms else "—"
    lines = [
        f"клавиша {name}",
        f"нажатий: {cell.attempts}",
        f"ошибок: {cell.errors}",
        f"процент ошибок: {format_number(cell.error_rate)} %",
        f"время реакции: {latency}",
        f"палец: {FINGER_NAMES[cell.key.finger]}",
    ]
    if not cell.enough_data:
        lines.append("меньше 5 нажатий — данных мало")
    return "\n".join(lines)
