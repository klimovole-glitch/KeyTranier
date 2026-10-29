"""Settings and profiles screen (Figma: рисунок 10)."""

import tkinter as tk
from collections.abc import Callable

from keytrainer.data.keyboard_layouts import LAYOUT_EN, LAYOUT_IDS, LAYOUT_RU
from keytrainer.data.models import ExerciseMode, Theme, User
from keytrainer.engine.profile_service import FONT_SIZE_RANGE, ProfileInfo
from keytrainer.labels import LAYOUT_SHORT, LAYOUT_TITLES, MODE_TITLES, plural
from keytrainer.views.animation import Animator
from keytrainer.views.theme import ThemeManager
from keytrainer.views.widgets.dropdown import Dropdown
from keytrainer.views.widgets.message import show_animated_message
from keytrainer.views.widgets.slider import Slider
from keytrainer.views.widgets.text_button import TextButton

LAYOUT_BY_ID = {layout_id: name for name, layout_id in LAYOUT_IDS.items()}


class SettingsScreen(tk.Frame):
    """Passive view: profiles list, new profile, appearance and defaults."""

    def __init__(self, parent: tk.Misc, theme: ThemeManager) -> None:
        """Build the widgets.

        Args:
            parent: Content area of the main window.
            theme: Theme manager.
        """
        super().__init__(parent, bd=0)
        self.theme = theme
        theme.style(self, bg="bg")
        self.callbacks: dict[str, Callable] = {}
        body = theme.frame(self)
        body.place(relx=0.08, rely=0.04, relwidth=0.84, relheight=0.92)
        theme.label(body, "настройки", font="title").pack(anchor="w", pady=(0, 24))
        self._section(body, "профили")
        self.profiles = theme.frame(body)
        self.profiles.pack(anchor="w", fill="x")
        self._build_new_profile(body)
        self._section(body, "внешний вид")
        self._build_appearance(body)
        self._section(body, "по умолчанию")
        self._build_defaults(body)
        bottom = theme.frame(body)
        bottom.pack(fill="x", pady=(24, 0))
        TextButton(bottom, theme, "сбросить", lambda: self._emit("reset")).pack(
            side="right", padx=(40, 60)
        )
        TextButton(
            bottom, theme, "сохранить", lambda: self._emit("save"), role="text"
        ).pack(side="right")
        self.message = theme.label(bottom, "", role="muted", font="small")
        self.message.pack(side="left")

    # ------------------------------------------------------------ build
    def _emit(self, name: str, *args, **kwargs) -> None:
        """Call a controller callback.

        Args:
            name: Callback name.
            *args: Positional arguments.
            **kwargs: Named arguments (changed settings).
        """
        callback = self.callbacks.get(name)
        if callback:
            callback(*args, **kwargs)

    def _section(self, parent: tk.Misc, caption: str) -> None:
        """Small grey section caption.

        Args:
            parent: Container.
            caption: Caption text.
        """
        self.theme.label(parent, caption, role="muted", font="tiny").pack(
            anchor="w", pady=(22, 8)
        )

    def _row(self, parent: tk.Misc, caption: str) -> tk.Frame:
        """Row "caption   controls".

        Args:
            parent: Container.
            caption: Left caption.

        Returns:
            Frame for the controls.
        """
        row = self.theme.frame(parent)
        row.pack(anchor="w", pady=3)
        self.theme.label(row, caption, role="muted", width=20, anchor="w").pack(
            side="left"
        )
        return row

    def _build_new_profile(self, parent: tk.Misc) -> None:
        """Entry for the name of a new profile.

        Args:
            parent: Container.
        """
        self.theme.label(parent, "имя нового профиля", role="muted", font="tiny").pack(
            anchor="w", pady=(18, 4)
        )
        row = self.theme.frame(parent)
        row.pack(anchor="w")
        field = self.theme.frame(row)
        field.pack(side="left")
        self.name_entry = tk.Entry(
            field, width=28, bd=0, highlightthickness=0, font=self.theme.fonts["ui"]
        )
        self.theme.style(self.name_entry, bg="bg", fg="text", insertbackground="text")
        self.name_entry.pack(ipady=4)
        self.name_line = tk.Frame(field, height=1, bd=0)
        self.name_line.configure(bg=self.theme.palette.border)
        self.name_line.pack(fill="x")
        self._line_animator = Animator(self.name_line)
        self._name_error = False
        self.name_entry.bind("<FocusIn>", lambda _e: self._underline(True))
        self.name_entry.bind("<FocusOut>", lambda _e: self._underline(False))
        self.theme.on_change(lambda _p: self._underline(False, animate=False))
        self.name_entry.bind("<Return>", lambda _e: self._create())
        TextButton(row, self.theme, "создать профиль", self._create, role="text").pack(
            side="left", padx=30
        )
        self.name_error = self.theme.label(parent, "", role="error", font="tiny")
        self.name_error.pack(anchor="w", pady=(4, 0))

    def _underline(self, focused: bool, animate: bool = True) -> None:
        """Color the line under the name entry (states «фокус» and «ошибка»).

        Args:
            focused: Whether the entry has the keyboard focus.
            animate: Change the color smoothly.
        """
        palette = self.theme.palette
        if self._name_error:
            color = palette.error
        else:
            color = palette.text if focused else palette.border
        if animate:
            self._line_animator.fade(
                "line", self.name_line, "bg", self.name_line.cget("bg"), color, 180
            )
        else:
            self.name_line.configure(bg=color)

    def _create(self) -> None:
        """Report the entered name to the controller."""
        self._emit("create", self.name_entry.get())

    def _build_appearance(self, parent: tk.Misc) -> None:
        """Theme switch and font size slider.

        Args:
            parent: Container.
        """
        row = self._row(parent, "тема")
        self.theme_buttons = {}
        for value, title in ((Theme.LIGHT, "светлая"), (Theme.DARK, "тёмная")):
            button = TextButton(
                row, self.theme, title, lambda v=value: self._emit("draft", theme=v)
            )
            button.pack(side="left", padx=10)
            self.theme_buttons[value] = button
        row = self._row(parent, "размер шрифта")
        self.font_label = self.theme.label(row, "", width=6, anchor="w")
        self.font_label.pack(side="left", padx=10)
        low, high = FONT_SIZE_RANGE
        self.font_scale = Slider(
            row,
            self.theme,
            low,
            high,
            lambda v: self._emit("draft", font_size=v),
        )
        self.font_scale.pack(side="left", pady=(10, 0))

    def _build_defaults(self, parent: tk.Misc) -> None:
        """Default layout, mode, finger hint and auto-pause.

        Args:
            parent: Container.
        """
        row = self._row(parent, "раскладка")
        self.layout_buttons = {}
        for name in (LAYOUT_RU, LAYOUT_EN):
            button = TextButton(
                row,
                self.theme,
                LAYOUT_SHORT[name],
                lambda n=name: self._emit("draft", layout_id=LAYOUT_IDS[n]),
            )
            button.pack(side="left", padx=10)
            self.layout_buttons[name] = button
        row = self._row(parent, "режим")
        self.mode_button = TextButton(row, self.theme, "", self._mode_menu, role="text")
        self.mode_button.pack(side="left", padx=10)
        self._mode_items = [
            (MODE_TITLES[mode], lambda m=mode: self._emit("draft", default_mode=m))
            for mode in (ExerciseMode.KEYS, ExerciseMode.WORDS, ExerciseMode.TEXT)
        ]
        self.switches = {}
        for field, caption in (
            ("show_finger_hint", "подсказка пальцев"),
            ("auto_pause", "автопауза"),
        ):
            row = self._row(parent, caption)
            button = TextButton(
                row,
                self.theme,
                "",
                lambda f=field: self._emit("switch", f),
                role="text",
            )
            button.pack(side="left", padx=10)
            self.switches[field] = button

    def _mode_menu(self) -> None:
        """Open the list of default modes."""
        current = self.mode_button.cget("text")
        Dropdown(self.mode_button, self.theme, self._mode_items, current).open()

    # ----------------------------------------------------------- update
    def show_profiles(self, profiles: list[ProfileInfo], active_id: int) -> None:
        """Draw the list of profiles with their actions.

        Args:
            profiles: Profiles with session counts.
            active_id: Id of the active profile.
        """
        for child in self.profiles.winfo_children():
            child.destroy()
        for info in profiles:
            user = info.user
            active = user.id == active_id
            row = self.theme.frame(self.profiles)
            row.pack(anchor="w", fill="x", pady=4)
            self.theme.label(
                row,
                user.user_name,
                role="text" if active else "muted",
                font="title",
                width=14,
                anchor="w",
            ).pack(side="left")
            layout = LAYOUT_TITLES[LAYOUT_BY_ID.get(user.layout_id or 1, LAYOUT_RU)]
            sessions = plural(info.sessions_count, "сессия", "сессии", "сессий")
            details = "активен" if active else f"{layout} · {sessions}"
            self.theme.label(
                row,
                details,
                role="success" if active else "dim",
                font="tiny",
                width=30,
                anchor="w",
            ).pack(side="left")
            actions = [("переименовать", "rename", "muted")]
            if not active:
                actions = [("переключить", "switch_user", "muted")] + actions
                actions.append(("удалить", "delete", "error"))
            for caption, event, role in actions:
                TextButton(
                    row,
                    self.theme,
                    caption,
                    lambda e=event, i=user.id: self._emit(e, i),
                    role=role,
                    hover_role="text" if role != "error" else "error",
                ).pack(side="left", padx=14)

    def show_draft(self, user: User) -> None:
        """Show settings that are being edited (not saved yet).

        Args:
            user: Profile copy with edited settings.
        """
        for value, button in self.theme_buttons.items():
            button.set_state(selected=user.theme == value)
        self.font_label.configure(text=f"{user.font_size} px")
        if self.font_scale.get() != user.font_size:
            self.font_scale.set(user.font_size)
        layout = LAYOUT_BY_ID.get(user.layout_id or 1, LAYOUT_RU)
        for name, button in self.layout_buttons.items():
            button.set_state(selected=name == layout)
        self.mode_button.configure(text=MODE_TITLES[user.default_mode])
        for field, button in self.switches.items():
            button.configure(text="вкл" if getattr(user, field) else "выкл")

    def clear_new_name(self) -> None:
        """Empty the new profile entry."""
        self.name_entry.delete(0, "end")
        self.name_error.configure(text="")
        self._name_error = False
        self._underline(False)

    def show_name_error(self, text: str) -> None:
        """Show a validation error under the entry (state "ошибка").

        Args:
            text: Error text.
        """
        self.name_error.configure(text=text)
        self._name_error = True
        self._underline(True)
        show_animated_message(self.name_error, self.theme, text, is_error=True)

    def show_message(self, text: str, is_error: bool = False) -> None:
        """Show a message next to the buttons.

        Args:
            text: Message.
            is_error: Color as an error.
        """
        show_animated_message(self.message, self.theme, text, is_error)
