from __future__ import annotations
"""Сборка приложения (ТЗ, п. 4.1.1, многослойная архитектура).

Порядок: база данных -> репозитории -> движок -> контроллеры -> представления.
"""

import logging
import tkinter as tk
from tkinter import messagebox

from keytrainer.config import APP_NAME, DB_PATH, SETTINGS_PATH, setup_logging
from keytrainer.controllers.app_state import AppState
from keytrainer.controllers.history_controller import HistoryController
from keytrainer.controllers.settings_controller import SettingsController
from keytrainer.controllers.stats_controller import StatsController
from keytrainer.controllers.training_controller import (
    ResultsController,
    TrainingController,
)
from keytrainer.data.database import Database, InitStatus
from keytrainer.data.models import Theme
from keytrainer.data.repositories import (
    KeyRepository,
    KeyStatRepository,
    LayoutRepository,
    SessionRepository,
    TextRepository,
    UserRepository,
    WordRepository,
)
from keytrainer.engine.analytics_engine import AnalyticsEngine
from keytrainer.engine.exercise_generator import (
    ExerciseGenerator,
    RepositoryWordSource,
)
from keytrainer.engine.history_service import HistoryService
from keytrainer.engine.profile_service import ProfileService
from keytrainer.engine.session_service import SessionService
from keytrainer.labels import LAYOUT_TITLES
from keytrainer.views.dialogs.about_dialog import AboutDialog
from keytrainer.views.display import (
    init_scale,
    prepare_display,
    px,
    set_title_bar_theme,
)
from keytrainer.views.main_window import MainWindow
from keytrainer.views.screens.history_screen import HistoryScreen
from keytrainer.views.screens.results_screen import ResultsScreen
from keytrainer.views.screens.settings_screen import SettingsScreen
from keytrainer.views.screens.stats_screen import StatsScreen
from keytrainer.views.screens.training_screen import TrainingScreen
from keytrainer.views.theme import ThemeManager

logger = logging.getLogger(__name__)

RECOVERY_MESSAGES = {
    InitStatus.RESTORED_FROM_BACKUP: (
        "База данных была повреждена и восстановлена из резервной копии. "
        "Поврежденный файл сохранен рядом с программой."
    ),
    InitStatus.RECREATED: (
        "База данных была повреждена, резервной копии нет. Создана новая база; "
        "поврежденный файл сохранен рядом с программой."
    ),
}


class Repositories:
    """Все репозитории программы, создаются один раз."""

    def __init__(self, database: Database) -> None:
        """Создать репозитории поверх одной базы данных.

        Args:
            database: Инициализированная база данных.
        """
        self.layouts = LayoutRepository(database)
        self.keys = KeyRepository(database)
        self.users = UserRepository(database)
        self.words = WordRepository(database)
        self.texts = TextRepository(database)
        self.sessions = SessionRepository(database)
        self.key_stats = KeyStatRepository(database)


class Application:
    """Создаёт окно и связывает контроллеры с представлениями."""

    def __init__(self, root: tk.Tk, database: Database) -> None:
        """Создать всё, что нужно программе.

        Args:
            root: Корневое окно Tk.
            database: Инициализированная база данных.
        """
        self.root = root
        self.repos = Repositories(database)
        self.state = AppState(self.repos.users, SETTINGS_PATH)
        user = self.state.user
        self.theme = ThemeManager(root, user.theme, user.font_size)
        self.window = MainWindow(root, self.theme)
        self.window.on_about = self.show_about
        root.report_callback_exception = self._report_error

        source = RepositoryWordSource(
            self.repos.layouts, self.repos.words, self.repos.texts
        )
        self.session_service = SessionService(
            self.repos.sessions, self.repos.keys, self.repos.layouts
        )
        self._build_training(ExerciseGenerator(source))
        self._build_stats()
        self._build_history_and_settings()
        self.state.subscribe(self._on_user_changed)
        self._on_user_changed(user)

    def _build_training(self, generator: ExerciseGenerator) -> None:
        """Создать экраны тренировки и результатов.

        Args:
            generator: Генератор упражнений.
        """
        content = self.window.content
        self.training_view = TrainingScreen(content, self.theme)
        self.training = TrainingController(
            self.root,
            self.training_view,
            self.state,
            generator,
            self.session_service,
            self.repos.keys,
            self.repos.texts,
        )
        self.results_view = ResultsScreen(content, self.theme)
        results = ResultsController(self.results_view, self.training, self.window.show)
        self.training.on_finished = self._show_results
        self.training.on_layout_changed = lambda _layout: self._update_status()
        self.window.add_screen(
            "training", "тренировка", self.training_view, self.training
        )
        self.window.add_screen(
            "results", "результаты", self.results_view, results, in_menu=False
        )

    def _build_stats(self) -> None:
        """Создать экран статистики (тепловая карта и проблемные клавиши)."""
        analytics = AnalyticsEngine(
            self.repos.key_stats, self.repos.keys, self.repos.sessions
        )
        view = StatsScreen(self.window.content, self.theme)
        controller = StatsController(
            self.root, view, self.state, analytics, self.training, self.window.show
        )
        self.window.add_screen("stats", "статистика", view, controller)

    def _build_history_and_settings(self) -> None:
        """Создать экраны истории и настроек."""
        content = self.window.content
        history_view = HistoryScreen(content, self.theme)
        history = HistoryController(
            self.root, history_view, self.state, HistoryService(self.repos.sessions)
        )
        self.window.add_screen("history", "история", history_view, history)
        settings_view = SettingsScreen(content, self.theme)
        settings = SettingsController(
            self.root,
            settings_view,
            self.state,
            ProfileService(self.repos.users, self.repos.sessions),
        )
        self.window.add_screen("settings", "настройки", settings_view, settings)

    def _show_results(self, result) -> None:
        """Открыть карточку результатов.

        Args:
            result: Данные завершённой сессии.
        """
        self.results_view.set_stats_available(self.window.has_screen("stats"))
        self.results_view.show_result(result)
        self.window.show("results")

    def _on_user_changed(self, user) -> None:
        """Применить тему профиля и обновить строку состояния.

        Args:
            user: Активный профиль.
        """
        self.theme.set_theme(user.theme, user.font_size)
        set_title_bar_theme(self.root, user.theme == Theme.DARK)
        self._update_status()

    def _update_status(self) -> None:
        """Показать профиль и раскладку в строке состояния."""
        layout = LAYOUT_TITLES[self.training.params.layout_name]
        user = self.state.user
        self.window.set_status(f"профиль: {user.user_name}   ·   {layout}")
        theme = "тёмная тема" if user.theme == Theme.DARK else "светлая тема"
        self.window.set_profile(user.user_name, f"{layout}   ·   {theme}")

    def show_about(self) -> None:
        """Open "О программе"."""
        AboutDialog(self.root, self.theme).show_modal()

    def start(self) -> None:
        """Показать первый экран и сгенерировать первое упражнение."""
        self.window.show("training")
        self.training.new_exercise()
        self.root.focus_force()

    def _report_error(self, exc_type, exc_value, traceback) -> None:
        """Записать непредвиденную ошибку в журнал и показать её понятными словами (ТЗ, п. 4.1.4).

        Args:
            exc_type: Класс исключения.
            exc_value: Исключение.
            traceback: Трассировка стека.
        """
        logger.error("Unhandled error", exc_info=(exc_type, exc_value, traceback))
        messagebox.showerror(
            APP_NAME,
            f"Произошла ошибка: {exc_value}\nПодробности записаны в keytrainer.log",
            parent=self.root,
        )


def main() -> None:
    """Запустить программу."""
    setup_logging()
    database = Database(DB_PATH)
    status = database.initialize()
    prepare_display()  # чёткий текст при масштабе экрана 125-200 %, встроенный шрифт
    root = tk.Tk()
    init_scale(root)
    root.title(APP_NAME)
    width, height = px(1280), px(820)
    # не больше экрана (ноутбуки с большим масштабированием)
    width = min(width, root.winfo_screenwidth() - px(40))
    height = min(height, root.winfo_screenheight() - px(80))
    root.geometry(f"{width}x{height}")
    root.minsize(min(px(1024), width), min(px(720), height))
    app = Application(root, database)
    app.start()
    if status in RECOVERY_MESSAGES:
        root.after(
            300, lambda: messagebox.showwarning(APP_NAME, RECOVERY_MESSAGES[status])
        )
    root.mainloop()


if __name__ == "__main__":
    main()