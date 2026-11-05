from __future__ import annotations
"""Контроллер экрана истории: загрузка, сортировка, удаление, экспорт и импорт CSV."""

import tkinter as tk
from pathlib import Path
from tkinter import filedialog

from keytrainer.controllers.app_state import AppState
from keytrainer.engine.csv_exporter import export_sessions
from keytrainer.engine.history_service import (
    HistoryData,
    HistoryService,
    ImportSummary,
)
from keytrainer.labels import plural
from keytrainer.utils.background import run_in_background
from keytrainer.views.dialogs.confirm_dialog import ask_confirm
from keytrainer.views.screens.history_screen import HistoryScreen


class HistoryController:
    """Читает историю в фоновом потоке и обрабатывает действия с таблицей."""

    def __init__(
        self,
        root: tk.Tk,
        view: HistoryScreen,
        state: AppState,
        service: HistoryService,
    ) -> None:
        """Связать представление с сервисом истории.

        Args:
            root: Корневое окно Tk.
            view: Экран истории.
            state: Активный профиль.
            service: Сервис истории.
        """
        self.root = root
        self.view = view
        self.state = state
        self.service = service
        self.order_by = "started_at"
        self.descending = True
        self.data: HistoryData | None = None
        self._request = 0
        view.callbacks.update(
            sort=self.sort,
            delete=self.delete_selected,
            export=self.export,
            import_csv=self.import_csv,
        )

    def refresh(self) -> None:
        """Перезагрузить историю в фоновом потоке."""
        self._request += 1
        request = self._request
        user_id, order_by, descending = (
            self.state.user.id,
            self.order_by,
            self.descending,
        )
        self.view.show_sort(order_by, descending)
        self.view.show_message("загрузка…")
        run_in_background(
            self.root,
            lambda: self.service.load(user_id, order_by, descending),
            lambda data: self._on_data(request, data),
            lambda error: self.view.show_message(f"Ошибка: {error}", is_error=True),
        )

    def _on_data(self, request: int, data: HistoryData) -> None:
        """Показать загруженные данные, если не был сделан более новый запрос.

        Args:
            request: Номер запроса.
            data: Загруженная история.
        """
        if request != self._request:
            return
        self.data = data
        self.view.show_summary(data.summary)
        self.view.show_chart(data.chart)
        self.view.show_sessions(data.sessions)
        self.view.show_message("" if data.sessions else "история пуста")

    def sort(self, column: str) -> None:
        """Сортировать по столбцу; повторный щелчок меняет направление.

        Args:
            column: Имя столбца (белый список ``SessionRepository``).
        """
        if column == self.order_by:
            self.descending = not self.descending
        else:
            self.order_by, self.descending = column, True
        self.refresh()

    def delete_selected(self) -> None:
        """Удалить выбранные сессии после подтверждения."""
        ids = self.view.selected_ids()
        if not ids:
            self.view.show_message("выберите сессию в таблице", is_error=True)
            return
        if len(ids) == 1:
            question = f"удалить запись от {self.view.selected_dates()[0]}?"
            details = "Сессия будет удалена из истории и графика."
        else:
            question = f"удалить {plural(len(ids), 'запись', 'записи', 'записей')}?"
            details = "Сессии будут удалены из истории и графика."
        if not ask_confirm(self.root, self.view.theme, question, details):
            return
        deleted = self.service.delete(ids)
        self.refresh()
        self.root.after(
            50,
            lambda: self.view.show_message(
                f"удалено: {plural(deleted, 'сессия', 'сессии', 'сессий')}"
            ),
        )

    def export(self) -> None:
        """Сохранить историю профиля в файл CSV."""
        if not self.data or not self.data.sessions:
            self.view.show_message("нечего экспортировать", is_error=True)
            return
        name = filedialog.asksaveasfilename(
            parent=self.root,
            defaultextension=".csv",
            filetypes=[("CSV (Excel)", "*.csv")],
            initialfile=f"история_{self.state.user.user_name}.csv",
        )
        if not name:
            return
        sessions = self.data.sessions
        self.view.show_message("экспорт…")
        run_in_background(
            self.root,
            lambda: export_sessions(Path(name), sessions),
            lambda count: self.view.show_message(
                f"сохранено {plural(count, 'сессия', 'сессии', 'сессий')}: {name}"
            ),
            lambda error: self.view.show_message(
                f"не удалось сохранить файл: {error}", is_error=True
            ),
        )

    def import_csv(self) -> None:
        """Добавить сессии из файла CSV в историю профиля."""
        name = filedialog.askopenfilename(
            parent=self.root,
            filetypes=[("CSV (Excel)", "*.csv"), ("Все файлы", "*.*")],
        )
        if not name:
            return
        user = self.state.user
        self.view.show_message("импорт…")
        run_in_background(
            self.root,
            lambda: self.service.import_csv(Path(name), user.id, user.layout_id),
            self._on_imported,
            lambda error: self.view.show_message(
                f"не удалось импортировать: {error}", is_error=True
            ),
        )

    def _on_imported(self, summary: ImportSummary) -> None:
        """Перезагрузить таблицу и сообщить, что было импортировано.

        Args:
            summary: Количество добавленных, повторяющихся и нечитаемых строк.
        """
        text = f"добавлено: {plural(summary.added, 'сессия', 'сессии', 'сессий')}"
        if summary.duplicates:
            text += f", уже были: {summary.duplicates}"
        if summary.invalid:
            text += f", пропущено строк с ошибками: {summary.invalid}"
        self.refresh()
        self.root.after(
            50,
            lambda: self.view.show_message(
                text, is_error=summary.added == 0 and summary.invalid > 0
            ),
        )

    # ------------------------------------------------- ScreenController
    def on_show(self) -> None:
        """Перезагружать историю при каждом открытии экрана."""
        self.refresh()

    def on_hide(self) -> None:
        """Очищать нечего."""

    def handle_key(self, event: tk.Event) -> bool:
        """Клавиша Delete удаляет выбранные сессии.

        Args:
            event: Событие клавиши Tk.

        Returns:
            ``True``, если клавиша обработана.
        """
        if event.keysym == "Delete":
            self.delete_selected()
            return True
        return False

    def handle_key_release(self, event: tk.Event) -> None:
        """Отпускание клавиш здесь не нужно.

        Args:
            event: Событие клавиши Tk.
        """

    def status_hint(self) -> str:
        """Подсказки экрана истории.

        Returns:
            Текст подсказки.
        """
        return "щелчок по заголовку — сортировка   ·   delete — удалить"
