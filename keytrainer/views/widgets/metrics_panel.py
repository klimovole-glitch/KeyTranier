"""Row of metrics: a big number with a small caption under it."""

import tkinter as tk

from keytrainer.views.theme import ThemeManager


class MetricsPanel(tk.Frame):
    """Horizontal set of metric cells (training screen and results card)."""

    def __init__(
        self,
        parent: tk.Misc,
        theme: ThemeManager,
        captions: dict[str, str],
        value_font: str = "metric",
        cell_width: int = 12,
    ) -> None:
        """Create cells.

        Args:
            parent: Parent widget.
            theme: Theme manager.
            captions: Metric key -> caption ("wpm" -> "wpm").
            value_font: Font of the values.
            cell_width: Width of a cell in characters.
        """
        super().__init__(parent, bd=0)
        theme.style(self, bg="bg")
        self._values: dict[str, tk.Label] = {}
        for column, (key, caption) in enumerate(captions.items()):
            cell = theme.frame(self)
            cell.grid(row=0, column=column, padx=6)
            value = theme.label(cell, "0", font=value_font, width=cell_width)
            value.pack()
            theme.label(cell, caption, role="muted", font="tiny").pack(pady=(4, 0))
            self._values[key] = value

    def set_values(self, values: dict[str, str]) -> None:
        """Show new values.

        Args:
            values: Metric key -> formatted text.
        """
        for key, text in values.items():
            self._values[key].configure(text=text)
