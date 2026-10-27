"""Base class for modal dialogs in the style of the main window."""

import tkinter as tk

from keytrainer.views.theme import ThemeManager


class BaseDialog(tk.Toplevel):
    """Modal window centered over its parent; Esc closes it."""

    def __init__(self, parent: tk.Misc, theme: ThemeManager, title: str) -> None:
        """Create an empty modal window.

        Args:
            parent: Main window.
            theme: Theme manager.
            title: Window title.
        """
        super().__init__(parent)
        self.theme = theme
        self.title(title)
        self.resizable(False, False)
        self.transient(parent.winfo_toplevel())
        theme.style(self, bg="bg")
        self.body = theme.frame(self)
        self.body.pack(fill="both", expand=True, padx=36, pady=30)
        self.bind("<Escape>", lambda _e: self.destroy())

    def show_modal(self) -> None:
        """Center the window, grab input and wait until it is closed."""
        self.update_idletasks()
        parent = self.master.winfo_toplevel()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 3
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        self.grab_set()
        self.focus_set()
        self.wait_window()
