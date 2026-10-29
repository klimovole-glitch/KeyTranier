"""Business rules of profiles (ТЗ, п. 4.2.1 «Профили (CRUD)»)."""

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
    """A profile with the number of its sessions."""

    user: User
    sessions_count: int


class ProfileService:
    """Create, rename, delete profiles and save their settings."""

    def __init__(self, users: UserRepository, sessions: SessionRepository) -> None:
        """Store repositories.

        Args:
            users: Profile repository.
            sessions: Session repository (for counts).
        """
        self._users = users
        self._sessions = sessions

    def list_profiles(self) -> list[ProfileInfo]:
        """Read all profiles with their session counts.

        Returns:
            Profiles in creation order.
        """
        return [
            ProfileInfo(user, self._sessions.count_by_user(user.id))
            for user in self._users.get_all()
        ]

    def create(self, user_name: str, layout_id: int) -> User:
        """Create a profile.

        Args:
            user_name: Name typed by the user.
            layout_id: Default layout.

        Returns:
            New profile.
        """
        return self._users.create(user_name, layout_id)

    def rename(self, user_id: int, new_name: str) -> None:
        """Rename a profile.

        Args:
            user_id: Profile id.
            new_name: New name.

        Raises:
            NotFoundError: If the profile does not exist.
        """
        if not self._users.rename(user_id, new_name):
            raise NotFoundError("Профиль не найден")

    def delete(self, user_id: int, active_id: int) -> int:
        """Delete a profile with its history.

        Args:
            user_id: Profile to delete.
            active_id: Currently active profile.

        Returns:
            Id of the profile that must be active after deletion.

        Raises:
            ValidationError: If it is the last profile.
        """
        profiles = self._users.get_all()
        if len(profiles) <= 1:
            raise ValidationError("Нельзя удалить единственный профиль")
        self._users.delete(user_id)
        if user_id != active_id:
            return active_id
        return next(u.id for u in profiles if u.id != user_id)

    def save_settings(self, user: User) -> None:
        """Validate and save personal settings.

        Args:
            user: Profile with new settings.

        Raises:
            ValidationError: If the font size is out of range.
        """
        low, high = FONT_SIZE_RANGE
        if not low <= user.font_size <= high:
            raise ValidationError(f"Размер шрифта должен быть от {low} до {high}")
        self._users.update_settings(user)

    @staticmethod
    def with_defaults(user: User) -> User:
        """Return a copy of a profile with default settings.

        Args:
            user: Profile.

        Returns:
            Copy with the settings of a new profile.
        """
        return replace(user, **DEFAULT_SETTINGS)
