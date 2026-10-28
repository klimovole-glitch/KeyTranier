"""Tooltip shown next to the mouse pointer."""

import tkinter as tk

from keytrainer.views.theme import ThemeManager

OFFSET = 16


class Tooltip:
    """Multi-line hint placed inside a container near the pointer."""

    def __init__(self, container: tk.Misc, theme: ThemeManager) -> None:
        """Create a hidden tooltip.

        Args:
            container: Widget the tooltip is placed in (usually the screen).
            theme: Theme manager.
        """
        self._container = container
        self._label = theme.label(
            container,
            "",
            role="text",
            font="small",
            bg="surface",
            justify="left",
            padx=14,
            pady=10,
        )

    def show(self, x_root: int, y_root: int, text: str) -> None:
        """Show the tooltip next to a point of the screen.

        Args:
            x_root: Pointer X in screen coordinates.
            y_root: Pointer Y in screen coordinates.
            text: Tooltip text.
        """
        self._label.configure(text=text)
        x = x_root - self._container.winfo_rootx() + OFFSET
        y = y_root - self._container.winfo_rooty() + OFFSET
        self._label.place(x=x, y=y)
        self._label.lift()

    def hide(self) -> None:
        """Hide the tooltip."""
        self._label.place_forget()
