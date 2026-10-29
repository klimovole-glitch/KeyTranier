"""Controller of the settings screen: profile CRUD and personal settings."""

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
    """Edits a draft copy of the settings until "сохранить" is pressed."""

    def __init__(
        self,
        root: tk.Tk,
        view: SettingsScreen,
        state: AppState,
        profiles: ProfileService,
    ) -> None:
        """Connect the view with the profile service.

        Args:
            root: Tk root.
            view: Settings screen.
            state: Active profile.
            profiles: Profile service.
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
        """Show profiles and the saved settings of the active profile."""
        self.draft = replace(self.state.user)
        self.view.show_profiles(self.profiles.list_profiles(), self.state.user.id)
        self.view.show_draft(self.draft)

    # --------------------------------------------------------- profiles
    def create(self, name: str) -> None:
        """Create a profile from the entry.

        Args:
            name: Entered name.
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
        """Rename a profile in a dialog.

        Args:
            user_id: Profile id.
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
        """Make another profile active.

        Args:
            user_id: Profile id.
        """
        self.state.switch_user(user_id)
        self.view.show_message(f"активный профиль: {self.state.user.user_name}")

    def delete(self, user_id: int) -> None:
        """Delete a profile and its history after confirmation.

        Args:
            user_id: Profile id.
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

    # --------------------------------------------------------- settings
    def change_draft(self, **changes) -> None:
        """Change an edited setting (not saved yet).

        Args:
            **changes: Fields of :class:`User`.
        """
        self.draft = replace(self.draft, **changes)
        self.view.show_draft(self.draft)
        if "theme" in changes or "font_size" in changes:
            self._apply_appearance_later()

    def _apply_appearance_later(self) -> None:
        """Apply the theme and the font size a moment after the last change.

        The slider sends many values while it is dragged; only the last one
        is saved, so the window is not repainted dozens of times.
        """
        if self._appearance_job is not None:
            self.root.after_cancel(self._appearance_job)
        self._appearance_job = self.root.after(
            APPEARANCE_DELAY_MS, self._apply_appearance
        )

    def _apply_appearance(self) -> None:
        """Save the theme and the font size at once and repaint the window.

        Other edited settings stay in the draft until «сохранить».
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
        self.state.reload_user()  # repaints the window, refreshes this screen
        self.draft = pending
        self.view.show_draft(self.draft)

    def toggle(self, field: str) -> None:
        """Switch "вкл/выкл" settings.

        Args:
            field: ``show_finger_hint`` or ``auto_pause``.
        """
        self.change_draft(**{field: not getattr(self.draft, field)})

    def save(self) -> None:
        """Save the draft and apply it to the whole program."""
        try:
            self.profiles.save_settings(self.draft)
        except DataAccessError as error:
            self.view.show_message(str(error), is_error=True)
            return
        self.state.reload_user()
        self.view.show_message("настройки сохранены")

    def reset(self) -> None:
        """Put default values into the draft."""
        self.draft = self.profiles.with_defaults(self.draft)
        self.view.show_draft(self.draft)
        self._apply_appearance_later()
        self.view.show_message("значения по умолчанию — нажмите «сохранить»")

    # ------------------------------------------------- ScreenController
    def on_show(self) -> None:
        """Reload profiles when the screen is opened."""
        self._visible = True
        self.refresh()

    def on_hide(self) -> None:
        """Forget unsaved changes."""
        self._visible = False

    def handle_key(self, event: tk.Event) -> bool:
        """Keys go to the entry; nothing is consumed.

        Args:
            event: Tk key event.

        Returns:
            Always ``False``.
        """
        return False

    def handle_key_release(self, event: tk.Event) -> None:
        """Key releases are not needed here.

        Args:
            event: Tk key event.
        """

    def status_hint(self) -> str:
        """Hints of the settings screen.

        Returns:
            Hint text.
        """
        return "тема и шрифт меняются сразу, остальное — после «сохранить»"
