from __future__ import annotations
"""Чёткая отрисовка на экранах с высоким DPI и встроенный шрифт.

Windows растягивает программы, не объявившие поддержку DPI, как картинку,
поэтому текст и линии выглядят размытыми на ноутбуках с масштабом 125-200 %.
:func:`prepare_display` объявляет поддержку до создания окна; после этого
каждый размер в пикселях нужно умножать на масштаб экрана — это делает
:func:`px`. Шрифты задаются в пунктах и масштабируются самим Tk.

Шрифт интерфейса в макетах — JetBrains Mono (SIL Open Font License,
``resources/fonts/OFL.txt``). Tk не умеет открывать файлы шрифтов, поэтому
в Windows встроенные файлы TTF регистрируются только для этого процесса
через ``AddFontResourceExW`` — в систему ничего не устанавливается.
"""

import ctypes
import logging
import sys
import tkinter as tk

from keytrainer.config import RESOURCES_DIR

FONTS_DIR = RESOURCES_DIR / "fonts"
FR_PRIVATE = 0x10
BASE_DPI = 96

_scale = 1.0
logger = logging.getLogger(__name__)


def prepare_display() -> None:
    """Объявить поддержку DPI и зарегистрировать встроенные шрифты (вызывать до ``Tk()``)."""
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # система учитывает DPI
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()  # Windows 7
        except (AttributeError, OSError):
            logger.warning("DPI awareness is not available")
    for path in FONTS_DIR.glob("*.ttf"):
        added = ctypes.windll.gdi32.AddFontResourceExW(str(path), FR_PRIVATE, 0)
        if not added:
            logger.warning("Font %s was not loaded", path.name)


def init_scale(root: tk.Misc) -> float:
    """Измерить масштаб экрана, когда главное окно уже существует.

    Args:
        root: Главное окно.

    Returns:
        Коэффициент масштаба: 1.0 при 100 %, 1.5 при 150 % и так далее.
    """
    global _scale
    _scale = max(1.0, root.winfo_fpixels("1i") / BASE_DPI)
    return _scale


def scale() -> float:
    """Текущий коэффициент масштаба экрана.

    Returns:
        Коэффициент, измеренный :func:`init_scale` (до неё — 1.0).
    """
    return _scale


def px(value):
    """Преобразовать размер из макета в пиксели экрана.

    Args:
        value: Число или кортеж чисел (``padx=(30, 0)``).

    Returns:
        Масштабированное значение той же формы.
    """
    if isinstance(value, tuple):
        return tuple(round(v * _scale) for v in value)
    return round(value * _scale)


def set_title_bar_theme(window: tk.Misc, dark: bool) -> None:
    """Покрасить заголовок окна Windows в тёмный или светлый цвет под тему.

    Windows 10 (20H1+) и 11 поддерживают тёмный заголовок через
    ``DwmSetWindowAttribute``; в других системах ничего не происходит.

    Args:
        window: Окно верхнего уровня.
        dark: ``True`` для тёмной темы.
    """
    if sys.platform != "win32":
        return
    try:
        window.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        value = ctypes.c_int(1 if dark else 0)
        for attribute in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE, старый номер
            result = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value)
            )
            if result == 0:
                break
        # SWP_FRAMECHANGED | SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER
        ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x27)
    except (AttributeError, OSError, tk.TclError):
        logger.debug("Title bar color is not supported")
