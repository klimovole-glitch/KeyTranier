"""Thin slider with a round knob (Figma: «Настройки», размер шрифта).

``ttk.Scale`` looks like a grey box on Windows and cannot be animated, so
the slider is drawn on a Canvas: a thin line, the filled part up to the
knob, and the knob that grows under the mouse and moves smoothly.
"""

import tkinter as tk
from collections.abc import Callable

from keytrainer.views.animation import HOVER_MS, Animator
from keytrainer.views.theme import ThemeManager

KNOB_RADIUS = 6
KNOB_HOVER_RADIUS = 8
MOVE_MS = 160
HEIGHT = 40
LINE_Y = 14


class Slider(tk.Canvas):
    """Integer slider from ``low`` to ``high``."""

    def __init__(
        self,
        parent: tk.Misc,
        theme: ThemeManager,
        low: int,
        high: int,
        command: Callable[[int], None],
        length: int = 260,
    ) -> None:
        """Create the slider.

        Args:
            parent: Parent widget.
            theme: Theme manager.
            low: Minimal value.
            high: Maximal value.
            command: Called with the new value when the user moves the knob.
            length: Width in pixels.
        """
        super().__init__(
            parent, width=length, height=HEIGHT, bd=0, highlightthickness=0
        )
        self.theme = theme
        theme.style(self, bg="bg")
        self.low, self.high = low, high
        self.command = command
        self.length = length
        self.value = low
        self._x = self._x_of(low)
        self._radius = KNOB_RADIUS
        self.animator = Animator(self)
        self.bind("<Button-1>", self._drag)
        self.bind("<B1-Motion>", self._drag)
        self.bind("<Enter>", lambda _e: self._grow(KNOB_HOVER_RADIUS))
        self.bind("<Leave>", lambda _e: self._grow(KNOB_RADIUS))
        theme.on_change(lambda _p: self._draw())
        self._draw()

    @property
    def _left(self) -> int:
        """X of the line start (room for the knob)."""
        return KNOB_HOVER_RADIUS + 1

    @property
    def _right(self) -> int:
        """X of the line end."""
        return self.length - KNOB_HOVER_RADIUS - 1

    def _x_of(self, value: int) -> float:
        """Convert a value to the knob position.

        Args:
            value: Slider value.

        Returns:
            X coordinate.
        """
        share = (value - self.low) / (self.high - self.low)
        return KNOB_HOVER_RADIUS + 1 + share * (self.length - 2 * KNOB_HOVER_RADIUS - 2)

    def _value_of(self, x: float) -> int:
        """Convert a position to the nearest value.

        Args:
            x: X coordinate.

        Returns:
            Value between ``low`` and ``high``.
        """
        share = (x - self._left) / (self._right - self._left)
        value = round(self.low + share * (self.high - self.low))
        return min(max(value, self.low), self.high)

    def _draw(self) -> None:
        """Draw the line, the filled part, the knob and the end values."""
        palette = self.theme.palette
        self.delete("all")
        self.create_line(
            self._left, LINE_Y, self._right, LINE_Y, fill=palette.border, width=2
        )
        self.create_line(
            self._left, LINE_Y, self._x, LINE_Y, fill=palette.muted, width=2
        )
        r = self._radius
        self.create_oval(
            self._x - r,
            LINE_Y - r,
            self._x + r,
            LINE_Y + r,
            fill=palette.text,
            outline="",
        )
        font = self.theme.fonts["tiny"]
        self.create_text(
            self._left, HEIGHT - 6, text=str(self.low), fill=palette.dim, font=font
        )
        self.create_text(
            self._right, HEIGHT - 6, text=str(self.high), fill=palette.dim, font=font
        )

    def _grow(self, radius: int) -> None:
        """Change the knob size smoothly (hover).

        Args:
            radius: Final radius.
        """
        start = self._radius

        def step(t: float) -> None:
            self._radius = start + (radius - start) * t
            self._draw()

        self.animator.run("grow", HOVER_MS, step)

    def _drag(self, event: tk.Event) -> None:
        """Move the knob after the mouse and report a new value.

        Args:
            event: Tk mouse event.
        """
        value = self._value_of(event.x)
        self.animator.cancel("move")
        self._x = self._x_of(value)
        self._draw()
        if value != self.value:
            self.value = value
            self.command(value)

    def get(self) -> int:
        """Current value.

        Returns:
            Value.
        """
        return self.value

    def set(self, value: int) -> None:
        """Move the knob to a value smoothly (without calling the command).

        Args:
            value: New value.
        """
        self.value = min(max(int(value), self.low), self.high)
        start, end = self._x, self._x_of(self.value)

        def step(t: float) -> None:
            self._x = start + (end - start) * t
            self._draw()

        self.animator.run("move", MOVE_MS, step)
