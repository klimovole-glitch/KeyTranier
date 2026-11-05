from __future__ import annotations
"""Подтверждение поверх затемнённого окна (Figma 09c «История — удаление записи»).

Окно затемняется :class:`DimLayer`; над ним безрамочное окно с
«прозрачным» цветом фона показывает только вопрос и два действия, поэтому
они кажутся лежащими прямо на затемнённом экране. Enter подтверждает,
Esc отменяет. Где прозрачность недоступна, вопрос показывается на
обычной тёмной панели посередине окна.
"""

import tkinter as tk

from keytrainer.views.animation import Animator, mix_colors
from keytrainer.views.display import px
from keytrainer.views.theme import ThemeManager
from keytrainer.views.widgets.dim_layer import (
    DIM_ALPHA,
    DimLayer,
    transparency_supported,
)

FADE_IN_MS = 200
TEXT = "#e6e6ea"
MUTED = "#9a9aa4"
ERROR = "#c97b7b"


class ConfirmOverlay:
    """Вопрос с «отмена» и опасным действием поверх затемнённого окна."""

    def __init__(
        self,
        root: tk.Misc,
        theme: ThemeManager,
        question: str,
        details: str = "",
        action: str = "удалить",
    ) -> None:
        """Построить наложение (показывается через :meth:`ask`).

        Args:
            root: Главное окно.
            theme: Менеджер тем (шрифты и фон).
            question: Главная строка, например «удалить запись от 19.10.2026 18:30?».
            details: Мелкая строка под вопросом.
            action: Подпись подтверждающего действия.
        """
        self.root = root.winfo_toplevel()
        self.theme = theme
        self.question = question
        self.details = details
        self.action = action
        self.confirmed = False
        self.layer = DimLayer(self.root, self._client_area)
        self.panel: tk.Toplevel | None = None
        self._geometry = ""

    def _client_area(self) -> tuple[int, int, int, int]:
        """Всё главное окно.

        Returns:
            ``x, y, width, height`` относительно главного окна.
        """
        return 0, 0, self.root.winfo_width(), self.root.winfo_height()

    def ask(self) -> bool:
        """Показать вопрос и дождаться ответа.

        Returns:
            ``True``, если действие подтверждено.
        """
        transparent = transparency_supported()
        key = mix_colors(self.theme.palette.bg, "#000000", DIM_ALPHA)
        bg = key if transparent else self.theme.palette.surface
        panel = tk.Toplevel(self.root, bg=bg, bd=0)
        panel.overrideredirect(True)
        panel.transient(self.root)
        self.panel = panel
        if transparent:
            panel.attributes("-transparentcolor", key)
            panel.attributes("-alpha", 0.0)
        body = tk.Frame(panel, bg=bg, bd=0)
        body.place(relx=0.5, rely=0.45, anchor="center")
        fonts = self.theme.fonts
        tk.Label(body, text=self.question, bg=bg, fg=TEXT, font=fonts["confirm"]).pack()
        if self.details:
            tk.Label(body, text=self.details, bg=bg, fg=MUTED, font=fonts["ui"]).pack(
                pady=px((10, 0))
            )
        row = tk.Frame(body, bg=bg, bd=0)
        row.pack(pady=px((34, 0)))
        self._button(row, "отмена", MUTED, TEXT, self._cancel, bg).pack(
            side="left", padx=px(40)
        )
        self._button(row, self.action, ERROR, "#e09a9a", self._confirm, bg).pack(
            side="left", padx=px(40)
        )
        panel.bind("<Escape>", lambda _e: self._cancel())
        panel.bind("<Return>", lambda _e: self._confirm())
        self._place_panel()
        panel.lift()
        follow = self.root.bind(
            "<Configure>",
            lambda e: e.widget is self.root and self._place_panel(),
            add="+",
        )
        self.layer.show()
        if transparent:
            Animator(panel).run(
                "alpha", FADE_IN_MS, lambda t: panel.attributes("-alpha", t)
            )
        panel.grab_set()
        panel.focus_force()
        self.root.wait_window(panel)
        self.root.unbind("<Configure>", follow)
        self.layer.hide(140)
        return self.confirmed

    def _button(self, parent, text, color, hover, command, bg) -> tk.Label:
        """Создать текстовое действие, которое светлеет под мышью.

        Args:
            parent: Контейнер.
            text: Подпись.
            color: Обычный цвет.
            hover: Цвет под мышью.
            command: Вызывается по щелчку.
            bg: Цвет фона.

        Returns:
            Метка, используемая как кнопка.
        """
        label = tk.Label(
            parent,
            text=text,
            bg=bg,
            fg=color,
            font=self.theme.fonts["ui"],
            cursor="hand2",
            padx=px(4),
        )
        label.bind("<Enter>", lambda _e: label.configure(fg=hover))
        label.bind("<Leave>", lambda _e: label.configure(fg=color))
        label.bind("<Button-1>", lambda _e: command())
        return label

    def _place_panel(self) -> None:
        """Накрыть главное окно панелью."""
        panel = self.panel
        if panel is None or not panel.winfo_exists():
            return
        if transparency_supported():
            width, height = self.root.winfo_width(), self.root.winfo_height()
            x, y = self.root.winfo_rootx(), self.root.winfo_rooty()
        else:
            width, height = px(640), px(240)
            x = self.root.winfo_rootx() + (self.root.winfo_width() - width) // 2
            y = self.root.winfo_rooty() + (self.root.winfo_height() - height) // 3
        geometry = f"{width}x{height}+{x}+{y}"
        if geometry != self._geometry:  # см. DimLayer.place: избегаем цикла
            self._geometry = geometry
            panel.geometry(geometry)

    def _confirm(self) -> None:
        """Закрыть с ответом «да»."""
        self.confirmed = True
        self._close()

    def _cancel(self) -> None:
        """Закрыть с ответом «нет»."""
        self._close()

    def _close(self) -> None:
        """Уничтожить панель (затемняющий слой гаснет следом)."""
        if self.panel is not None and self.panel.winfo_exists():
            self.panel.grab_release()
            self.panel.destroy()
        self.root.focus_force()  # клавиши должны возвращаться в главное окно


def ask_confirm(
    parent: tk.Misc,
    theme: ThemeManager,
    question: str,
    details: str = "",
    action: str = "удалить",
) -> bool:
    """Показать подтверждение поверх затемнённого окна и дождаться ответа.

    Args:
        parent: Любой виджет главного окна.
        theme: Менеджер тем.
        question: Главная строка.
        details: Пояснение мелким шрифтом.
        action: Подпись подтверждающего действия.

    Returns:
        ``True``, если пользователь подтвердил.
    """
    return ConfirmOverlay(parent, theme, question, details, action).ask()
