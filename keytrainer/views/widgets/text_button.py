from __future__ import annotations
"""Текстовые кнопки минималистичного дизайна (Figma, страница «COMPONENTS»).

В макетах нет кнопок с рамками: действие — это слово, которое светлеет при
наведении, выбранный вариант подчёркнут, недоступный — приглушён.
Цвет текста меняется плавно, а не скачком.
"""

import tkinter as tk
from collections.abc import Callable

from keytrainer.views.animation import HOVER_MS, Animator
from keytrainer.views.display import px
from keytrainer.views.theme import Palette, ThemeManager


class TextButton(tk.Label):
    """Нажимаемая подпись с обычным, наведённым, выбранным и отключённым состояниями."""

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
        """Создать кнопку.

        Args:
            parent: Родительский виджет.
            theme: Менеджер тем.
            text: Подпись.
            command: Вызывается по щелчку.
            role: Поле палитры обычного цвета текста.
            hover_role: Поле палитры цвета при наведении и выборе.
            font: Имя шрифта.
            bg: Поле палитры фона.
        """
        super().__init__(
            parent, text=text, bd=0, padx=px(4), pady=px(2), cursor="hand2"
        )
        self._theme = theme
        self._command = command
        self._role = role
        self._hover_role = hover_role
        self._font = font
        self._bg = bg
        self._hover = False
        self.selected = False
        self.enabled = True
        self._animator = Animator(self)
        theme.style(self, bg=bg)  # фон следует за плавной сменой темы
        self.bind("<Enter>", lambda _e: self._set_hover(True))
        self.bind("<Leave>", lambda _e: self._set_hover(False))
        self.bind("<Button-1>", self._click)
        theme.on_change(lambda _p: self.refresh())
        self.refresh()

    def _set_hover(self, value: bool) -> None:
        """Запомнить состояние наведения и перерисовать.

        Args:
            value: ``True``, пока мышь над кнопкой.
        """
        self._hover = value
        self.refresh(animate=True)

    def _click(self, _event: tk.Event) -> None:
        """Выполнить команду, если кнопка включена.

        Args:
            _event: Событие Tk (не используется).
        """
        if self.enabled and self._command:
            self._command()

    def set_command(self, command: Callable[[], None]) -> None:
        """Заменить обработчик щелчка.

        Args:
            command: Новый обработчик.
        """
        self._command = command

    def set_state(
        self, enabled: bool | None = None, selected: bool | None = None
    ) -> None:
        """Изменить доступность и выбор.

        Args:
            enabled: Новая доступность, ``None`` оставляет текущую.
            selected: Новый выбор, ``None`` оставляет текущий.
        """
        if enabled is not None:
            self.enabled = enabled
        if selected is not None:
            self.selected = selected
        self.refresh(animate=True)

    def target_color(self) -> str:
        """Цвет текста для текущего состояния.

        Returns:
            Шестнадцатеричный цвет.
        """
        palette = self._theme.palette
        if not self.enabled:
            return palette.dim
        if self._hover or self.selected:
            return getattr(palette, self._hover_role)
        return getattr(palette, self._role)

    def fade_in(self, delay_ms: int = 0, duration_ms: int = 260) -> None:
        """Проявиться из цвета фона (пункты меню, кнопки результата).

        Args:
            delay_ms: Пауза перед началом (списки со сдвигом).
            duration_ms: Длительность анимации.
        """
        start = getattr(self._theme.palette, self._bg)
        self._animator.fade(
            "color", self, "fg", start, self.target_color(), duration_ms, delay_ms
        )

    def refresh(self, _palette: Palette | None = None, animate: bool = False) -> None:
        """Перерисовать по состоянию и текущей палитре.

        Args:
            _palette: Игнорируется; текущая палитра берётся у менеджера.
            animate: Плавно менять цвет текста (наведение, выбор).
        """
        if not self.winfo_exists():
            return  # кнопка уничтожена (меню пересобрано)
        palette = self._theme.palette
        color = self.target_color()
        font = "underlined" if self.selected and self._font == "ui" else self._font
        self.configure(
            bg=getattr(palette, self._bg),
            font=self._theme.fonts[font],
            cursor="hand2" if self.enabled else "arrow",
        )
        if animate:
            current = self.cget("fg")
            if current.startswith("#") and len(current) == 7:
                self._animator.fade("color", self, "fg", current, color, HOVER_MS)
                return
        self._animator.cancel("color")
        self.configure(fg=color)
