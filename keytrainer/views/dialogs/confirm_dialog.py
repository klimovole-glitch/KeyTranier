"""Confirmation in the style of the program instead of the system message box."""

import tkinter as tk

from keytrainer.views.dialogs.base_dialog import BaseDialog
from keytrainer.views.display import px
from keytrainer.views.theme import ThemeManager
from keytrainer.views.widgets.text_button import TextButton


class ConfirmDialog(BaseDialog):
    """Question with a dangerous action and "отмена" (Enter / Esc)."""

    def __init__(
        self,
        parent: tk.Misc,
        theme: ThemeManager,
        title: str,
        question: str,
        action: str = "удалить",
    ) -> None:
        """Build the dialog.

        Args:
            parent: Main window.
            theme: Theme manager.
            title: Window title.
            question: Question text.
            action: Caption of the confirming button.
        """
        super().__init__(parent, theme, title)
        self.confirmed = False
        theme.label(self.body, title.lower(), role="muted", font="small").pack(
            anchor="w"
        )
        theme.label(
            self.body, question, font="title", justify="left", wraplength=px(420)
        ).pack(anchor="w", pady=px((10, 26)))
        buttons = theme.frame(self.body)
        buttons.pack(fill="x")
        TextButton(buttons, theme, "отмена", self.destroy).pack(side="right")
        TextButton(
            buttons, theme, action, self._confirm, role="error", hover_role="error"
        ).pack(side="right", padx=px(30))
        self.bind("<Return>", lambda _e: self._confirm())

    def _confirm(self) -> None:
        """Remember the answer and close."""
        self.confirmed = True
        self.destroy()


def ask_confirm(
    parent: tk.Misc, theme: ThemeManager, title: str, question: str
) -> bool:
    """Show the confirmation and wait for the answer.

    Args:
        parent: Main window.
        theme: Theme manager.
        title: Window title.
        question: Question text.

    Returns:
        ``True`` if the user confirmed.
    """
    dialog = ConfirmDialog(parent, theme, title, question)
    dialog.show_modal()
    return dialog.confirmed
