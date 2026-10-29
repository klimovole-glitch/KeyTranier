"""Thin scrollbar in the colors of the theme.

The standard scrollbar on Windows is a wide light-grey bar with arrows that
does not fit the dark design. This one is a rounded thumb on a canvas: it
widens under the mouse and hides itself when everything fits.
"""

import tkinter as tk
from collections.abc import Callable

from keytrainer.views.animation import HOVER_MS, Animator
from keytrainer.views.display import px
from keytrainer.views.theme import ThemeManager

THIN = 4
WIDE = 8


class SlimScrollbar(tk.Canvas):
    """Vertical scrollbar compatible with ``yscrollcommand``."""

    def __init__(
        self, parent: tk.Misc, theme: ThemeManager, command: Callable[..., None]
    ) -> None:
        """Create the scrollbar.

        Args:
            parent: Parent widget.
            theme: Theme manager.
            command: The ``yview`` method of the scrolled widget.
        """
        super().__init__(parent, width=px(WIDE + 4), bd=0, highlightthickness=0)
        self.theme = theme
        theme.style(self, bg="bg")
        self.command = command
        self.first, self.last = 0.0, 1.0
        self._width = px(THIN)
        self._drag_from: tuple[int, float] | None = None
        self.animator = Animator(self)
        self.bind("<Configure>", lambda _e: self._draw())
        self.bind("<Enter>", lambda _e: self._resize(px(WIDE)))
        self.bind("<Leave>", lambda _e: self._resize(px(THIN)))
        self.bind("<Button-1>", self._press)
        self.bind("<B1-Motion>", self._drag)
        self.bind("<ButtonRelease-1>", lambda _e: setattr(self, "_drag_from", None))
        theme.on_change(lambda _p: self._draw())

    def set(self, first: str, last: str) -> None:
        """Receive the visible part from the scrolled widget.

        Args:
            first: Start of the visible part (0..1).
            last: End of the visible part (0..1).
        """
        self.first, self.last = float(first), float(last)
        self._draw()

    def _draw(self) -> None:
        """Draw the thumb (nothing if all rows are visible)."""
        self.delete("all")
        if self.last - self.first >= 0.999:
            return
        height = self.winfo_height()
        width = self.winfo_width()
        top, bottom = self.first * height, self.last * height
        x = width - px(2) - self._width / 2
        self.create_line(
            x,
            top + self._width / 2,
            x,
            bottom - self._width / 2,
            width=self._width,
            capstyle="round",
            fill=self.theme.palette.dim,
        )

    def _resize(self, width: int) -> None:
        """Widen or narrow the thumb smoothly.

        Args:
            width: Final width.
        """
        start = self._width

        def step(t: float) -> None:
            self._width = start + (width - start) * t
            self._draw()

        self.animator.run("width", HOVER_MS, step)

    def _press(self, event: tk.Event) -> None:
        """Start dragging the thumb or jump to the clicked place.

        Args:
            event: Tk mouse event.
        """
        height = max(1, self.winfo_height())
        position = event.y / height
        if not self.first <= position <= self.last:
            size = self.last - self.first
            self.command("moveto", max(0.0, position - size / 2))
        self._drag_from = (event.y, self.first)

    def _drag(self, event: tk.Event) -> None:
        """Move the visible part after the mouse.

        Args:
            event: Tk mouse event.
        """
        if self._drag_from is None:
            return
        start_y, start_first = self._drag_from
        height = max(1, self.winfo_height())
        self.command("moveto", start_first + (event.y - start_y) / height)
