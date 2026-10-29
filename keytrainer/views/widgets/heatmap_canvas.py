"""Heatmap of the keyboard (ТЗ, п. 4.2.1; Figma: рисунок 8)."""

import tkinter as tk
from collections.abc import Callable

from keytrainer.data.models import Key
from keytrainer.engine.analytics_engine import (
    HeatmapData,
    KeyCell,
    Metric,
    heat_color,
)
from keytrainer.views.theme import Palette, ThemeManager
from keytrainer.views.widgets.keyboard_canvas import KeyboardCanvas


class HeatmapCanvas(KeyboardCanvas):
    """Keyboard whose keys are colored by error rate or reaction time.

    Inherits the drawing of keys from :class:`KeyboardCanvas` (DRY) and
    overrides only the fill and the caption of a key.
    """

    key_size = 54
    reveal_ms = 460

    def __init__(self, parent: tk.Misc, theme: ThemeManager) -> None:
        """Create an empty heatmap.

        Args:
            parent: Parent widget.
            theme: Theme manager.
        """
        super().__init__(parent, theme)
        self.data: HeatmapData | None = None
        self.on_hover: Callable[[KeyCell | None, int, int], None] | None = None
        self.tag_bind("key", "<Motion>", self._motion, add="+")
        self.tag_bind(
            "key", "<Leave>", lambda _e: self._emit_hover(None, 0, 0), add="+"
        )

    def show(self, data: HeatmapData, keys: list[Key]) -> None:
        """Draw new statistics.

        Args:
            data: Heatmap data.
            keys: Keys of the layout.
        """
        old_fills = dict(self._fills)
        self.data = data
        digits_used = any(c.attempts for c in data.cells.values() if c.key.row_num == 0)
        self.set_keys(keys, show_digits=digits_used)
        self._reveal(old_fills)

    def _reveal(self, old_fills: dict[str, str]) -> None:
        """Let the colors flow over the keyboard from left to right.

        On the first show keys start grey; after a filter change every key
        flows from its previous color to the new one.

        Args:
            old_fills: Key colors before the redraw.
        """
        palette = self.theme.palette
        for char, key in self._by_char.items():
            start = old_fills.get(char, palette.heat_empty)
            self._paint(char, start)
            delay = int(key.pos_x * 26 + key.pos_y * 34)
            self.fade_key(char, start, self.reveal_ms, delay_ms=delay)

    def color_for(self, cell: KeyCell, palette: Palette) -> str:
        """Color of a key on the scale (grey if there is too little data).

        Args:
            cell: Key statistics.
            palette: Current palette.

        Returns:
            Hex color.
        """
        ratio = self.data.ratio(cell) if self.data else None
        if ratio is None:
            return palette.heat_empty
        return heat_color(ratio, palette.heat_saturation, palette.heat_value)

    def key_fill(self, key: Key, palette: Palette) -> str:
        """Fill a key with its heat color.

        Args:
            key: Key to paint.
            palette: Current palette.

        Returns:
            Hex color.
        """
        cell = self.data.cells.get(key.key_char) if self.data else None
        return self.color_for(cell, palette) if cell else palette.heat_empty

    def draw_key_text(self, key: Key, box: tuple, palette: Palette) -> None:
        """Draw the character and the value under it ("27%", "412", "<5").

        Args:
            key: Key.
            box: Key rectangle.
            palette: Current palette.
        """
        x0, y0, x1, y1 = box
        cell = self.data.cells.get(key.key_char) if self.data else None
        tags = ("key", f"key:{ord(key.key_char)}")
        center = (x0 + x1) / 2
        self.create_text(
            center,
            y0 + 18,
            text=key.key_char,
            fill=palette.text,
            font=self.theme.fonts["key"],
            tags=tags,
        )
        caption = value_caption(cell, self.data.metric) if cell else ""
        self.create_text(
            center,
            y1 - 11,
            text=caption,
            fill=palette.muted,
            font=self.theme.fonts["tiny"],
            tags=tags,
        )

    def _motion(self, event: tk.Event) -> None:
        """Find the key under the pointer and report it.

        Args:
            event: Tk motion event.
        """
        item = self.find_withtag("current")
        if not item or self.data is None:
            return
        for tag in self.gettags(item[0]):
            if tag.startswith("key:"):
                cell = self.data.cells.get(chr(int(tag[4:])))
                self._emit_hover(cell, event.x_root, event.y_root)
                return

    def _emit_hover(self, cell: KeyCell | None, x: int, y: int) -> None:
        """Pass the hovered key to the screen.

        Args:
            cell: Key under the pointer or ``None``.
            x: Pointer X (screen).
            y: Pointer Y (screen).
        """
        if self.on_hover:
            self.on_hover(cell, x, y)


def value_caption(cell: KeyCell, metric: Metric) -> str:
    """Short value written on a key.

    Args:
        cell: Key statistics.
        metric: Chosen metric.

    Returns:
        "<5" for too little data, "27%" or "412" otherwise.
    """
    if not cell.enough_data:
        return "<5"
    if metric == Metric.ERROR_RATE:
        return f"{cell.error_rate:.0f}%"
    return f"{cell.avg_latency_ms:.0f}" if cell.avg_latency_ms else "—"
