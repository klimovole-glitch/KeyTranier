"""On-screen keyboard drawn on a Canvas from ``tbl_keys`` coordinates."""

import tkinter as tk

from keytrainer.data.keyboard_layouts import SPACE_CHAR
from keytrainer.data.models import Key
from keytrainer.views.theme import Palette, ThemeManager

SPACE_WIDTH_UNITS = 6


def rounded_rect(
    canvas: tk.Canvas, x0: float, y0: float, x1: float, y1: float, radius: float, **kw
) -> int:
    """Draw a rectangle with rounded corners.

    Args:
        canvas: Target canvas.
        x0: Left edge.
        y0: Top edge.
        x1: Right edge.
        y1: Bottom edge.
        radius: Corner radius.
        **kw: Canvas polygon options (fill, outline, tags...).

    Returns:
        Canvas item id.
    """
    points = [
        x0 + radius,
        y0,
        x1 - radius,
        y0,
        x1,
        y0,
        x1,
        y0 + radius,
        x1,
        y1 - radius,
        x1,
        y1,
        x1 - radius,
        y1,
        x0 + radius,
        y1,
        x0,
        y1,
        x0,
        y1 - radius,
        x0,
        y0 + radius,
        x0,
        y0,
    ]
    return canvas.create_polygon(points, smooth=True, **kw)


class KeyboardCanvas(tk.Canvas):
    """Keyboard with the highlighted next key (ТЗ, п. 4.1.6)."""

    key_size = 40
    gap = 6
    padding = 4
    radius = 8

    def __init__(self, parent: tk.Misc, theme: ThemeManager) -> None:
        """Create an empty keyboard.

        Args:
            parent: Parent widget.
            theme: Theme manager.
        """
        super().__init__(parent, bd=0, highlightthickness=0)
        self.theme = theme
        theme.style(self, bg="bg")
        theme.on_change(lambda _p: self.redraw())
        self._keys: list[Key] = []
        self._show_digits = False
        self._highlighted: str | None = None
        self._shapes: dict[str, int] = {}

    @property
    def unit(self) -> int:
        """Distance between neighbouring keys in pixels."""
        return self.key_size + self.gap

    def set_keys(self, keys: list[Key], show_digits: bool = False) -> None:
        """Set the layout to draw.

        Args:
            keys: Keys of the layout.
            show_digits: Draw the digit row (exercises with digits).
        """
        self._keys = keys
        self._show_digits = show_digits
        self.redraw()

    def visible_keys(self) -> list[Key]:
        """Keys that are drawn (the digit row is optional).

        Returns:
            Keys to draw.
        """
        return [k for k in self._keys if self._show_digits or k.row_num != 0]

    def key_box(self, key: Key) -> tuple[float, float, float, float]:
        """Calculate the rectangle of a key.

        Args:
            key: Key to place.

        Returns:
            Coordinates ``x0, y0, x1, y1``.
        """
        keys = self.visible_keys()
        min_x = min(k.pos_x for k in keys)
        min_y = min(k.pos_y for k in keys)
        x0 = self.padding + (key.pos_x - min_x) * self.unit
        y0 = self.padding + (key.pos_y - min_y) * self.unit
        units = SPACE_WIDTH_UNITS if key.key_char == SPACE_CHAR else 1
        width = units * self.unit - self.gap
        return x0, y0, x0 + width, y0 + self.key_size

    def key_fill(self, key: Key, palette: Palette) -> str:
        """Choose the fill color of a key (overridden by the heatmap).

        Args:
            key: Key to paint.
            palette: Current palette.

        Returns:
            Hex color.
        """
        if key.key_char == self._highlighted:
            return palette.surface_active
        return palette.surface

    def draw_key_text(self, key: Key, box: tuple, palette: Palette) -> None:
        """Draw the caption of a key (overridden by the heatmap).

        Args:
            key: Key.
            box: Key rectangle.
            palette: Current palette.
        """
        x0, y0, x1, y1 = box
        color = palette.text if key.key_char == self._highlighted else palette.muted
        self.create_text(
            (x0 + x1) / 2,
            (y0 + y1) / 2,
            text=key.key_char,
            fill=color,
            font=self.theme.fonts["key"],
            tags=("key", f"key:{ord(key.key_char)}"),
        )

    def redraw(self) -> None:
        """Draw all visible keys again."""
        self.delete("all")
        self._shapes.clear()
        keys = self.visible_keys()
        if not keys:
            return
        palette = self.theme.palette
        right = bottom = 0.0
        for key in keys:
            box = self.key_box(key)
            highlighted = key.key_char == self._highlighted
            self._shapes[key.key_char] = rounded_rect(
                self,
                *box,
                self.radius,
                fill=self.key_fill(key, palette),
                outline=palette.muted if highlighted else palette.border,
                tags=("key", f"key:{ord(key.key_char)}"),
            )
            self.draw_key_text(key, box, palette)
            right, bottom = max(right, box[2]), max(bottom, box[3])
        self.configure(width=right + self.padding, height=bottom + self.padding)

    def highlight(self, char: str | None) -> None:
        """Highlight the key that must be pressed next.

        Args:
            char: Base character of the key, ``None`` to clear.
        """
        if char != self._highlighted:
            self._highlighted = char
            self.redraw()
