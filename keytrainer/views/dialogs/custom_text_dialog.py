"""Dialog of the "Свой текст" mode: typing a text or loading a TXT file."""

import tkinter as tk
from pathlib import Path
from tkinter import filedialog

from keytrainer.utils.text_files import read_text_file
from keytrainer.views.dialogs.base_dialog import BaseDialog
from keytrainer.views.theme import ThemeManager
from keytrainer.views.widgets.text_button import TextButton


class CustomTextDialog(BaseDialog):
    """Returns the entered text in :attr:`result` (``None`` if cancelled)."""

    def __init__(
        self, parent: tk.Misc, theme: ThemeManager, saved_titles: list[str]
    ) -> None:
        """Build the dialog.

        Args:
            parent: Main window.
            theme: Theme manager.
            saved_titles: Titles of saved user texts (for information).
        """
        super().__init__(parent, theme, "Свой текст")
        self.result: tuple[str, str] | None = None
        theme.label(self.body, "название", role="muted", font="small").pack(anchor="w")
        self.title_entry = tk.Entry(
            self.body, font=theme.fonts["ui"], bd=0, highlightthickness=1, width=40
        )
        theme.style(
            self.title_entry,
            bg="surface",
            fg="text",
            insertbackground="text",
            highlightbackground="border",
            highlightcolor="muted",
        )
        self.title_entry.pack(anchor="w", pady=(4, 14), ipady=4)
        self.title_entry.insert(0, "Мой текст")
        theme.label(self.body, "текст упражнения", role="muted", font="small").pack(
            anchor="w"
        )
        self.text = tk.Text(
            self.body,
            width=70,
            height=12,
            wrap="word",
            bd=0,
            highlightthickness=1,
            font=theme.fonts["ui"],
        )
        theme.style(
            self.text,
            bg="surface",
            fg="text",
            insertbackground="text",
            highlightbackground="border",
            highlightcolor="muted",
        )
        self.text.pack(pady=(4, 6))
        self.error = theme.label(self.body, "", role="error", font="small")
        self.error.pack(anchor="w")
        if saved_titles:
            theme.label(
                self.body,
                "сохраненные тексты: " + ", ".join(saved_titles[-5:]),
                role="dim",
                font="tiny",
            ).pack(anchor="w")
        buttons = theme.frame(self.body)
        buttons.pack(fill="x", pady=(16, 0))
        TextButton(buttons, theme, "загрузить TXT", self._load).pack(side="left")
        TextButton(buttons, theme, "отмена", self.destroy).pack(side="right")
        TextButton(buttons, theme, "начать", self._accept, role="text").pack(
            side="right", padx=30
        )
        self.text.focus_set()

    def _load(self) -> None:
        """Load a TXT file into the text field."""
        name = filedialog.askopenfilename(
            parent=self, filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
        )
        if not name:
            return
        try:
            content = read_text_file(Path(name))
        except (OSError, UnicodeDecodeError) as error:
            self.error.configure(text=f"Не удалось прочитать файл: {error}")
            return
        self.text.delete("1.0", "end")
        self.text.insert("1.0", content)
        self.title_entry.delete(0, "end")
        self.title_entry.insert(0, Path(name).stem[:40])

    def _accept(self) -> None:
        """Validate the input and close the dialog."""
        content = self.text.get("1.0", "end").strip()
        title = self.title_entry.get().strip() or "Мой текст"
        if not content:
            self.error.configure(text="Введите текст или загрузите файл")
            return
        self.result = (title, content)
        self.destroy()
