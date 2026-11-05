from __future__ import annotations
"""Затемнение окна под боковым меню и подтверждениями (Figma 02, 09c).

Виджеты Tk не могут быть полупрозрачными, а отдельное безрамочное окно —
может (``-alpha`` в Windows). Слой — это такое окно: чёрное, с плавно
меняющейся прозрачностью, расположенное точно над частью главного окна и
двигающееся вместе с ним. В системах без прозрачности слой просто не
показывается.
"""

import sys
import tkinter as tk
from collections.abc import Callable

from keytrainer.views.animation import FADE_MS, Animator

DIM_ALPHA = 0.55
Rect = tuple[int, int, int, int]


def transparency_supported() -> bool:
    """Могут ли окна быть полупрозрачными здесь.

    Returns:
        ``True`` в Windows.
    """
    return sys.platform == "win32"


class DimLayer:
    """Полупрозрачное чёрное окно поверх прямоугольника главного окна."""

    def __init__(
        self,
        root: tk.Tk,
        area: Callable[[], Rect],
        on_click: Callable[[], None] | None = None,
        on_key: Callable[[tk.Event], object] | None = None,
        alpha: float = DIM_ALPHA,
    ) -> None:
        """Подготовить слой (создаётся в :meth:`show`).

        Args:
            root: Главное окно.
            area: Возвращает ``x, y, width, height`` затемняемой части
                относительно главного окна.
            on_click: Вызывается при щелчке по затемнённой части.
            on_key: Получает нажатия клавиш, пока у слоя есть фокус.
            alpha: Конечная непрозрачность.
        """
        self.root = root
        self.area = area
        self.on_click = on_click
        self.on_key = on_key
        self.alpha = alpha
        self.window: tk.Toplevel | None = None
        self._current = 0.0
        self._animator = Animator(root)
        self._bind_id: str | None = None
        self._geometry = ""

    def show(self) -> None:
        """Создать слой и плавно показать его."""
        if not transparency_supported():
            return
        if self.window is None or not self.window.winfo_exists():
            window = tk.Toplevel(self.root, bg="#000000", bd=0)
            window.overrideredirect(True)
            window.transient(self.root)
            window.attributes("-alpha", 0.0)
            window.bind("<Button-1>", lambda _e: self.on_click and self.on_click())
            if self.on_key:
                window.bind("<KeyPress>", self.on_key)
            self.window = window
            self._current = 0.0
            self._geometry = ""
            self._bind_id = self.root.bind("<Configure>", self._follow, add="+")
        self.place()
        self.window.lift(self.root)
        self._fade(self.alpha)

    def place(self) -> None:
        """Поставить слой поверх его части главного окна."""
        if self.window is None:
            return
        x, y, width, height = self.area()
        width, height = max(1, width), max(1, height)
        left = self.root.winfo_rootx() + x
        top = self.root.winfo_rooty() + y
        geometry = f"{width}x{height}+{left}+{top}"
        # Применяется только реальное изменение: перемещение или поднятие окна заставляет
        # Windows снова отправить <Configure> главному окну, а бесконечная реакция
        # на это подвешивала программу.
        if geometry != self._geometry:
            self._geometry = geometry
            self.window.geometry(geometry)

    def _follow(self, event: tk.Event) -> None:
        """Переместить слой, когда главное окно двигается или меняет размер.

        Привязка к главному окну получает и <Configure> каждого вложенного
        виджета; они игнорируются.

        Args:
            event: Событие конфигурации Tk.
        """
        if event.widget is not self.root:
            return
        if self.window is not None and self.window.winfo_exists():
            self.place()

    def hide(self, duration_ms: int = FADE_MS) -> None:
        """Плавно скрыть слой и уничтожить его.

        Args:
            duration_ms: Длительность анимации.
        """
        if self.window is None:
            return
        self._fade(0.0, duration_ms, done=self._destroy)

    def _destroy(self) -> None:
        """Удалить окно слоя."""
        if self._bind_id is not None:
            self.root.unbind("<Configure>", self._bind_id)
            self._bind_id = None
        if self.window is not None and self.window.winfo_exists():
            self.window.destroy()
        self.window = None
        # щелчок пришёлся на слой, который был активным окном; вернуть клавиатуру,
        # иначе Windows активирует другую программу, и набор прекратится
        self.root.focus_force()

    def _fade(self, target: float, duration_ms: int = FADE_MS, done=None) -> None:
        """Плавно изменить непрозрачность.

        Args:
            target: Конечная непрозрачность.
            duration_ms: Длительность анимации.
            done: Вызывается в конце.
        """
        start = self._current
        window = self.window

        def step(t: float) -> None:
            self._current = start + (target - start) * t
            if window is not None and window.winfo_exists():
                window.attributes("-alpha", self._current)

        self._animator.run(f"dim{id(self)}", duration_ms, step, done)
