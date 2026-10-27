"""Shared state of the running program: the active profile.

Controllers subscribe to changes (pattern Observer): when the profile is
switched or its settings are saved, every screen reloads its data.
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
    """Active profile and the file with the last used profile."""

    def __init__(self, users: UserRepository, settings_path: Path) -> None:
        """Load the last active profile.

        Args:
            users: Profile repository.
            settings_path: ``settings.json`` next to the database.
        """
        self._users = users
        self._settings_path = settings_path
        self._listeners: list[Callable[[User], None]] = []
        self.user = self._load_user()

    def _read_settings(self) -> dict:
        """Read ``settings.json``; a broken file is ignored.

        Returns:
            Settings dictionary.
        """
        try:
            return json.loads(self._settings_path.read_text("utf-8"))
        except (OSError, ValueError):
            return {}

    def _save_settings(self) -> None:
        """Remember the active profile in ``settings.json``."""
        try:
            self._settings_path.write_text(
                json.dumps({"last_user_id": self.user.id}), "utf-8"
            )
        except OSError:
            logger.exception("Cannot save %s", self._settings_path)

    def _load_user(self) -> User:
        """Find the last active profile, any profile, or create "Гость".

        Returns:
            Active profile.
        """
        last_id = self._read_settings().get("last_user_id")
        user = self._users.get_by_id(last_id) if isinstance(last_id, int) else None
        if user is None:
            users = self._users.get_all()
            user = users[0] if users else self._users.create(DEFAULT_USER_NAME, 1)
        return user

    def subscribe(self, callback: Callable[[User], None]) -> None:
        """Get notified when the active profile or its settings change.

        Args:
            callback: Function receiving the active profile.
        """
        self._listeners.append(callback)

    def _notify(self) -> None:
        """Call all subscribers."""
        for callback in self._listeners:
            callback(self.user)

    def switch_user(self, user_id: int) -> None:
        """Make another profile active.

        Args:
            user_id: Profile id.

        Raises:
            ValueError: If the profile does not exist.
        """
        user = self._users.get_by_id(user_id)
        if user is None:
            raise ValueError(f"Profile {user_id} not found")
        self.user = user
        self._save_settings()
        self._notify()

    def reload_user(self) -> None:
        """Re-read the active profile after its settings were saved."""
        user = self._users.get_by_id(self.user.id)
        if user is not None:
            self.user = user
        self._notify()
