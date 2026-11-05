from __future__ import annotations
"""Общее состояние запущенной программы: активный профиль.

Контроллеры подписываются на изменения (паттерн «Наблюдатель»): при
переключении профиля или сохранении его настроек каждый экран
перезагружает свои данные.
"""

import json
import logging
from collections.abc import Callable
from pathlib import Path

from keytrainer.data.models import User
from keytrainer.data.repositories import UserRepository
from keytrainer.data.seed import DEFAULT_USER_NAME

logger = logging.getLogger(__name__)


class AppState:
    """Активный профиль и файл с последним использованным профилем."""

    def __init__(self, users: UserRepository, settings_path: Path) -> None:
        """Загрузить последний активный профиль.

        Args:
            users: Репозиторий профилей.
            settings_path: ``settings.json`` рядом с базой данных.
        """
        self._users = users
        self._settings_path = settings_path
        self._listeners: list[Callable[[User], None]] = []
        self.user = self._load_user()

    def _read_settings(self) -> dict:
        """Прочитать ``settings.json``; повреждённый файл игнорируется.

        Returns:
            Словарь настроек.
        """
        try:
            return json.loads(self._settings_path.read_text("utf-8"))
        except (OSError, ValueError):
            return {}

    def _save_settings(self) -> None:
        """Запомнить активный профиль в ``settings.json``."""
        try:
            self._settings_path.write_text(
                json.dumps({"last_user_id": self.user.id}), "utf-8"
            )
        except OSError:
            logger.exception("Cannot save %s", self._settings_path)

    def _load_user(self) -> User:
        """Найти последний активный профиль, любой профиль или создать «Гость».

        Returns:
            Активный профиль.
        """
        last_id = self._read_settings().get("last_user_id")
        user = self._users.get_by_id(last_id) if isinstance(last_id, int) else None
        if user is None:
            users = self._users.get_all()
            user = users[0] if users else self._users.create(DEFAULT_USER_NAME, 1)
        return user

    def subscribe(self, callback: Callable[[User], None]) -> None:
        """Получать уведомления при смене активного профиля или его настроек.

        Args:
            callback: Функция, принимающая активный профиль.
        """
        self._listeners.append(callback)

    def _notify(self) -> None:
        """Вызвать всех подписчиков."""
        for callback in self._listeners:
            callback(self.user)

    def switch_user(self, user_id: int) -> None:
        """Сделать активным другой профиль.

        Args:
            user_id: Идентификатор профиля.

        Raises:
            ValueError: Если профиль не существует.
        """
        user = self._users.get_by_id(user_id)
        if user is None:
            raise ValueError(f"Profile {user_id} not found")
        self.user = user
        self._save_settings()
        self._notify()

    def reload_user(self) -> None:
        """Перечитать активный профиль после сохранения его настроек."""
        user = self._users.get_by_id(self.user.id)
        if user is not None:
            self.user = user
        self._notify()
