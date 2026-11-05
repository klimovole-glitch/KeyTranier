from __future__ import annotations
"""Тонкий ползунок с круглой ручкой (Figma: «Настройки», размер шрифта).

``ttk.Scale`` в Windows выглядит как серая коробка и не анимируется, поэтому
ползунок рисуется на Canvas: тонкая линия, закрашенная часть до ручки и
ручка, которая растёт под мышью и плавно двигается.
"""

import tkinter as tk
from collections.abc import Callable

from keytrainer.views.animation import HOVER_MS, Animator
from keytrainer.views.display import px
from keytrainer.views.theme import ThemeManager

KNOB_RADIUS = 6
KNOB_HOVER_RADIUS = 8
MOVE_MS = 160
HEIGHT = 40
LINE_Y = 14


class Slider(tk.Canvas):
    """Целочисленный ползунок от ``low`` до ``high``."""

    def __init__(
        self,
        parent: tk.Misc,
        theme: ThemeManager,
        low: int,
        high: int,
        command: Callable[[int], None],
        length: int = 260,
    ) -> None:
        """Создать ползунок.

        Args:
            parent: Родительский виджет.
            theme: Менеджер тем.
            low: Минимальное значение.
            high: Максимальное значение.
            command: Вызывается с новым значением, когда пользователь двигает ручку.
            length: Ширина в пикселях.
        """
        length = px(length)
        super().__init__(
            parent, width=length, height=px(HEIGHT), bd=0, highlightthickness=0
        )
        self.theme = theme
        theme.style(self, bg="bg")
        self.low, self.high = low, high
        self.command = command
        self.length = length
        self.value = low
        self._x = self._x_of(low)
        self._radius = px(KNOB_RADIUS)
        self.animator = Animator(self)
        self.bind("<Button-1>", self._drag)
        self.bind("<B1-Motion>", self._drag)
        self.bind("<Enter>", lambda _e: self._grow(px(KNOB_HOVER_RADIUS)))
        self.bind("<Leave>", lambda _e: self._grow(px(KNOB_RADIUS)))
        theme.on_change(lambda _p: self._draw())
        self._draw()

    @property
    def _left(self) -> int:
        """X начала линии (место для ручки)."""
        return px(KNOB_HOVER_RADIUS) + 1

    @property
    def _right(self) -> int:
        """X конца линии."""
        return self.length - px(KNOB_HOVER_RADIUS) - 1

    def _x_of(self, value: int) -> float:
        """Преобразовать значение в положение ручки.

        Args:
            value: Значение ползунка.

        Returns:
            Координата X.
        """
        share = (value - self.low) / (self.high - self.low)
        return self._left + share * (self._right - self._left)

    def _value_of(self, x: float) -> int:
        """Преобразовать положение в ближайшее значение.

        Args:
            x: Координата X.

        Returns:
            Значение между ``low`` и ``high``.
        """
        share = (x - self._left) / (self._right - self._left)
        value = round(self.low + share * (self.high - self.low))
        return min(max(value, self.low), self.high)

    def _draw(self) -> None:
        """Нарисовать линию, закрашенную часть, ручку и крайние значения."""
        palette = self.theme.palette
        line_y = px(LINE_Y)
        self.delete("all")
        self.create_line(
            self._left, line_y, self._right, line_y, fill=palette.border, width=px(2)
        )
        self.create_line(
            self._left, line_y, self._x, line_y, fill=palette.muted, width=px(2)
        )
        r = self._radius
        self.create_oval(
            self._x - r,
            line_y - r,
            self._x + r,
            line_y + r,
            fill=palette.text,
            outline="",
        )
        font = self.theme.fonts["tiny"]
        self.create_text(
            self._left, px(HEIGHT - 6), text=str(self.low), fill=palette.dim, font=font
        )
        self.create_text(
            self._right,
            px(HEIGHT - 6),
            text=str(self.high),
            fill=palette.dim,
            font=font,
        )

    def _grow(self, radius: int) -> None:
        """Плавно изменить размер ручки (наведение).

        Args:
            radius: Конечный радиус.
        """
        start = self._radius

        def step(t: float) -> None:
            self._radius = start + (radius - start) * t
            self._draw()

        self.animator.run("grow", HOVER_MS, step)

    def _drag(self, event: tk.Event) -> None:
        """Переместить ручку за мышью и сообщить новое значение.

        Args:
            event: Событие мыши Tk.
        """
        value = self._value_of(event.x)
        self.animator.cancel("move")
        self._x = self._x_of(value)
        self._draw()
        if value != self.value:
            self.value = value
            self.command(value)

    def get(self) -> int:
        """Текущее значение.

        Returns:
            Значение.
        """
        return self.value

    def set(self, value: int) -> None:
        """Плавно переместить ручку к значению (без вызова команды).

        Args:
            value: Новое значение.
        """
        self.value = min(max(int(value), self.low), self.high)
        start, end = self._x, self._x_of(self.value)

        def step(t: float) -> None:
            self._x = start + (end - start) * t
            self._draw()

        self.animator.run("move", MOVE_MS, step)
