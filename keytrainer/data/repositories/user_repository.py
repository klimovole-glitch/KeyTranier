"""Repository for ``tbl_users`` (profiles, ТЗ, п. 4.2.1 «Профили (CRUD)»)."""

import sqlite3
from datetime import datetime

from keytrainer.data.exceptions import DuplicateNameError, ValidationError
from keytrainer.data.models import ExerciseMode, Theme, User
from keytrainer.data.repositories.base import BaseRepository

MAX_NAME_LENGTH = 30


class UserRepository(BaseRepository[User]):
    """CRUD operations for user profiles and their settings."""

    table = "tbl_users"

    def _to_entity(self, row: sqlite3.Row) -> User:
        """Convert a row to :class:`User`.

        Args:
            row: Row of ``tbl_users``.

        Returns:
            User entity.
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
        """Check a profile name.

        Args:
            user_name: Name typed by the user.

        Returns:
            Name without leading and trailing spaces.

        Raises:
            ValidationError: If the name is empty or too long.
        """
        user_name = user_name.strip()
        if not user_name:
            raise ValidationError("Имя профиля не может быть пустым")
        if len(user_name) > MAX_NAME_LENGTH:
            raise ValidationError(f"Имя профиля длиннее {MAX_NAME_LENGTH} символов")
        return user_name

    def create(self, user_name: str, layout_id: int | None = None) -> User:
        """Create a profile with default settings.

        Args:
            user_name: Unique profile name.
            layout_id: Default layout of the profile.

        Returns:
            Created profile.

        Raises:
            ValidationError: If the name is invalid.
            DuplicateNameError: If the name is already taken.
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
        """Find a profile by name.

        Args:
            user_name: Profile name.

        Returns:
            Profile or ``None``.
        """
        return self._fetch_one(
            "SELECT * FROM tbl_users WHERE user_name = ?", (user_name.strip(),)
        )

    def rename(self, user_id: int, new_name: str) -> bool:
        """Rename a profile.

        Args:
            user_id: Profile id.
            new_name: New unique name.

        Returns:
            ``True`` if the profile was renamed.

        Raises:
            ValidationError: If the name is invalid.
            DuplicateNameError: If the name is already taken.
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
        """Save personal settings of a profile.

        Args:
            user: Profile with changed settings.

        Returns:
            ``True`` if the profile was updated.
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
