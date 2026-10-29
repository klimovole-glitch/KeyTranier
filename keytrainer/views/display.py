"""Sharp rendering on high-DPI screens and the bundled font.

Windows stretches programs that do not declare DPI awareness like a
picture, so text and lines look blurry on laptops with 125-200 % scaling.
:func:`prepare_display` declares awareness before the window is created;
after that every size in pixels has to be multiplied by the screen scale —
this is what :func:`px` does. Fonts are given in points and scale by Tk.

The interface font of the mockups is JetBrains Mono (SIL Open Font
License, ``resources/fonts/OFL.txt``). Tk cannot open font files, so on
Windows the bundled TTF files are registered for this process only with
``AddFontResourceExW`` — nothing is installed into the system.
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
    """Declare DPI awareness and register bundled fonts (call before ``Tk()``)."""
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # system DPI aware
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
    """Measure the screen scale once the main window exists.

    Args:
        root: Main window.

    Returns:
        Scale factor: 1.0 at 100 %, 1.5 at 150 % and so on.
    """
    global _scale
    _scale = max(1.0, root.winfo_fpixels("1i") / BASE_DPI)
    return _scale


def scale() -> float:
    """Current screen scale factor.

    Returns:
        Factor measured by :func:`init_scale` (1.0 before it).
    """
    return _scale


def px(value):
    """Convert a size from the mockup to screen pixels.

    Args:
        value: Number or tuple of numbers (``padx=(30, 0)``).

    Returns:
        Scaled value of the same shape.
    """
    if isinstance(value, tuple):
        return tuple(round(v * _scale) for v in value)
    return round(value * _scale)


def set_title_bar_theme(window: tk.Misc, dark: bool) -> None:
    """Paint the Windows title bar dark or light to match the theme.

    Windows 10 (20H1+) and 11 support a dark title bar through
    ``DwmSetWindowAttribute``; on other systems nothing happens.

    Args:
        window: Toplevel window.
        dark: ``True`` for the dark theme.
    """
    if sys.platform != "win32":
        return
    try:
        window.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        value = ctypes.c_int(1 if dark else 0)
        for attribute in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE, old number
            result = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value)
            )
            if result == 0:
                break
        # SWP_FRAMECHANGED | SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER
        ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x27)
    except (AttributeError, OSError, tk.TclError):
        logger.debug("Title bar color is not supported")
