"""Controller of the history screen: loading, sorting, deletion, CSV export."""

import tkinter as tk
from pathlib import Path
from tkinter import filedialog

from keytrainer.controllers.app_state import AppState
from keytrainer.engine.csv_exporter import export_sessions
from keytrainer.engine.history_service import HistoryData, HistoryService
from keytrainer.labels import plural
from keytrainer.utils.background import run_in_background
from keytrainer.views.dialogs.confirm_dialog import ask_confirm
from keytrainer.views.screens.history_screen import HistoryScreen


class HistoryController:
    """Reads the history in a background thread and handles table actions."""

    def __init__(
        self,
        root: tk.Tk,
        view: HistoryScreen,
        state: AppState,
        service: HistoryService,
    ) -> None:
        """Connect the view with the history service.

        Args:
            root: Tk root.
            view: History screen.
            state: Active profile.
            service: History service.
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
            sort=self.sort, delete=self.delete_selected, export=self.export
        )

    def refresh(self) -> None:
        """Reload the history in a background thread."""
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
        """Show loaded data unless a newer request was made.

        Args:
            request: Number of the request.
            data: Loaded history.
        """
        if request != self._request:
            return
        self.data = data
        self.view.show_summary(data.summary)
        self.view.show_chart(data.chart)
        self.view.show_sessions(data.sessions)
        self.view.show_message("" if data.sessions else "история пуста")

    def sort(self, column: str) -> None:
        """Sort by a column; a second click reverses the direction.

        Args:
            column: Column name (white list of ``SessionRepository``).
        """
        if column == self.order_by:
            self.descending = not self.descending
        else:
            self.order_by, self.descending = column, True
        self.refresh()

    def delete_selected(self) -> None:
        """Delete the selected sessions after confirmation."""
        ids = self.view.selected_ids()
        if not ids:
            self.view.show_message("выберите сессию в таблице", is_error=True)
            return
        question = f"Удалить {plural(len(ids), 'сессию', 'сессии', 'сессий')}?"
        if not ask_confirm(self.root, self.view.theme, "Удаление", question):
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
        """Save the history of the profile to a CSV file."""
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

    # ------------------------------------------------- ScreenController
    def on_show(self) -> None:
        """Reload the history every time the screen is opened."""
        self.refresh()

    def on_hide(self) -> None:
        """Nothing to clean up."""

    def handle_key(self, event: tk.Event) -> bool:
        """Delete key removes the selected sessions.

        Args:
            event: Tk key event.

        Returns:
            ``True`` if the key was consumed.
        """
        if event.keysym == "Delete":
            self.delete_selected()
            return True
        return False

    def handle_key_release(self, event: tk.Event) -> None:
        """Key releases are not needed here.

        Args:
            event: Tk key event.
        """

    def status_hint(self) -> str:
        """Hints of the history screen.

        Returns:
            Hint text.
        """
        return "щелчок по заголовку — сортировка   ·   delete — удалить"
