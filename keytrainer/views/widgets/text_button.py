"""Text buttons of the minimalist design (Figma, страница «COMPONENTS»).

The mockups have no framed buttons: an action is a word that brightens on
hover, a chosen option is underlined, an unavailable one is dimmed.
"""

import tkinter as tk
from collections.abc import Callable

from keytrainer.views.theme import Palette, ThemeManager


class TextButton(tk.Label):
    """Clickable caption with normal, hover, selected and disabled states."""

    def __init__(
        self,
        parent: tk.Misc,
        theme: ThemeManager,
        text: str,
        command: Callable[[], None] | None = None,
        role: str = "muted",
        hover_role: str = "text",
        font: str = "ui",
        bg: str = "bg",
    ) -> None:
        """Create the button.

        Args:
            parent: Parent widget.
            theme: Theme manager.
            text: Caption.
            command: Called on click.
            role: Palette field of the normal text color.
            hover_role: Palette field of the hover and selected color.
            font: Font name.
            bg: Palette field of the background.
        """
        super().__init__(parent, text=text, bd=0, padx=4, pady=2, cursor="hand2")
        self._theme = theme
        self._command = command
        self._role = role
        self._hover_role = hover_role
        self._font = font
        self._bg = bg
        self._hover = False
        self.selected = False
        self.enabled = True
        self.bind("<Enter>", lambda _e: self._set_hover(True))
        self.bind("<Leave>", lambda _e: self._set_hover(False))
        self.bind("<Button-1>", self._click)
        theme.on_change(lambda _p: self.refresh())
        self.refresh()

    def _set_hover(self, value: bool) -> None:
        """Remember the hover state and repaint.

        Args:
            value: ``True`` while the mouse is over the button.
        """
        self._hover = value
        self.refresh()

    def _click(self, _event: tk.Event) -> None:
        """Run the command if the button is enabled.

        Args:
            _event: Tk event (unused).
        """
        if self.enabled and self._command:
            self._command()

    def set_command(self, command: Callable[[], None]) -> None:
        """Replace the click handler.

        Args:
            command: New handler.
        """
        self._command = command

    def set_state(
        self, enabled: bool | None = None, selected: bool | None = None
    ) -> None:
        """Change availability and selection.

        Args:
            enabled: New availability, ``None`` keeps the current one.
            selected: New selection, ``None`` keeps the current one.
        """
        if enabled is not None:
            self.enabled = enabled
        if selected is not None:
            self.selected = selected
        self.refresh()

    def refresh(self, _palette: Palette | None = None) -> None:
        """Repaint according to the state and the current palette.

        Args:
            _palette: Ignored; the current palette is taken from the manager.
        """
        if not self.winfo_exists():
            return  # the button was destroyed (menu rebuilt)
        palette = self._theme.palette
        if not self.enabled:
            color = palette.dim
        elif self._hover or self.selected:
            color = getattr(palette, self._hover_role)
        else:
            color = getattr(palette, self._role)
        font = "underlined" if self.selected and self._font == "ui" else self._font
        self.configure(
            fg=color,
            bg=getattr(palette, self._bg),
            font=self._theme.fonts[font],
            cursor="hand2" if self.enabled else "arrow",
        )
