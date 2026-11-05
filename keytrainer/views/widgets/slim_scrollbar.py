from __future__ import annotations
"""Тонкая полоса прокрутки в цветах темы.

Стандартная полоса прокрутки в Windows — широкая светло-серая полоса со
стрелками, не подходящая к тёмному дизайну. Эта — скруглённый бегунок на
холсте: он расширяется под мышью и скрывается, когда всё помещается.
"""

import tkinter as tk
from collections.abc import Callable

from keytrainer.views.animation import HOVER_MS, Animator
from keytrainer.views.display import px
from keytrainer.views.theme import ThemeManager

THIN = 4
WIDE = 8


class SlimScrollbar(tk.Canvas):
    """Вертикальная полоса прокрутки, совместимая с ``yscrollcommand``."""

    def __init__(
        self, parent: tk.Misc, theme: ThemeManager, command: Callable[..., None]
    ) -> None:
        """Создать полосу прокрутки.

        Args:
            parent: Родительский виджет.
            theme: Менеджер тем.
            command: Метод ``yview`` прокручиваемого виджета.
        """
        super().__init__(parent, width=px(WIDE + 4), bd=0, highlightthickness=0)
        self.theme = theme
        theme.style(self, bg="bg")
        self.command = command
        self.first, self.last = 0.0, 1.0
        self._width = px(THIN)
        self._drag_from: tuple[int, float] | None = None
        self.animator = Animator(self)
        self.bind("<Configure>", lambda _e: self._draw())
        self.bind("<Enter>", lambda _e: self._resize(px(WIDE)))
        self.bind("<Leave>", lambda _e: self._resize(px(THIN)))
        self.bind("<Button-1>", self._press)
        self.bind("<B1-Motion>", self._drag)
        self.bind("<ButtonRelease-1>", lambda _e: setattr(self, "_drag_from", None))
        theme.on_change(lambda _p: self._draw())

    def set(self, first: str, last: str) -> None:
        """Получить видимую часть от прокручиваемого виджета.

        Args:
            first: Начало видимой части (0..1).
            last: Конец видимой части (0..1).
        """
        self.first, self.last = float(first), float(last)
        self._draw()

    def _draw(self) -> None:
        """Нарисовать бегунок (ничего, если все строки видны)."""
        self.delete("all")
        if self.last - self.first >= 0.999:
            return
        height = self.winfo_height()
        width = self.winfo_width()
        top, bottom = self.first * height, self.last * height
        x = width - px(2) - self._width / 2
        self.create_line(
            x,
            top + self._width / 2,
            x,
            bottom - self._width / 2,
            width=self._width,
            capstyle="round",
            fill=self.theme.palette.dim,
        )

    def _resize(self, width: int) -> None:
        """Плавно расширить или сузить бегунок.

        Args:
            width: Конечная ширина.
        """
        start = self._width

        def step(t: float) -> None:
            self._width = start + (width - start) * t
            self._draw()

        self.animator.run("width", HOVER_MS, step)

    def _press(self, event: tk.Event) -> None:
        """Начать перетаскивание бегунка или перейти к месту щелчка.

        Args:
            event: Событие мыши Tk.
        """
        height = max(1, self.winfo_height())
        position = event.y / height
        if not self.first <= position <= self.last:
            size = self.last - self.first
            self.command("moveto", max(0.0, position - size / 2))
        self._drag_from = (event.y, self.first)

    def _drag(self, event: tk.Event) -> None:
        """Сдвинуть видимую часть за мышью.

        Args:
            event: Событие мыши Tk.
        """
        if self._drag_from is None:
            return
        start_y, start_first = self._drag_from
        height = max(1, self.winfo_height())
        self.command("moveto", start_first + (event.y - start_y) / height)
