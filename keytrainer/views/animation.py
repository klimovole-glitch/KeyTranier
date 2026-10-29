"""Small animation helpers for Tkinter (no extra libraries).

Tkinter has no built-in animations, so every animation is a chain of
``after()`` calls about 60 times per second. :class:`Animator` keeps one
running animation per name: starting a new one with the same name stops the
old one, so fast typing never piles up hundreds of timers.

Durations follow the Figma page «СПЕЦИФИКАЦИЯ»: a key press lasts 0.1 s,
the caret slides in 0.09 s, an error shakes the text for 0.22 s and the
side panel slides out in 0.38 s.
"""

import math
import tkinter as tk
from collections.abc import Callable

FRAME_MS = 16  # ~60 frames per second

# Durations from the specification (milliseconds)
KEY_PRESS_MS = 100
CARET_SLIDE_MS = 90
CARET_ERROR_MS = 260
SHAKE_MS = 220
PANEL_MS = 380
SCREEN_MS = 260
HOVER_MS = 140
FADE_MS = 220
CARET_BLINK_MS = 530


def ease_out(t: float) -> float:
    """Ease-out cubic curve: fast start, soft stop.

    Args:
        t: Progress from 0 to 1.

    Returns:
        Eased progress from 0 to 1.
    """
    t = min(max(t, 0.0), 1.0)
    return 1 - (1 - t) ** 3


def ease_in_out(t: float) -> float:
    """Ease-in-out cubic curve: soft start and soft stop.

    Args:
        t: Progress from 0 to 1.

    Returns:
        Eased progress from 0 to 1.
    """
    t = min(max(t, 0.0), 1.0)
    return 4 * t**3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def linear(t: float) -> float:
    """Linear curve (used for shakes, which have their own shape).

    Args:
        t: Progress from 0 to 1.

    Returns:
        The same progress.
    """
    return min(max(t, 0.0), 1.0)


def shake_offset(t: float, amplitude: float = 7.0, waves: float = 3.0) -> float:
    """Horizontal offset of a decaying shake.

    Args:
        t: Progress from 0 to 1.
        amplitude: Offset of the first swing in pixels.
        waves: Number of full swings.

    Returns:
        Offset in pixels (0 at the start and at the end).
    """
    return amplitude * (1 - t) * math.sin(t * waves * 2 * math.pi)


def lerp(start: float, end: float, t: float) -> float:
    """Linear interpolation between two numbers.

    Args:
        start: Value at ``t = 0``.
        end: Value at ``t = 1``.
        t: Progress from 0 to 1.

    Returns:
        Intermediate value.
    """
    return start + (end - start) * t


def _rgb(color: str) -> tuple[int, int, int]:
    """Convert ``#rrggbb`` to a tuple of integers.

    Args:
        color: Hex color.

    Returns:
        Red, green and blue from 0 to 255.
    """
    color = color.lstrip("#")
    return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)


def mix_colors(start: str, end: str, t: float) -> str:
    """Blend two hex colors.

    Args:
        start: Color at ``t = 0`` (``#rrggbb``).
        end: Color at ``t = 1`` (``#rrggbb``).
        t: Progress from 0 to 1.

    Returns:
        Hex color between ``start`` and ``end``.
    """
    t = min(max(t, 0.0), 1.0)
    channels = (
        round(lerp(a, b, t)) for a, b in zip(_rgb(start), _rgb(end), strict=True)
    )
    return "#" + "".join(f"{c:02x}" for c in channels)


class Animator:
    """Runs named animations on top of ``after()``."""

    def __init__(self, widget: tk.Misc) -> None:
        """Bind the animator to a widget whose ``after()`` is used.

        Args:
            widget: Any widget that lives as long as the animations.
        """
        self._widget = widget
        self._jobs: dict[str, str] = {}

    def is_running(self, name: str) -> bool:
        """Check whether an animation is in progress.

        Args:
            name: Animation name.

        Returns:
            ``True`` while it runs.
        """
        return name in self._jobs

    def cancel(self, name: str) -> None:
        """Stop an animation (the last drawn frame stays on screen).

        Args:
            name: Animation name.
        """
        job = self._jobs.pop(name, None)
        if job is not None:
            try:
                self._widget.after_cancel(job)
            except tk.TclError:
                pass  # the widget is being destroyed

    def cancel_all(self) -> None:
        """Stop every animation of this animator."""
        for name in list(self._jobs):
            self.cancel(name)

    def _alive(self) -> bool:
        """Check that the widget still exists.

        Returns:
            ``False`` after the widget was destroyed.
        """
        try:
            return bool(self._widget.winfo_exists())
        except tk.TclError:
            return False

    def run(
        self,
        name: str,
        duration_ms: int,
        step: Callable[[float], None],
        done: Callable[[], None] | None = None,
        easing: Callable[[float], float] = ease_out,
        delay_ms: int = 0,
        frame_ms: int = FRAME_MS,
    ) -> None:
        """Start an animation, replacing one with the same name.

        Args:
            name: Animation name (one animation per name).
            duration_ms: Length of the animation.
            step: Called on every frame with the eased progress 0..1.
            done: Called once after the last frame.
            easing: Easing curve.
            delay_ms: Pause before the first frame (staggered animations).
            frame_ms: Interval between frames (bigger for heavy redraws).
        """
        self.cancel(name)
        frames = max(1, duration_ms // frame_ms)

        def frame(index: int) -> None:
            if not self._alive():
                self._jobs.pop(name, None)
                return
            step(easing(index / frames))
            if index >= frames:
                self._jobs.pop(name, None)
                if done:
                    done()
                return
            self._jobs[name] = self._widget.after(frame_ms, frame, index + 1)

        if delay_ms > 0:
            self._jobs[name] = self._widget.after(delay_ms, frame, 1)
        else:
            frame(1)

    def repeat(self, name: str, interval_ms: int, tick: Callable[[], None]) -> None:
        """Call ``tick`` every ``interval_ms`` until cancelled (blinking).

        Args:
            name: Animation name.
            interval_ms: Interval between calls.
            tick: Function to call.
        """
        self.cancel(name)

        def again() -> None:
            if not self._alive():
                self._jobs.pop(name, None)
                return
            tick()
            self._jobs[name] = self._widget.after(interval_ms, again)

        self._jobs[name] = self._widget.after(interval_ms, again)

    def later(self, name: str, delay_ms: int, callback: Callable[[], None]) -> None:
        """Call ``callback`` once after a delay (cancellable by name).

        Args:
            name: Animation name.
            delay_ms: Delay.
            callback: Function to call.
        """
        self.cancel(name)

        def fire() -> None:
            self._jobs.pop(name, None)
            if self._alive():
                callback()

        self._jobs[name] = self._widget.after(delay_ms, fire)

    def fade(
        self,
        name: str,
        widget: tk.Misc,
        option: str,
        start: str,
        end: str,
        duration_ms: int = FADE_MS,
        delay_ms: int = 0,
        done: Callable[[], None] | None = None,
    ) -> None:
        """Change a color option of a widget smoothly.

        Args:
            name: Animation name.
            widget: Widget to recolor.
            option: Option name, e.g. ``"fg"``.
            start: First color.
            end: Last color.
            duration_ms: Length of the animation.
            delay_ms: Pause before the start.
            done: Called after the last frame.
        """

        def step(t: float) -> None:
            if widget.winfo_exists():
                widget.configure(**{option: mix_colors(start, end, t)})

        if delay_ms > 0:
            widget.configure(**{option: start})
        self.run(name, duration_ms, step, done, delay_ms=delay_ms)
