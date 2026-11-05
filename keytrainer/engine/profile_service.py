from __future__ import annotations
"""Бизнес-правила профилей (ТЗ, п. 4.2.1 «Профили (CRUD)»)."""

from dataclasses import dataclass, replace

from keytrainer.data.exceptions import NotFoundError, ValidationError
from keytrainer.data.models import ExerciseMode, Theme, User
from keytrainer.data.repositories import SessionRepository, UserRepository

DEFAULT_SETTINGS = {
    "layout_id": 1,
    "theme": Theme.LIGHT,
    "font_size": 18,
    "default_mode": ExerciseMode.WORDS,
    "show_finger_hint": True,
    "auto_pause": True,
}
FONT_SIZE_RANGE = (14, 32)


@dataclass(frozen=True)
class ProfileInfo:
    """Профиль с количеством его сессий."""

    user: User
    sessions_count: int


class ProfileService:
    """Создаёт, переименовывает, удаляет профили и сохраняет их настройки."""

    def __init__(self, users: UserRepository, sessions: SessionRepository) -> None:
        """Сохранить репозитории.

        Args:
            users: Репозиторий профилей.
            sessions: Репозиторий сессий (для подсчётов).
        """
        self._users = users
        self._sessions = sessions

    def list_profiles(self) -> list[ProfileInfo]:
        """Прочитать все профили с количеством их сессий.

        Returns:
            Профили в порядке создания.
        """
        return [
            ProfileInfo(user, self._sessions.count_by_user(user.id))
            for user in self._users.get_all()
        ]

    def create(self, user_name: str, layout_id: int) -> User:
        """Создать профиль.

        Args:
            user_name: Имя, введённое пользователем.
            layout_id: Раскладка по умолчанию.

        Returns:
            Новый профиль.
        """
        return self._users.create(user_name, layout_id)

    def rename(self, user_id: int, new_name: str) -> None:
        """Переименовать профиль.

        Args:
            user_id: Идентификатор профиля.
            new_name: Новое имя.

        Raises:
            NotFoundError: Если профиль не существует.
        """
        if not self._users.rename(user_id, new_name):
            raise NotFoundError("Профиль не найден")

    def delete(self, user_id: int, active_id: int) -> int:
        """Удалить профиль вместе с его историей.

        Args:
            user_id: Удаляемый профиль.
            active_id: Текущий активный профиль.

        Returns:
            Идентификатор профиля, который должен стать активным после удаления.

        Raises:
            ValidationError: Если это последний профиль.
        """
        profiles = self._users.get_all()
        if len(profiles) <= 1:
            raise ValidationError("Нельзя удалить единственный профиль")
        self._users.delete(user_id)
        if user_id != active_id:
            return active_id
        return next(u.id for u in profiles if u.id != user_id)

    def save_settings(self, user: User) -> None:
        """Проверить и сохранить личные настройки.

        Args:
            user: Профиль с новыми настройками.

        Raises:
            ValidationError: Если размер шрифта вне допустимого диапазона.
        """
        low, high = FONT_SIZE_RANGE
        if not low <= user.font_size <= high:
            raise ValidationError(f"Размер шрифта должен быть от {low} до {high}")
        self._users.update_settings(user)

    @staticmethod
    def with_defaults(user: User) -> User:
        """Вернуть копию профиля с настройками по умолчанию.

        Args:
            user: Профиль.

        Returns:
            Копия с настройками нового профиля.
        """
        return replace(user, **DEFAULT_SETTINGS)
