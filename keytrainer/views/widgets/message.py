"""Status messages that appear smoothly instead of popping up."""

import tkinter as tk

from keytrainer.views.animation import Animator
from keytrainer.views.theme import ThemeManager

MESSAGE_FADE_MS = 260


def show_animated_message(
    label: tk.Label, theme: ThemeManager, text: str, is_error: bool = False
) -> None:
    """Change the text of a message label and fade it in.

    Args:
        label: Message label of a screen.
        theme: Theme manager.
        text: New message, empty string to clear.
        is_error: Color the message as an error.
    """
    animator = getattr(label, "_message_animator", None)
    if animator is None:
        animator = Animator(label)
        label._message_animator = animator  # one animator per label
    palette = theme.palette
    color = palette.error if is_error else palette.muted
    label.configure(text=text)
    if not text:
        animator.cancel("fade")
        return
    animator.fade("fade", label, "fg", palette.bg, color, MESSAGE_FADE_MS)
