"""Built-in help "Помощь → О программе" (ТЗ, п. 4.3.8)."""

import tkinter as tk

from keytrainer import __version__
from keytrainer.config import APP_NAME
from keytrainer.views.dialogs.base_dialog import BaseDialog
from keytrainer.views.display import px
from keytrainer.views.theme import ThemeManager
from keytrainer.views.widgets.text_button import TextButton

HELP_TEXT = (
    "Клавиатурный тренажер с аналитикой\n\n"
    "Поставьте пальцы на домашний ряд (ФЫВА — ОЛДЖ, ASDF — JKL;) и печатайте,\n"
    "не глядя на клавиатуру. Подсвеченная клавиша и подсказка показывают,\n"
    "какой палец нажимает следующую клавишу.\n\n"
    "Метрики: WPM — слов в минуту (слово = 5 символов), CPM — символов\n"
    "в минуту, % ошибок — неверные нажатия от всех нажатий.\n"
    "Ошибка учитывается, даже если ее исправили клавишей Backspace.\n\n"
    "Тепловая карта: зеленый — мало ошибок, красный — много,\n"
    "серый — меньше 5 нажатий.\n\n"
    "Клавиши: Tab — заново, Enter — завершить, Ctrl+P — пауза,\n"
    "Esc — меню, F1 — эта справка.\n\n"
    "Перед тренировкой включите в ОС раскладку, выбранную в упражнении."
)


class AboutDialog(BaseDialog):
    """Short user guide and the program version."""

    def __init__(self, parent: tk.Misc, theme: ThemeManager) -> None:
        """Fill the dialog.

        Args:
            parent: Main window.
            theme: Theme manager.
        """
        super().__init__(parent, theme, "О программе")
        theme.label(self.body, f"{APP_NAME} {__version__}", font="title").pack(
            anchor="w"
        )
        theme.label(self.body, HELP_TEXT, role="muted", justify="left").pack(
            anchor="w", pady=px((16, 20))
        )
        theme.label(
            self.body,
            "Разработчик: Климов О. В., группа ИСП-341, НЭК, 2026",
            role="dim",
            font="small",
        ).pack(anchor="w")
        TextButton(self.body, theme, "закрыть", self.destroy, role="text").pack(
            anchor="e", pady=px((20, 0))
        )
