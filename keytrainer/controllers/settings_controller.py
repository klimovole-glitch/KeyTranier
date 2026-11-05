from __future__ import annotations
"""Контроллер экрана настроек: управление профилями и личные настройки."""

import tkinter as tk
from dataclasses import replace

from keytrainer.controllers.app_state import AppState
from keytrainer.data.exceptions import DataAccessError
from keytrainer.data.models import User
from keytrainer.engine.profile_service import ProfileService
from keytrainer.labels import plural
from keytrainer.views.dialogs.confirm_dialog import ask_confirm
from keytrainer.views.dialogs.profile_name_dialog import ProfileNameDialog
from keytrainer.views.screens.settings_screen import SettingsScreen

APPEARANCE_DELAY_MS = 250


class SettingsController:
    """Редактирует черновую копию настроек, пока не нажато «сохранить»."""

    def __init__(
        self,
        root: tk.Tk,
        view: SettingsScreen,
        state: AppState,
        profiles: ProfileService,
    ) -> None:
        """Связать представление с сервисом профилей.

        Args:
            root: Корневое окно Tk.
            view: Экран настроек.
            state: Активный профиль.
            profiles: Сервис профилей.
        """
        self.root = root
        self.view = view
        self.state = state
        self.profiles = profiles
        self.draft: User = replace(state.user)
        self._visible = False
        self._appearance_job: str | None = None
        view.callbacks.update(
            create=self.create,
            rename=self.rename,
            switch_user=self.switch_user,
            delete=self.delete,
            draft=self.change_draft,
            switch=self.toggle,
            save=self.save,
            reset=self.reset,
        )
        state.subscribe(lambda _user: self._visible and self.refresh())

    def refresh(self) -> None:
        """Показать профили и сохранённые настройки активного профиля."""
        self.draft = replace(self.state.user)
        self.view.show_profiles(self.profiles.list_profiles(), self.state.user.id)
        self.view.show_draft(self.draft)

    # --------------------------------------------------------- профили
    def create(self, name: str) -> None:
        """Создать профиль из введённого имени.

        Args:
            name: Введённое имя.
        """
        try:
            user = self.profiles.create(name, self.draft.layout_id or 1)
        except DataAccessError as error:
            self.view.show_name_error(str(error))
            return
        self.view.clear_new_name()
        self.view.show_profiles(self.profiles.list_profiles(), self.state.user.id)
        self.view.show_message(f"профиль «{user.user_name}» создан")

    def rename(self, user_id: int) -> None:
        """Переименовать профиль в диалоге.

        Args:
            user_id: Идентификатор профиля.
        """
        info = next(p for p in self.profiles.list_profiles() if p.user.id == user_id)

        def apply(name: str) -> str | None:
            try:
                self.profiles.rename(user_id, name)
            except DataAccessError as error:
                return str(error)
            return None

        ProfileNameDialog(
            self.root, self.view.theme, info.user.user_name, apply
        ).show_modal()
        if user_id == self.state.user.id:
            self.state.reload_user()
        self.refresh()

    def switch_user(self, user_id: int) -> None:
        """Сделать активным другой профиль.

        Args:
            user_id: Идентификатор профиля.
        """
        self.state.switch_user(user_id)
        self.view.show_message(f"активный профиль: {self.state.user.user_name}")

    def delete(self, user_id: int) -> None:
        """Удалить профиль и его историю после подтверждения.

        Args:
            user_id: Идентификатор профиля.
        """
        info = next(p for p in self.profiles.list_profiles() if p.user.id == user_id)
        sessions = plural(info.sessions_count, "сессия", "сессии", "сессий")
        question = f"удалить профиль «{info.user.user_name}»?"
        details = f"Вместе с ним будут удалены {sessions} и статистика клавиш."
        if not ask_confirm(self.root, self.view.theme, question, details):
            return
        try:
            active = self.profiles.delete(user_id, self.state.user.id)
        except DataAccessError as error:
            self.view.show_message(str(error), is_error=True)
            return
        if active != self.state.user.id:
            self.state.switch_user(active)
        self.refresh()
        self.view.show_message(f"профиль «{info.user.user_name}» удален")

    # --------------------------------------------------------- настройки
    def change_draft(self, **changes) -> None:
        """Изменить редактируемую настройку (ещё не сохранена).

        Args:
            **changes: Поля :class:`User`.
        """
        self.draft = replace(self.draft, **changes)
        self.view.show_draft(self.draft)
        if "theme" in changes or "font_size" in changes:
            self._apply_appearance_later()

    def _apply_appearance_later(self) -> None:
        """Применить тему и размер шрифта через мгновенье после последнего изменения.

        Ползунок отправляет много значений во время перетаскивания; сохраняется
        только последнее, поэтому окно не перерисовывается десятки раз.
        """
        if self._appearance_job is not None:
            self.root.after_cancel(self._appearance_job)
        self._appearance_job = self.root.after(
            APPEARANCE_DELAY_MS, self._apply_appearance
        )

    def _apply_appearance(self) -> None:
        """Сразу сохранить тему и размер шрифта и перерисовать окно.

        Остальные изменённые настройки остаются в черновике до нажатия «сохранить».
        """
        self._appearance_job = None
        user, pending = self.state.user, self.draft
        if (user.theme, user.font_size) == (pending.theme, pending.font_size):
            return
        try:
            self.profiles.save_settings(
                replace(user, theme=pending.theme, font_size=pending.font_size)
            )
        except DataAccessError as error:
            self.view.show_message(str(error), is_error=True)
            return
        self.state.reload_user()  # перерисовывает окно, обновляет этот экран
        self.draft = pending
        self.view.show_draft(self.draft)

    def toggle(self, field: str) -> None:
        """Переключить настройки «вкл/выкл».

        Args:
            field: ``show_finger_hint`` или ``auto_pause``.
        """
        self.change_draft(**{field: not getattr(self.draft, field)})

    def save(self) -> None:
        """Сохранить черновик и применить его ко всей программе."""
        try:
            self.profiles.save_settings(self.draft)
        except DataAccessError as error:
            self.view.show_message(str(error), is_error=True)
            return
        self.state.reload_user()
        self.view.show_message("настройки сохранены")

    def reset(self) -> None:
        """Подставить в черновик значения по умолчанию."""
        self.draft = self.profiles.with_defaults(self.draft)
        self.view.show_draft(self.draft)
        self._apply_appearance_later()
        self.view.show_message("значения по умолчанию — нажмите «сохранить»")

    # ------------------------------------------------- ScreenController
    def on_show(self) -> None:
        """Перезагружать профили при открытии экрана."""
        self._visible = True
        self.refresh()

    def on_hide(self) -> None:
        """Отказаться от несохранённых изменений."""
        self._visible = False

    def handle_key(self, event: tk.Event) -> bool:
        """Клавиши идут в поле ввода; ничего не обрабатывается.

        Args:
            event: Событие клавиши Tk.

        Returns:
            Всегда ``False``.
        """
        return False

    def handle_key_release(self, event: tk.Event) -> None:
        """Отпускание клавиш здесь не нужно.

        Args:
            event: Событие клавиши Tk.
        """

    def status_hint(self) -> str:
        """Подсказки экрана настроек.

        Returns:
            Текст подсказки.
        """
        return "тема и шрифт меняются сразу, остальное — после «сохранить»"
