from __future__ import annotations
"""Ряд метрик: крупное число с маленькой подписью под ним."""

import tkinter as tk
from collections.abc import Callable

from keytrainer.views.animation import Animator
from keytrainer.views.display import px
from keytrainer.views.theme import ThemeManager

COUNT_MS = 700
COUNT_STAGGER_MS = 70


class MetricsPanel(tk.Frame):
    """Горизонтальный набор ячеек метрик (экран тренировки и карточка результатов)."""

    def __init__(
        self,
        parent: tk.Misc,
        theme: ThemeManager,
        captions: dict[str, str],
        value_font: str = "metric",
        cell_width: int = 12,
    ) -> None:
        """Создать ячейки.

        Args:
            parent: Родительский виджет.
            theme: Менеджер тем.
            captions: Ключ метрики -> подпись («wpm» -> «wpm»).
            value_font: Шрифт значений.
            cell_width: Ширина ячейки в символах.
        """
        super().__init__(parent, bd=0)
        theme.style(self, bg="bg")
        self.animator = Animator(self)
        self._values: dict[str, tk.Label] = {}
        for column, (key, caption) in enumerate(captions.items()):
            cell = theme.frame(self)
            cell.grid(row=0, column=column, padx=px(6))
            value = theme.label(cell, "0", font=value_font, width=cell_width)
            value.pack()
            theme.label(cell, caption, role="muted", font="tiny").pack(pady=px((4, 0)))
            self._values[key] = value

    def set_values(self, values: dict[str, str]) -> None:
        """Показать новые значения.

        Args:
            values: Ключ метрики -> отформатированный текст.
        """
        for key, text in values.items():
            self._values[key].configure(text=text)

    def count_up(self, values: dict[str, tuple[float, Callable[[float], str]]]) -> None:
        """Пустить числа от нуля до их значений (карточка результатов).

        Args:
            values: Ключ метрики -> (конечное число, функция его форматирования).
        """
        for index, (key, (number, formatter)) in enumerate(values.items()):
            label = self._values[key]
            label.configure(text=formatter(0))
            self.animator.run(
                f"count:{key}",
                COUNT_MS,
                lambda t, lb=label, n=number, f=formatter: lb.configure(text=f(n * t)),
                done=lambda lb=label, n=number, f=formatter: lb.configure(text=f(n)),
                delay_ms=index * COUNT_STAGGER_MS,
            )
