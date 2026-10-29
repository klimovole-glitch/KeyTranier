"""Dialog for renaming a profile."""

import tkinter as tk
from collections.abc import Callable

from keytrainer.views.dialogs.base_dialog import BaseDialog
from keytrainer.views.theme import ThemeManager
from keytrainer.views.widgets.text_button import TextButton


class ProfileNameDialog(BaseDialog):
    """Asks for a new name; the controller validates it before closing."""

    def __init__(
        self,
        parent: tk.Misc,
        theme: ThemeManager,
        current_name: str,
        apply: Callable[[str], str | None],
    ) -> None:
        """Build the dialog.

        Args:
            parent: Main window.
            theme: Theme manager.
            current_name: Name shown in the entry.
            apply: Saves the name; returns an error text or ``None``.
        """
        super().__init__(parent, theme, "Переименовать профиль")
        self._apply = apply
        theme.label(self.body, "новое имя профиля", role="muted", font="small").pack(
            anchor="w"
        )
        self.entry = tk.Entry(
            self.body, width=30, bd=0, highlightthickness=1, font=theme.fonts["ui"]
        )
        theme.style(
            self.entry,
            bg="surface",
            fg="text",
            insertbackground="text",
            highlightbackground="border",
            highlightcolor="muted",
        )
        self.entry.pack(anchor="w", pady=(6, 4), ipady=4)
        self.entry.insert(0, current_name)
        self.entry.select_range(0, "end")
        self.entry.bind("<Return>", lambda _e: self._accept())
        self.error = theme.label(self.body, "", role="error", font="tiny")
        self.error.pack(anchor="w")
        buttons = theme.frame(self.body)
        buttons.pack(fill="x", pady=(16, 0))
        TextButton(buttons, theme, "отмена", self.destroy).pack(side="right")
        TextButton(buttons, theme, "сохранить", self._accept, role="text").pack(
            side="right", padx=30
        )
        self.entry.focus_set()

    def _accept(self) -> None:
        """Save the name or show why it is not accepted."""
        error = self._apply(self.entry.get())
        if error:
            self.error.configure(text=error)
        else:
            self.destroy()
