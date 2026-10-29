"""Darkening of the window under the side menu and confirmations (Figma 02, 09c).

Tk widgets cannot be semi-transparent, but a separate borderless window can
(``-alpha`` on Windows). The layer is such a window: black, with the
transparency changing smoothly, placed exactly over a part of the main
window and moving together with it. On systems without transparency the
layer is simply not shown.
"""

import sys
import tkinter as tk
from collections.abc import Callable

from keytrainer.views.animation import FADE_MS, Animator

DIM_ALPHA = 0.55
Rect = tuple[int, int, int, int]


def transparency_supported() -> bool:
    """Whether windows can be semi-transparent here.

    Returns:
        ``True`` on Windows.
    """
    return sys.platform == "win32"


class DimLayer:
    """Semi-transparent black window over a rectangle of the main window."""

    def __init__(
        self,
        root: tk.Tk,
        area: Callable[[], Rect],
        on_click: Callable[[], None] | None = None,
        on_key: Callable[[tk.Event], object] | None = None,
        alpha: float = DIM_ALPHA,
    ) -> None:
        """Prepare the layer (it is created by :meth:`show`).

        Args:
            root: Main window.
            area: Returns ``x, y, width, height`` of the darkened part,
                relative to the main window.
            on_click: Called when the darkened part is clicked.
            on_key: Receives key presses while the layer has the focus.
            alpha: Final opacity.
        """
        self.root = root
        self.area = area
        self.on_click = on_click
        self.on_key = on_key
        self.alpha = alpha
        self.window: tk.Toplevel | None = None
        self._current = 0.0
        self._animator = Animator(root)
        self._bind_id: str | None = None

    def show(self) -> None:
        """Create the layer and fade it in."""
        if not transparency_supported():
            return
        if self.window is None or not self.window.winfo_exists():
            window = tk.Toplevel(self.root, bg="#000000", bd=0)
            window.overrideredirect(True)
            window.transient(self.root)
            window.attributes("-alpha", 0.0)
            window.bind("<Button-1>", lambda _e: self.on_click and self.on_click())
            if self.on_key:
                window.bind("<KeyPress>", self.on_key)
            self.window = window
            self._current = 0.0
            self._bind_id = self.root.bind("<Configure>", self._follow, add="+")
        self.place()
        self._fade(self.alpha)

    def place(self) -> None:
        """Put the layer over its part of the main window."""
        if self.window is None:
            return
        x, y, width, height = self.area()
        width, height = max(1, width), max(1, height)
        left = self.root.winfo_rootx() + x
        top = self.root.winfo_rooty() + y
        self.window.geometry(f"{width}x{height}+{left}+{top}")
        self.window.lift(self.root)

    def _follow(self, _event: tk.Event) -> None:
        """Move the layer when the main window moves or changes size.

        Args:
            _event: Tk configure event.
        """
        if self.window is not None and self.window.winfo_exists():
            self.place()

    def hide(self, duration_ms: int = FADE_MS) -> None:
        """Fade the layer out and destroy it.

        Args:
            duration_ms: Length of the animation.
        """
        if self.window is None:
            return
        self._fade(0.0, duration_ms, done=self._destroy)

    def _destroy(self) -> None:
        """Remove the window of the layer."""
        if self._bind_id is not None:
            self.root.unbind("<Configure>", self._bind_id)
            self._bind_id = None
        if self.window is not None and self.window.winfo_exists():
            self.window.destroy()
        self.window = None

    def _fade(self, target: float, duration_ms: int = FADE_MS, done=None) -> None:
        """Change the opacity smoothly.

        Args:
            target: Final opacity.
            duration_ms: Length of the animation.
            done: Called at the end.
        """
        start = self._current
        window = self.window

        def step(t: float) -> None:
            self._current = start + (target - start) * t
            if window is not None and window.winfo_exists():
                window.attributes("-alpha", self._current)

        self._animator.run(f"dim{id(self)}", duration_ms, step, done)
