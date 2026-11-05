from __future__ import annotations
"""Всплывающая подсказка рядом с указателем мыши."""

import tkinter as tk

from keytrainer.views.animation import Animator
from keytrainer.views.display import px
from keytrainer.views.theme import ThemeManager

OFFSET = 16


class Tooltip:
    """Многострочная подсказка внутри контейнера рядом с указателем."""

    def __init__(self, container: tk.Misc, theme: ThemeManager) -> None:
        """Создать скрытую подсказку.

        Args:
            container: Виджет, в который помещается подсказка (обычно экран).
            theme: Менеджер тем.
        """
        self._container = container
        self._theme = theme
        self._visible = False
        self._label = theme.label(
            container,
            "",
            role="text",
            font="small",
            bg="surface",
            justify="left",
            padx=px(14),
            pady=px(10),
        )
        self._animator = Animator(self._label)

    def show(self, x_root: int, y_root: int, text: str) -> None:
        """Показать подсказку рядом с точкой экрана.

        Args:
            x_root: X указателя в экранных координатах.
            y_root: Y указателя в экранных координатах.
            text: Текст подсказки.
        """
        self._label.configure(text=text)
        x = x_root - self._container.winfo_rootx() + px(OFFSET)
        y = y_root - self._container.winfo_rooty() + px(OFFSET)
        self._label.place(x=x, y=y)
        self._label.lift()
        if not self._visible:
            palette = self._theme.palette
            self._animator.fade(
                "show", self._label, "fg", palette.surface, palette.text, 160
            )
        self._visible = True

    def hide(self) -> None:
        """Скрыть подсказку."""
        self._visible = False
        self._label.place_forget()
