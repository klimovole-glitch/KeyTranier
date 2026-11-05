from __future__ import annotations
"""Базовый класс модальных диалогов в стиле главного окна."""

import tkinter as tk

from keytrainer.data.models import Theme
from keytrainer.views.animation import Animator
from keytrainer.views.display import px, set_title_bar_theme
from keytrainer.views.theme import ThemeManager

DIALOG_FADE_MS = 180


class BaseDialog(tk.Toplevel):
    """Модальное окно по центру родительского; Esc закрывает его."""

    def __init__(self, parent: tk.Misc, theme: ThemeManager, title: str) -> None:
        """Создать пустое модальное окно.

        Args:
            parent: Главное окно.
            theme: Менеджер тем.
            title: Заголовок окна.
        """
        super().__init__(parent)
        self.theme = theme
        self.title(title)
        self.resizable(False, False)
        self.transient(parent.winfo_toplevel())
        theme.style(self, bg="bg")
        self.body = theme.frame(self)
        self.body.pack(fill="both", expand=True, padx=px(36), pady=px(30))
        self.bind("<Escape>", lambda _e: self.destroy())

    def show_modal(self) -> None:
        """Центрировать окно, захватить ввод и ждать закрытия."""
        self.update_idletasks()
        parent = self.master.winfo_toplevel()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 3
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        set_title_bar_theme(self, self.theme.theme == Theme.DARK)
        self._fade_in()
        self.grab_set()
        self.focus_set()
        self.wait_window()

    def _fade_in(self) -> None:
        """Сделать появление окна плавным (прозрачность 0 -> 1).

        Некоторые оконные менеджеры Linux не поддерживают прозрачность;
        тогда окно просто появляется сразу.
        """
        try:
            self.attributes("-alpha", 0.0)
        except tk.TclError:
            return
        Animator(self).run(
            "alpha", DIALOG_FADE_MS, lambda t: self.attributes("-alpha", t)
        )
