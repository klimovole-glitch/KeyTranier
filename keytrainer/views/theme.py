from __future__ import annotations
"""Цветовые темы и шрифты интерфейса (Figma, страница «СПЕЦИФИКАЦИЯ»).

Виджеты красятся не напрямую: они регистрируются в :class:`ThemeManager`
с *ролями* («bg», «text», «dim»...). Когда пользователь переключает тему,
менеджер перекрашивает каждый зарегистрированный виджет, поэтому окно
не нужно пересобирать.
"""

import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass
from tkinter import font as tkfont

from keytrainer.data.models import Theme
from keytrainer.views.animation import Animator, ease_in_out, mix_colors

THEME_FADE_MS = 320

MONO_FAMILIES = ("JetBrains Mono", "Consolas", "DejaVu Sans Mono", "Courier New")


@dataclass(frozen=True)
class Palette:
    """Цвета одной темы (шестнадцатеричные строки)."""

    bg: str
    surface: str
    surface_active: str
    border: str
    text: str
    dim: str
    muted: str
    error: str
    success: str
    selection: str
    heat_saturation: float
    heat_value: float
    heat_empty: str


COLOR_FIELDS = (
    "bg",
    "surface",
    "surface_active",
    "border",
    "text",
    "dim",
    "muted",
    "error",
    "success",
    "selection",
    "heat_empty",
)

PALETTES = {
    Theme.DARK: Palette(
        bg="#17171a",
        surface="#222226",
        surface_active="#38383e",
        border="#2c2c31",
        text="#e6e6ea",
        dim="#6e6e78",
        muted="#9a9aa4",
        error="#c97b7b",
        success="#8fb59b",
        selection="#26262a",
        heat_saturation=0.45,
        heat_value=0.42,
        heat_empty="#232326",
    ),
    Theme.LIGHT: Palette(
        bg="#f2f2f4",
        surface="#e8e8eb",
        surface_active="#d2d2d6",
        border="#d9d9dd",
        text="#1d1d1f",
        dim="#a5a5ab",
        muted="#6f6f75",
        error="#c4594d",
        success="#4f8a48",
        selection="#e3e3e7",
        heat_saturation=0.38,
        heat_value=0.86,
        heat_empty="#e2e2e5",
    ),
}

# имя -> (размер в пунктах при font_size 18, жирный)
_FONT_SPECS = {
    "ui": (11, False),
    "small": (9, False),
    "tiny": (8, False),
    "metric": (20, False),
    "metric_big": (34, False),
    "title": (18, False),
    "confirm": (20, False),
    "key": (12, False),
}


def pick_mono_family(root: tk.Misc) -> str:
    """Выбрать первый установленный моноширинный шрифт.

    Tkinter не умеет загружать шрифт из файла, поэтому JetBrains Mono должен
    быть установлен в ОС; иначе используется похожий системный шрифт.

    Args:
        root: Любой виджет (шрифты запрашиваются у Tk).

    Returns:
        Название семейства шрифта.
    """
    installed = set(tkfont.families(root))
    return next((f for f in MONO_FAMILIES if f in installed), "TkFixedFont")


class ThemeManager:
    """Хранит текущую палитру и шрифты и перекрашивает виджеты при смене."""

    def __init__(self, root: tk.Misc, theme: Theme, font_size: int) -> None:
        """Создать шрифты и выбрать палитру.

        Args:
            root: Главное окно.
            theme: Начальная тема.
            font_size: Размер шрифта текста упражнения (настройка профиля).
        """
        self._root = root
        self.family = pick_mono_family(root)
        self.theme = Theme(theme)
        self.palette = PALETTES[self.theme]
        self.fonts = {
            name: tkfont.Font(root, family=self.family, size=size, weight="normal")
            for name, (size, _bold) in _FONT_SPECS.items()
        }
        self.fonts["text"] = tkfont.Font(root, family=self.family, size=font_size)
        self.fonts["underlined"] = tkfont.Font(
            root, family=self.family, size=_FONT_SPECS["ui"][0], underline=True
        )
        self._styled: list[tuple[tk.Misc, dict[str, str]]] = []
        self._listeners: list[Callable[[Palette], None]] = []
        self._animator = Animator(root)

    def style(self, widget: tk.Misc, **roles: str) -> tk.Misc:
        """Покрасить виджет сейчас и при каждой смене темы.

        Args:
            widget: Любой виджет Tk.
            **roles: Параметр виджета -> поле палитры, например ``bg="bg", fg="text"``.

        Returns:
            Тот же виджет (для цепочек вызовов).
        """
        self._styled.append((widget, roles))
        self._apply(widget, roles)
        return widget

    def on_change(self, callback: Callable[[Palette], None]) -> None:
        """Подписаться на смену темы (для холстов и графиков).

        Args:
            callback: Функция, принимающая новую палитру.
        """
        self._listeners.append(callback)

    def set_theme(self, theme: Theme, font_size: int) -> None:
        """Переключить палитру и размер шрифта упражнения.

        Цвета обычных виджетов плавно перетекают из старой палитры в новую;
        холсты и график перерисовываются один раз в конце.

        Args:
            theme: Новая тема.
            font_size: Новый размер текста упражнения.
        """
        old = self.palette
        self.theme = Theme(theme)
        self.palette = PALETTES[self.theme]
        self.fonts["text"].configure(size=font_size)
        self._styled = [(w, r) for w, r in self._styled if w.winfo_exists()]
        if old == self.palette:
            return
        new = self.palette

        def step(t: float) -> None:
            mixed = {
                field: mix_colors(getattr(old, field), getattr(new, field), t)
                for field in COLOR_FIELDS
            }
            self._root.configure(bg=mixed["bg"])
            for widget, roles in self._styled:
                if widget.winfo_exists():
                    widget.configure(
                        **{option: mixed[role] for option, role in roles.items()}
                    )

        def done() -> None:
            self._root.configure(bg=new.bg)
            for widget, roles in self._styled:
                if widget.winfo_exists():
                    self._apply(widget, roles)
            for callback in self._listeners:
                callback(new)

        self._animator.run("theme", THEME_FADE_MS, step, done, easing=ease_in_out)

    def _apply(self, widget: tk.Misc, roles: dict[str, str]) -> None:
        """Настроить параметры виджета по палитре.

        Args:
            widget: Красимый виджет.
            roles: Параметр -> поле палитры.
        """
        widget.configure(
            **{option: getattr(self.palette, role) for option, role in roles.items()}
        )

    # -------------------------------------------------- фабрики виджетов
    def frame(self, parent: tk.Misc, role: str = "bg", **options) -> tk.Frame:
        """Создать рамку, залитую цветом палитры.

        Args:
            parent: Родительский виджет.
            role: Поле палитры для фона.
            **options: Остальные параметры Frame.

        Returns:
            Новая рамка.
        """
        frame = tk.Frame(parent, bd=0, highlightthickness=0, **options)
        return self.style(frame, bg=role)

    def label(
        self,
        parent: tk.Misc,
        text: str = "",
        role: str = "text",
        font: str = "ui",
        bg: str = "bg",
        **options,
    ) -> tk.Label:
        """Создать метку с темой.

        Args:
            parent: Родительский виджет.
            text: Подпись.
            role: Поле палитры для цвета текста.
            font: Имя шрифта из :attr:`fonts`.
            bg: Поле палитры для фона.
            **options: Остальные параметры Label.

        Returns:
            Новая метка.
        """
        options = {"bd": 0, "padx": 0, "pady": 0, **options}
        label = tk.Label(parent, text=text, font=self.fonts[font], **options)
        return self.style(label, fg=role, bg=bg)
