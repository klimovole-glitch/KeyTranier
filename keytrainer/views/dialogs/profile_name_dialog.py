from __future__ import annotations
"""Диалог переименования профиля."""

import tkinter as tk
from collections.abc import Callable

from keytrainer.views.dialogs.base_dialog import BaseDialog
from keytrainer.views.display import px
from keytrainer.views.theme import ThemeManager
from keytrainer.views.widgets.text_button import TextButton


class ProfileNameDialog(BaseDialog):
    """Запрашивает новое имя; контроллер проверяет его перед закрытием."""

    def __init__(
        self,
        parent: tk.Misc,
        theme: ThemeManager,
        current_name: str,
        apply: Callable[[str], str | None],
    ) -> None:
        """Построить диалог.

        Args:
            parent: Главное окно.
            theme: Менеджер тем.
            current_name: Имя, показанное в поле ввода.
            apply: Сохраняет имя; возвращает текст ошибки или ``None``.
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
        self.entry.pack(anchor="w", pady=px((6, 4)), ipady=px(4))
        self.entry.insert(0, current_name)
        self.entry.select_range(0, "end")
        self.entry.bind("<Return>", lambda _e: self._accept())
        self.error = theme.label(self.body, "", role="error", font="tiny")
        self.error.pack(anchor="w")
        buttons = theme.frame(self.body)
        buttons.pack(fill="x", pady=px((16, 0)))
        TextButton(buttons, theme, "отмена", self.destroy).pack(side="right")
        TextButton(buttons, theme, "сохранить", self._accept, role="text").pack(
            side="right", padx=px(30)
        )
        self.entry.focus_set()

    def _accept(self) -> None:
        """Сохранить имя или показать, почему оно не принято."""
        error = self._apply(self.entry.get())
        if error:
            self.error.configure(text=error)
        else:
            self.destroy()
