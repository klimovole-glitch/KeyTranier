"""On-screen keyboard drawn on a Canvas from ``tbl_keys`` coordinates.

The keyboard is drawn once; after that only the changed keys are recolored
(no full redraw on every key press), and colors change smoothly.
Figma «СПЕЦИФИКАЦИЯ»: hover — background 6 %, pressed — background 10 % and
scale 0.96 for 0.1 s, next key — background 12 % with a brighter border,
error — muted red.
"""

import tkinter as tk

from keytrainer.data.keyboard_layouts import SPACE_CHAR
from keytrainer.data.models import Key
from keytrainer.views.animation import KEY_PRESS_MS, Animator, ease_in_out, mix_colors
from keytrainer.views.display import px
from keytrainer.views.theme import Palette, ThemeManager

SPACE_WIDTH_UNITS = 6
HIGHLIGHT_MS = 140
FLASH_MS = 320
PRESS_SCALE = 0.96
HOVER_MIX = 0.06


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

    key_size = 46
    gap = 7
    padding = 4
    radius = 9

    def __init__(self, parent: tk.Misc, theme: ThemeManager) -> None:
        """Create an empty keyboard.

        Args:
            parent: Parent widget.
            theme: Theme manager.
        """
        super().__init__(parent, bd=0, highlightthickness=0)
        cls = type(self)
        # sizes of the mockup, converted to screen pixels (high-DPI screens)
        self.key_size = px(cls.key_size)
        self.gap = px(cls.gap)
        self.padding = px(cls.padding)
        self.radius = px(cls.radius)
        self.theme = theme
        theme.style(self, bg="bg")
        theme.on_change(lambda _p: self.redraw())
        self._keys: list[Key] = []
        self._show_digits = False
        self._highlighted: str | None = None
        self._shapes: dict[str, int] = {}
        self._texts: dict[str, list[int]] = {}
        self._fills: dict[str, str] = {}
        self._by_char: dict[str, Key] = {}
        self._boxes: dict[str, tuple[float, float, float, float]] = {}
        self._hovered: str | None = None
        self._scales: dict[str, float] = {}
        self.animator = Animator(self)
        self.tag_bind("key", "<Enter>", self._on_enter, add="+")
        self.tag_bind("key", "<Leave>", self._on_leave, add="+")

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
        self.create_text(
            (x0 + x1) / 2,
            (y0 + y1) / 2,
            text=key.key_char,
            fill=self.key_text_color(key, palette),
            font=self.theme.fonts["key"],
            tags=("key", f"key:{ord(key.key_char)}"),
        )

    def key_text_color(self, key: Key, palette: Palette) -> str:
        """Choose the caption color of a key.

        Args:
            key: Key.
            palette: Current palette.

        Returns:
            Hex color.
        """
        return palette.text if key.key_char == self._highlighted else palette.muted

    def key_outline(self, key: Key, palette: Palette) -> str:
        """Choose the border color of a key.

        Args:
            key: Key.
            palette: Current palette.

        Returns:
            Hex color.
        """
        return palette.muted if key.key_char == self._highlighted else palette.border

    def redraw(self) -> None:
        """Draw all visible keys again (layout or theme changed)."""
        self.animator.cancel_all()
        self.delete("all")
        self._shapes.clear()
        self._texts.clear()
        self._fills.clear()
        self._by_char.clear()
        self._boxes.clear()
        self._scales.clear()
        keys = self.visible_keys()
        if not keys:
            return
        palette = self.theme.palette
        right = bottom = 0.0
        for key in keys:
            box = self.key_box(key)
            char = key.key_char
            fill = self.key_fill(key, palette)
            self._boxes[char] = box
            self._shapes[char] = rounded_rect(
                self,
                *box,
                self.radius,
                fill=fill,
                outline=self.key_outline(key, palette),
                tags=("key", f"key:{ord(char)}"),
            )
            self._fills[char] = fill
            self._by_char[char] = key
            self.draw_key_text(key, box, palette)
            self._texts[char] = [
                item
                for item in self.find_withtag(f"key:{ord(char)}")
                if self.type(item) == "text"
            ]
            right, bottom = max(right, box[2]), max(bottom, box[3])
        self.configure(width=right + self.padding, height=bottom + self.padding)

    # ------------------------------------------------------- animation
    def _paint(self, char: str, fill: str) -> None:
        """Set the fill of one key without redrawing the keyboard.

        Args:
            char: Base character of the key.
            fill: New fill color.
        """
        self.itemconfigure(self._shapes[char], fill=fill)
        self._fills[char] = fill

    def fade_key(
        self, char: str, start: str, duration_ms: int, delay_ms: int = 0
    ) -> None:
        """Change the fill of a key smoothly from ``start`` to its normal color.

        The target color is asked on every frame, so if the key stops being
        highlighted in the middle of the animation, it fades to the new color.

        Args:
            char: Base character of the key.
            start: Color of the first frame.
            duration_ms: Length of the animation.
            delay_ms: Pause before the start (waves over the keyboard).
        """
        key = self._by_char.get(char)
        if key is None:
            return

        def step(t: float) -> None:
            end = self.target_fill(key)
            self._paint(char, mix_colors(start, end, t))

        self.animator.run(f"fill:{char}", duration_ms, step, delay_ms=delay_ms)

    def _restyle(self, char: str | None) -> None:
        """Update border and caption of a key and fade its fill.

        Args:
            char: Base character of the key.
        """
        key = self._by_char.get(char) if char is not None else None
        if key is None:
            return
        palette = self.theme.palette
        self.itemconfigure(self._shapes[char], outline=self.key_outline(key, palette))
        for item in self._texts.get(char, []):
            self.itemconfigure(item, fill=self.key_text_color(key, palette))
        if not self.animator.is_running(f"fill:{char}"):
            # a running flash already fades to the new target color
            self.fade_key(char, self._fills[char], HIGHLIGHT_MS)

    def highlight(self, char: str | None) -> None:
        """Highlight the key that must be pressed next.

        Only two keys are recolored: the old and the new one.

        Args:
            char: Base character of the key, ``None`` to clear.
        """
        if char == self._highlighted:
            return
        old, self._highlighted = self._highlighted, char
        self._restyle(old)
        self._restyle(char)

    def flash(self, char: str | None, is_correct: bool) -> None:
        """Briefly light up a pressed key and let it fade back.

        Args:
            char: Base character of the pressed key.
            is_correct: Green-grey flash for a correct press, red for an error.
        """
        if char is None or char not in self._shapes:
            return
        palette = self.theme.palette
        if is_correct:
            start = mix_colors(palette.surface, palette.muted, 0.55)
        else:
            start = mix_colors(palette.surface, palette.error, 0.8)
        self._paint(char, start)
        self.fade_key(char, start, FLASH_MS)

    def press(self, char: str | None, is_correct: bool) -> None:
        """Animate a key press: flash plus a short "push" (scale 0.96).

        Args:
            char: Base character of the pressed key.
            is_correct: Whether the press was correct.
        """
        if char is None or char not in self._shapes:
            return
        self.flash(char, is_correct)
        x0, y0, x1, y1 = self._boxes[char]
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        tag = f"key:{ord(char)}"

        def set_scale(target: float) -> None:
            # a press interrupted by the next one continues from its scale
            factor = target / self._scales.get(char, 1.0)
            self.scale(tag, cx, cy, factor, factor)
            self._scales[char] = target

        def step(t: float) -> None:
            # down to 0.96 in the first half, back to 1.0 in the second
            set_scale(1 - (1 - PRESS_SCALE) * (1 - abs(2 * t - 1)))

        def done() -> None:
            set_scale(1.0)

        self.animator.run(
            f"press:{char}", KEY_PRESS_MS * 2, step, done, easing=ease_in_out
        )

    # ----------------------------------------------------------- hover
    def target_fill(self, key: Key) -> str:
        """Fill a key should end at: its own color, lighter under the mouse.

        Args:
            key: Key.

        Returns:
            Hex color.
        """
        palette = self.theme.palette
        fill = self.key_fill(key, palette)
        if key.key_char == self._hovered:
            fill = mix_colors(fill, palette.text, HOVER_MIX)
        return fill

    def _char_under_mouse(self) -> str | None:
        """Find the key under the mouse pointer.

        Returns:
            Base character or ``None``.
        """
        item = self.find_withtag("current")
        if not item:
            return None
        for tag in self.gettags(item[0]):
            if tag.startswith("key:"):
                return chr(int(tag[4:]))
        return None

    def _on_enter(self, _event: tk.Event) -> None:
        """Lighten the key under the mouse.

        Args:
            _event: Tk event (unused).
        """
        char = self._char_under_mouse()
        if char == self._hovered:
            return
        old, self._hovered = self._hovered, char
        for key_char in (old, char):
            if key_char in self._fills and not self.animator.is_running(
                f"fill:{key_char}"
            ):
                self.fade_key(key_char, self._fills[key_char], HIGHLIGHT_MS)

    def _on_leave(self, _event: tk.Event) -> None:
        """Return the key color when the mouse leaves it.

        Args:
            _event: Tk event (unused).
        """
        old, self._hovered = self._hovered, None
        if old in self._fills:
            self.fade_key(old, self._fills[old], HIGHLIGHT_MS)
