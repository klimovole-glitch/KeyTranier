"""Confirmation over the darkened window (Figma 09c «История — удаление записи»).

The window is darkened by :class:`DimLayer`; above it a borderless window
with a "transparent" background color shows only the question and the two
actions, so they seem to lie right on the darkened screen. Enter confirms,
Esc cancels. Where transparency is not available, the question is shown on
an ordinary dark panel in the middle of the window.
"""

import tkinter as tk

from keytrainer.views.animation import Animator, mix_colors
from keytrainer.views.display import px
from keytrainer.views.theme import ThemeManager
from keytrainer.views.widgets.dim_layer import (
    DIM_ALPHA,
    DimLayer,
    transparency_supported,
)

FADE_IN_MS = 200
TEXT = "#e6e6ea"
MUTED = "#9a9aa4"
ERROR = "#c97b7b"


class ConfirmOverlay:
    """Question with "отмена" and a dangerous action over the dimmed window."""

    def __init__(
        self,
        root: tk.Misc,
        theme: ThemeManager,
        question: str,
        details: str = "",
        action: str = "удалить",
    ) -> None:
        """Build the overlay (it is shown by :meth:`ask`).

        Args:
            root: Main window.
            theme: Theme manager (fonts and background).
            question: Main line, e.g. "удалить запись от 19.10.2026 18:30?".
            details: Smaller line under the question.
            action: Caption of the confirming action.
        """
        self.root = root.winfo_toplevel()
        self.theme = theme
        self.question = question
        self.details = details
        self.action = action
        self.confirmed = False
        self.layer = DimLayer(self.root, self._client_area)
        self.panel: tk.Toplevel | None = None
        self._geometry = ""

    def _client_area(self) -> tuple[int, int, int, int]:
        """The whole main window.

        Returns:
            ``x, y, width, height`` relative to the main window.
        """
        return 0, 0, self.root.winfo_width(), self.root.winfo_height()

    def ask(self) -> bool:
        """Show the question and wait for the answer.

        Returns:
            ``True`` if the action was confirmed.
        """
        transparent = transparency_supported()
        key = mix_colors(self.theme.palette.bg, "#000000", DIM_ALPHA)
        bg = key if transparent else self.theme.palette.surface
        panel = tk.Toplevel(self.root, bg=bg, bd=0)
        panel.overrideredirect(True)
        panel.transient(self.root)
        self.panel = panel
        if transparent:
            panel.attributes("-transparentcolor", key)
            panel.attributes("-alpha", 0.0)
        body = tk.Frame(panel, bg=bg, bd=0)
        body.place(relx=0.5, rely=0.45, anchor="center")
        fonts = self.theme.fonts
        tk.Label(body, text=self.question, bg=bg, fg=TEXT, font=fonts["confirm"]).pack()
        if self.details:
            tk.Label(body, text=self.details, bg=bg, fg=MUTED, font=fonts["ui"]).pack(
                pady=px((10, 0))
            )
        row = tk.Frame(body, bg=bg, bd=0)
        row.pack(pady=px((34, 0)))
        self._button(row, "отмена", MUTED, TEXT, self._cancel, bg).pack(
            side="left", padx=px(40)
        )
        self._button(row, self.action, ERROR, "#e09a9a", self._confirm, bg).pack(
            side="left", padx=px(40)
        )
        panel.bind("<Escape>", lambda _e: self._cancel())
        panel.bind("<Return>", lambda _e: self._confirm())
        self._place_panel()
        panel.lift()
        follow = self.root.bind(
            "<Configure>",
            lambda e: e.widget is self.root and self._place_panel(),
            add="+",
        )
        self.layer.show()
        if transparent:
            Animator(panel).run(
                "alpha", FADE_IN_MS, lambda t: panel.attributes("-alpha", t)
            )
        panel.grab_set()
        panel.focus_force()
        self.root.wait_window(panel)
        self.root.unbind("<Configure>", follow)
        self.layer.hide(140)
        return self.confirmed

    def _button(self, parent, text, color, hover, command, bg) -> tk.Label:
        """Create a text action that brightens under the mouse.

        Args:
            parent: Container.
            text: Caption.
            color: Normal color.
            hover: Color under the mouse.
            command: Called on click.
            bg: Background color.

        Returns:
            Label used as a button.
        """
        label = tk.Label(
            parent,
            text=text,
            bg=bg,
            fg=color,
            font=self.theme.fonts["ui"],
            cursor="hand2",
            padx=px(4),
        )
        label.bind("<Enter>", lambda _e: label.configure(fg=hover))
        label.bind("<Leave>", lambda _e: label.configure(fg=color))
        label.bind("<Button-1>", lambda _e: command())
        return label

    def _place_panel(self) -> None:
        """Cover the main window with the panel."""
        panel = self.panel
        if panel is None or not panel.winfo_exists():
            return
        if transparency_supported():
            width, height = self.root.winfo_width(), self.root.winfo_height()
            x, y = self.root.winfo_rootx(), self.root.winfo_rooty()
        else:
            width, height = px(640), px(240)
            x = self.root.winfo_rootx() + (self.root.winfo_width() - width) // 2
            y = self.root.winfo_rooty() + (self.root.winfo_height() - height) // 3
        geometry = f"{width}x{height}+{x}+{y}"
        if geometry != self._geometry:  # see DimLayer.place: avoid a loop
            self._geometry = geometry
            panel.geometry(geometry)

    def _confirm(self) -> None:
        """Close with "yes"."""
        self.confirmed = True
        self._close()

    def _cancel(self) -> None:
        """Close with "no"."""
        self._close()

    def _close(self) -> None:
        """Destroy the panel (the dim layer fades out after it)."""
        if self.panel is not None and self.panel.winfo_exists():
            self.panel.grab_release()
            self.panel.destroy()
        self.root.focus_force()  # keys must go back to the main window


def ask_confirm(
    parent: tk.Misc,
    theme: ThemeManager,
    question: str,
    details: str = "",
    action: str = "удалить",
) -> bool:
    """Show the confirmation over the darkened window and wait for the answer.

    Args:
        parent: Any widget of the main window.
        theme: Theme manager.
        question: Main line.
        details: Smaller explanation.
        action: Caption of the confirming action.

    Returns:
        ``True`` if the user confirmed.
    """
    return ConfirmOverlay(parent, theme, question, details, action).ask()
