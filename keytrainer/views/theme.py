"""Color themes and fonts of the interface (Figma, страница «СПЕЦИФИКАЦИЯ»).

Widgets are not colored directly: they are registered in
:class:`ThemeManager` with *roles* ("bg", "text", "dim"...). When the user
switches the theme, the manager re-colors every registered widget, so the
window does not need to be rebuilt.
"""

import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass
from tkinter import font as tkfont

from keytrainer.data.models import Theme

MONO_FAMILIES = ("JetBrains Mono", "Consolas", "DejaVu Sans Mono", "Courier New")


@dataclass(frozen=True)
class Palette:
    """Colors of one theme (hex strings)."""

    bg: str
    surface: str
    surface_active: str
    border: str
    text: str
    dim: str
    muted: str
    error: str
    success: str
    selection: str
    heat_saturation: float
    heat_value: float
    heat_empty: str


PALETTES = {
    Theme.DARK: Palette(
        bg="#18181a",
        surface="#1f1f22",
        surface_active="#36363a",
        border="#2c2c30",
        text="#e8e8ea",
        dim="#5c5c61",
        muted="#8a8a90",
        error="#e07a6e",
        success="#86b47f",
        selection="#26262a",
        heat_saturation=0.45,
        heat_value=0.42,
        heat_empty="#232326",
    ),
    Theme.LIGHT: Palette(
        bg="#f2f2f4",
        surface="#e8e8eb",
        surface_active="#d2d2d6",
        border="#d9d9dd",
        text="#1d1d1f",
        dim="#a5a5ab",
        muted="#6f6f75",
        error="#c4594d",
        success="#4f8a48",
        selection="#e3e3e7",
        heat_saturation=0.38,
        heat_value=0.86,
        heat_empty="#e2e2e5",
    ),
}

# name -> (size in points at font_size 18, bold)
_FONT_SPECS = {
    "ui": (11, False),
    "small": (9, False),
    "tiny": (8, False),
    "metric": (20, False),
    "metric_big": (34, False),
    "title": (18, False),
    "key": (12, False),
}


def pick_mono_family(root: tk.Misc) -> str:
    """Choose the first installed monospace font.

    Tkinter cannot load a font from a file, so JetBrains Mono must be
    installed in the OS; otherwise a similar system font is used.

    Args:
        root: Any widget (fonts are queried from Tk).

    Returns:
        Font family name.
    """
    installed = set(tkfont.families(root))
    return next((f for f in MONO_FAMILIES if f in installed), "TkFixedFont")


class ThemeManager:
    """Keeps the current palette and fonts and re-colors widgets on change."""

    def __init__(self, root: tk.Misc, theme: Theme, font_size: int) -> None:
        """Create fonts and choose the palette.

        Args:
            root: Main window.
            theme: Initial theme.
            font_size: Size of the exercise text font (profile setting).
        """
        self._root = root
        self.family = pick_mono_family(root)
        self.theme = Theme(theme)
        self.palette = PALETTES[self.theme]
        self.fonts = {
            name: tkfont.Font(root, family=self.family, size=size, weight="normal")
            for name, (size, _bold) in _FONT_SPECS.items()
        }
        self.fonts["text"] = tkfont.Font(root, family=self.family, size=font_size)
        self.fonts["underlined"] = tkfont.Font(
            root, family=self.family, size=_FONT_SPECS["ui"][0], underline=True
        )
        self._styled: list[tuple[tk.Misc, dict[str, str]]] = []
        self._listeners: list[Callable[[Palette], None]] = []

    def style(self, widget: tk.Misc, **roles: str) -> tk.Misc:
        """Color a widget now and every time the theme changes.

        Args:
            widget: Any Tk widget.
            **roles: Widget option -> palette field, e.g. ``bg="bg", fg="text"``.

        Returns:
            The same widget (for chaining).
        """
        self._styled.append((widget, roles))
        self._apply(widget, roles)
        return widget

    def on_change(self, callback: Callable[[Palette], None]) -> None:
        """Subscribe to theme changes (for canvases and charts).

        Args:
            callback: Function receiving the new palette.
        """
        self._listeners.append(callback)

    def set_theme(self, theme: Theme, font_size: int) -> None:
        """Switch the palette and the exercise font size.

        Args:
            theme: New theme.
            font_size: New size of the exercise text.
        """
        self.theme = Theme(theme)
        self.palette = PALETTES[self.theme]
        self.fonts["text"].configure(size=font_size)
        self._root.configure(bg=self.palette.bg)
        alive = []
        for widget, roles in self._styled:
            if widget.winfo_exists():
                self._apply(widget, roles)
                alive.append((widget, roles))
        self._styled = alive
        for callback in self._listeners:
            callback(self.palette)

    def _apply(self, widget: tk.Misc, roles: dict[str, str]) -> None:
        """Configure widget options from the palette.

        Args:
            widget: Widget to color.
            roles: Option -> palette field.
        """
        widget.configure(
            **{option: getattr(self.palette, role) for option, role in roles.items()}
        )

    # -------------------------------------------------- widget factories
    def frame(self, parent: tk.Misc, role: str = "bg", **options) -> tk.Frame:
        """Create a frame filled with a palette color.

        Args:
            parent: Parent widget.
            role: Palette field for the background.
            **options: Other Frame options.

        Returns:
            New frame.
        """
        frame = tk.Frame(parent, bd=0, highlightthickness=0, **options)
        return self.style(frame, bg=role)

    def label(
        self,
        parent: tk.Misc,
        text: str = "",
        role: str = "text",
        font: str = "ui",
        bg: str = "bg",
        **options,
    ) -> tk.Label:
        """Create a themed label.

        Args:
            parent: Parent widget.
            text: Caption.
            role: Palette field for the text color.
            font: Name of a font from :attr:`fonts`.
            bg: Palette field for the background.
            **options: Other Label options.

        Returns:
            New label.
        """
        options = {"bd": 0, "padx": 0, "pady": 0, **options}
        label = tk.Label(parent, text=text, font=self.fonts[font], **options)
        return self.style(label, fg=role, bg=bg)
