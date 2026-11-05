from __future__ import annotations
"""Сообщения о состоянии, которые появляются плавно, а не выскакивают."""

import tkinter as tk

from keytrainer.views.animation import Animator
from keytrainer.views.theme import ThemeManager

MESSAGE_FADE_MS = 260


def show_animated_message(
    label: tk.Label, theme: ThemeManager, text: str, is_error: bool = False
) -> None:
    """Изменить текст метки сообщения и плавно показать её.

    Args:
        label: Метка сообщения экрана.
        theme: Менеджер тем.
        text: Новое сообщение, пустая строка — очистить.
        is_error: Окрасить сообщение как ошибку.
    """
    animator = getattr(label, "_message_animator", None)
    if animator is None:
        animator = Animator(label)
        label._message_animator = animator  # один аниматор на метку
    palette = theme.palette
    color = palette.error if is_error else palette.muted
    label.configure(text=text)
    if not text:
        animator.cancel("fade")
        return
    animator.fade("fade", label, "fg", palette.bg, color, MESSAGE_FADE_MS)
