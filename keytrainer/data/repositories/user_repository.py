from __future__ import annotations
"""Репозиторий для ``tbl_users`` (профили, ТЗ, п. 4.2.1 «Профили (CRUD)»)."""

import sqlite3
from datetime import datetime

from keytrainer.data.exceptions import DuplicateNameError, ValidationError
from keytrainer.data.models import ExerciseMode, Theme, User
from keytrainer.data.repositories.base import BaseRepository

MAX_NAME_LENGTH = 30


class UserRepository(BaseRepository[User]):
    """Операции CRUD для профилей пользователей и их настроек."""

    table = "tbl_users"

    def _to_entity(self, row: sqlite3.Row) -> User:
        """Преобразовать строку в :class:`User`.

        Args:
            row: Строка ``tbl_users``.

        Returns:
            Сущность пользователя.
        """
        return User(
            id=row["id"],
            user_name=row["user_name"],
            layout_id=row["layout_id"],
            theme=Theme(row["theme"]),
            font_size=row["font_size"],
            default_mode=ExerciseMode(row["default_mode"]),
            show_finger_hint=bool(row["show_finger_hint"]),
            auto_pause=bool(row["auto_pause"]),
            created_at=row["created_at"],
        )

    @staticmethod
    def validate_name(user_name: str) -> str:
        """Проверить имя профиля.

        Args:
            user_name: Имя, введённое пользователем.

        Returns:
            Имя без пробелов в начале и в конце.

        Raises:
            ValidationError: Если имя пустое или слишком длинное.
        """
        user_name = user_name.strip()
        if not user_name:
            raise ValidationError("Имя профиля не может быть пустым")
        if len(user_name) > MAX_NAME_LENGTH:
            raise ValidationError(f"Имя профиля длиннее {MAX_NAME_LENGTH} символов")
        return user_name

    def create(self, user_name: str, layout_id: int | None = None) -> User:
        """Создать профиль с настройками по умолчанию.

        Args:
            user_name: Уникальное имя профиля.
            layout_id: Раскладка профиля по умолчанию.

        Returns:
            Созданный профиль.

        Raises:
            ValidationError: Если имя недопустимо.
            DuplicateNameError: Если имя уже занято.
        """
        user_name = self.validate_name(user_name)
        created_at = datetime.now().isoformat(timespec="seconds")
        try:
            cursor = self._execute(
                "INSERT INTO tbl_users (user_name, layout_id, created_at) "
                "VALUES (?, ?, ?)",
                (user_name, layout_id, created_at),
            )
        except sqlite3.IntegrityError as error:
            raise DuplicateNameError(f"Профиль «{user_name}» уже существует") from error
        return self.get_by_id(cursor.lastrowid)

    def get_by_name(self, user_name: str) -> User | None:
        """Найти профиль по имени.

        Args:
            user_name: Имя профиля.

        Returns:
            Профиль или ``None``.
        """
        return self._fetch_one(
            "SELECT * FROM tbl_users WHERE user_name = ?", (user_name.strip(),)
        )

    def rename(self, user_id: int, new_name: str) -> bool:
        """Переименовать профиль.

        Args:
            user_id: Идентификатор профиля.
            new_name: Новое уникальное имя.

        Returns:
            ``True``, если профиль переименован.

        Raises:
            ValidationError: Если имя недопустимо.
            DuplicateNameError: Если имя уже занято.
        """
        new_name = self.validate_name(new_name)
        try:
            cursor = self._execute(
                "UPDATE tbl_users SET user_name = ? WHERE id = ?", (new_name, user_id)
            )
        except sqlite3.IntegrityError as error:
            raise DuplicateNameError(f"Профиль «{new_name}» уже существует") from error
        return cursor.rowcount > 0

    def update_settings(self, user: User) -> bool:
        """Сохранить личные настройки профиля.

        Args:
            user: Профиль с изменёнными настройками.

        Returns:
            ``True``, если профиль обновлён.
        """
        cursor = self._execute(
            "UPDATE tbl_users SET layout_id = ?, theme = ?, font_size = ?, "
            "default_mode = ?, show_finger_hint = ?, auto_pause = ? WHERE id = ?",
            (
                user.layout_id,
                Theme(user.theme).value,
                user.font_size,
                ExerciseMode(user.default_mode).value,
                int(user.show_finger_hint),
                int(user.auto_pause),
                user.id,
            ),
        )
        return cursor.rowcount > 0
