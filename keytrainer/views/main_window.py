from __future__ import annotations
"""Единое главное окно: экраны, боковое меню и строка состояния (ТЗ, п. 4.1.6).

Навигация следует прототипу Figma: боковая панель (300 px) выезжает за
0,38 с по Esc, по щелчку или просто при подведении мыши к левому краю
(зона 28 px с тонкой полосой); она закрывает содержимое, не сдвигая его.
Новый экран при появлении слегка выезжает вверх. F1 открывает «О программе».
"""

import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from keytrainer.views.animation import PANEL_MS, SCREEN_MS, Animator
from keytrainer.views.display import px
from keytrainer.views.theme import ThemeManager
from keytrainer.views.widgets.dim_layer import DimLayer
from keytrainer.views.widgets.dropdown import Dropdown
from keytrainer.views.widgets.text_button import TextButton

MENU_WIDTH = 220
HOVER_ZONE = 28
HOVER_DELAY_MS = 140
SCREEN_SHIFT = 22


class ScreenController(Protocol):
    """Что главное окно ожидает от контроллера экрана."""

    def on_show(self) -> None:
        """Вызывается, когда экран становится видимым."""

    def on_hide(self) -> None:
        """Вызывается, когда показан другой экран."""

    def handle_key(self, event: tk.Event) -> bool:
        """Обработать нажатие клавиши; вернуть ``True``, если оно обработано."""

    def handle_key_release(self, event: tk.Event) -> None:
        """Обработать отпускание клавиши."""

    def status_hint(self) -> str:
        """Вернуть подсказки горячих клавиш для правой части строки состояния."""


@dataclass
class Screen:
    """Зарегистрированный экран."""

    name: str
    title: str
    frame: tk.Frame
    controller: ScreenController | None
    in_menu: bool


class MainWindow:
    """Владеет компоновкой корневого окна и переключает экраны."""

    def __init__(self, root: tk.Tk, theme: ThemeManager) -> None:
        """Создать компоновку: строка меню, область содержимого, строка состояния, боковое меню.

        Args:
            root: Корневое окно Tk.
            theme: Менеджер тем.
        """
        self.root = root
        self.theme = theme
        root.configure(bg=theme.palette.bg)
        self.screens: dict[str, Screen] = {}
        self.current: Screen | None = None
        self.on_about: Callable[[], None] | None = None

        self.animator = Animator(root)

        status = theme.frame(root)
        status.pack(side="bottom", fill="x", padx=px(40), pady=px((0, 18)))
        self.status_left = theme.label(status, "", role="muted", font="tiny")
        self.status_left.pack(side="left")
        self.status_right = theme.label(status, "", role="muted", font="tiny")
        self.status_right.pack(side="right")

        self.content = theme.frame(root)
        self.content.pack(side="top", fill="both", expand=True, padx=px((30, 0)))

        zone = theme.frame(root, width=px(HOVER_ZONE), cursor="hand2")
        zone.place(x=0, y=0, relheight=1, width=px(HOVER_ZONE))
        self.handle = theme.frame(zone, role="dim", width=px(2), height=px(44))
        self.handle.place(x=px(8), rely=0.5, anchor="w")
        for widget in (zone, self.handle):
            widget.bind("<Button-1>", lambda _e: self.toggle_menu())
            widget.bind("<Enter>", self._zone_enter)
            widget.bind("<Leave>", lambda _e: self.animator.cancel("hover_open"))

        self.menu = theme.frame(root, role="surface")
        self._menu_items = theme.frame(self.menu, role="surface")
        self._menu_items.pack(fill="x", padx=px(30), pady=px((50, 0)))
        profile = theme.frame(self.menu, role="surface")
        profile.pack(side="bottom", fill="x", padx=px(30), pady=px((0, 40)))
        theme.label(
            profile, "активный профиль", role="dim", font="tiny", bg="surface"
        ).pack(anchor="w")
        self.profile_name = theme.label(profile, "", font="ui", bg="surface")
        self.profile_name.pack(anchor="w", pady=px((6, 4)))
        self.profile_details = theme.label(
            profile, "", role="muted", font="tiny", bg="surface", justify="left"
        )
        self.profile_details.pack(anchor="w")
        self.menu.bind("<Leave>", self._menu_leave)
        self.dim = DimLayer(
            root,
            self._dim_area,
            on_click=self.hide_menu,
            on_key=self._on_key,
        )
        self.menu_visible = False
        self._menu_x = -px(MENU_WIDTH)
        self._menu_buttons: dict[str, TextButton] = {}

        root.bind("<Button-1>", self._click_outside_menu, add="+")
        root.bind("<KeyPress>", self._on_key)
        root.bind("<KeyRelease>", self._on_key_release)

    # ---------------------------------------------------------- экраны
    def add_screen(
        self,
        name: str,
        title: str,
        frame: tk.Frame,
        controller: ScreenController | None = None,
        in_menu: bool = True,
    ) -> None:
        """Зарегистрировать экран.

        Args:
            name: Внутреннее имя («training»).
            title: Подпись в боковом меню.
            frame: Виджет экрана (дочерний к :attr:`content`).
            controller: Контроллер, получающий клавиши и события показа.
            in_menu: Есть ли у экрана пункт меню.
        """
        self.screens[name] = Screen(name, title, frame, controller, in_menu)
        self._rebuild_menu()

    def has_screen(self, name: str) -> bool:
        """Проверить, что экран зарегистрирован.

        Args:
            name: Имя экрана.

        Returns:
            ``True``, если он существует.
        """
        return name in self.screens

    def show(self, name: str) -> None:
        """Показать экран и скрыть остальные.

        Args:
            name: Имя экрана.
        """
        self.hide_menu()
        screen = self.screens[name]
        if self.current is screen:
            return
        if self.current is not None:
            self.current.frame.place_forget()
            if self.current.controller:
                self.current.controller.on_hide()
        self.current = screen
        frame = screen.frame
        shift = px(SCREEN_SHIFT)
        frame.place(x=0, y=shift, relwidth=1, relheight=1)
        self.animator.run(
            "screen",
            SCREEN_MS,
            lambda t: frame.place_configure(y=round(shift * (1 - t))),
        )
        self.root.focus_set()  # клавиши не должны оставаться в поле ввода скрытого экрана
        if screen.controller:
            screen.controller.on_show()
        self.refresh_status_hint()

    # ------------------------------------------------------------- меню
    def _rebuild_menu(self) -> None:
        """Пересоздать пункты меню для зарегистрированных экранов (Figma 02)."""
        for child in self._menu_items.winfo_children():
            child.destroy()
        self.theme.label(
            self._menu_items, "меню", role="dim", font="tiny", bg="surface"
        ).pack(anchor="w", pady=px((0, 26)))
        items = [
            (s.name, s.title, lambda n=s.name: self.show(n))
            for s in self.screens.values()
            if s.in_menu
        ]
        items.append(("about", "о программе", self._about))
        self._menu_buttons = {}
        for name, caption, command in items:
            button = TextButton(
                self._menu_items, self.theme, caption, command, bg="surface"
            )
            button.pack(anchor="w", pady=px(7))
            self._menu_buttons[name] = button
        self._mark_current()

    def _mark_current(self) -> None:
        """Подчеркнуть пункт меню видимого экрана."""
        current = self.current.name if self.current else None
        for name, button in self._menu_buttons.items():
            button.set_state(selected=name == current)

    def set_profile(self, name: str, details: str) -> None:
        """Показать активный профиль внизу меню.

        Args:
            name: Имя профиля.
            details: Раскладка и тема, например «EN · QWERTY · тёмная тема».
        """
        self.profile_name.configure(text=name)
        self.profile_details.configure(text=details.replace("   ·   ", "\n"))

    def _dim_area(self) -> tuple[int, int, int, int]:
        """Часть окна справа от меню (она затемняется).

        Returns:
            ``x, y, width, height`` относительно главного окна.
        """
        left = max(0, self._menu_x + px(MENU_WIDTH))
        return left, 0, self.root.winfo_width() - left, self.root.winfo_height()

    def _about(self) -> None:
        """Открыть диалог «О программе»."""
        self.hide_menu()
        if self.on_about:
            self.on_about()

    def toggle_menu(self) -> None:
        """Открыть или закрыть боковое меню."""
        if self.menu_visible:
            self.hide_menu()
        else:
            self.show_menu()

    def _slide_menu(self, target: int, duration_ms: int, done=None) -> None:
        """Сдвинуть боковую панель по горизонтали.

        Args:
            target: Конечный x панели (0 — открыта, ``-MENU_WIDTH`` — закрыта).
            duration_ms: Длительность анимации.
            done: Вызывается в конце.
        """
        start = self._menu_x

        def step(t: float) -> None:
            self._menu_x = round(start + (target - start) * t)
            self.menu.place_configure(x=self._menu_x)
            self.dim.place()

        self.animator.run("menu", duration_ms, step, done)

    def show_menu(self) -> None:
        """Выдвинуть боковое меню (0,38 с)."""
        if self.menu_visible:
            return
        Dropdown.close_active()
        self.menu_visible = True
        self.menu.place(x=self._menu_x, y=0, relheight=1, width=px(MENU_WIDTH))
        self.menu.lift()
        self._mark_current()
        self.dim.show()
        self._slide_menu(0, PANEL_MS)
        for index, button in enumerate(self._menu_buttons.values()):
            button.fade_in(delay_ms=90 + index * 45)

    def hide_menu(self) -> None:
        """Задвинуть боковое меню обратно."""
        if not self.menu_visible:
            return
        self.menu_visible = False
        self.animator.cancel("hover_open")
        self.dim.hide(round(PANEL_MS * 0.7))
        self._slide_menu(
            -px(MENU_WIDTH), round(PANEL_MS * 0.7), done=self.menu.place_forget
        )

    def _zone_enter(self, _event: tk.Event) -> None:
        """Открыть меню, когда мышь задерживается у левого края.

        Args:
            _event: Событие Tk (не используется).
        """
        self.animator.later("hover_open", HOVER_DELAY_MS, self.show_menu)

    def _click_outside_menu(self, event: tk.Event) -> None:
        """Закрыть меню по щелчку справа от него.

        Args:
            event: Событие щелчка Tk.
        """
        if self.menu_visible and event.x_root - self.root.winfo_rootx() > px(
            MENU_WIDTH
        ):
            self.hide_menu()

    def _menu_leave(self, _event: tk.Event) -> None:
        """Закрыть меню, когда мышь уходит с него вправо.

        ``<Leave>`` срабатывает и тогда, когда мышь переходит на дочерний
        виджет, поэтому положение указателя проверяется чуть позже.

        Args:
            _event: Событие Tk (не используется).
        """

        def check() -> None:
            x = self.root.winfo_pointerx() - self.root.winfo_rootx()
            if self.menu_visible and x > px(MENU_WIDTH) + 4:
                self.hide_menu()

        self.animator.later("menu_leave", 220, check)

    # ------------------------------------------------------- строка состояния
    def set_status(self, text: str) -> None:
        """Показать профиль и раскладку в строке состояния.

        Args:
            text: Левая часть строки состояния.
        """
        self.status_left.configure(text=text)

    def refresh_status_hint(self) -> None:
        """Показать горячие клавиши текущего экрана."""
        hint = "esc — меню"
        if self.current and self.current.controller:
            own = self.current.controller.status_hint()
            hint = f"{own}   ·   {hint}" if own else hint
        self.status_right.configure(text=hint)

    # ------------------------------------------------------------- клавиши
    def _on_key(self, event: tk.Event) -> str | None:
        """Направить нажатие клавиши: сначала глобальные клавиши, затем текущий экран.

        Args:
            event: Событие клавиши Tk.

        Returns:
            ``"break"``, если клавиша обработана.
        """
        if Dropdown.close_active():
            return "break"
        if event.keysym == "Escape":
            self.toggle_menu()
            return "break"
        if event.keysym == "F1":
            self._about()
            return "break"
        if self.menu_visible or self.current is None or not self.current.controller:
            return None
        if self.current.controller.handle_key(event):
            return "break"
        return None

    def _on_key_release(self, event: tk.Event) -> None:
        """Передать отпускание клавиши текущему экрану.

        Args:
            event: Событие клавиши Tk.
        """
        if self.current and self.current.controller:
            self.current.controller.handle_key_release(event)
