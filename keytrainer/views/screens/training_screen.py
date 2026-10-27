"""Training screen (Figma: рисунки 4-6, 11).

From top to bottom: exercise parameters, live metrics, exercise text with a
caret, next-key hint, on-screen keyboard, buttons and a message line.
The screen does not know how exercises are made: every action is reported
through a callback set by :class:`TrainingController`.
"""

import tkinter as tk
from collections.abc import Callable

from keytrainer.data.models import ExerciseMode, Key
from keytrainer.engine.exercise_generator import TIME_LIMITS, ExerciseParams
from keytrainer.engine.typing_session import SessionSnapshot
from keytrainer.labels import (
    KEY_LEVEL_TITLES,
    LAYOUT_TITLES,
    MODE_TITLES,
    format_duration,
    format_number,
)
from keytrainer.views.theme import ThemeManager
from keytrainer.views.widgets.keyboard_canvas import KeyboardCanvas
from keytrainer.views.widgets.metrics_panel import MetricsPanel
from keytrainer.views.widgets.text_button import TextButton

WORD_COUNTS = (10, 25, 50, 100, 200)
METRIC_CAPTIONS = {
    "wpm": "wpm",
    "cpm": "cpm",
    "errors": "ошибки",
    "error_rate": "% ошибок",
    "time": "время",
    "accuracy": "точность",
}
DECORATED_MODES = (ExerciseMode.WORDS, ExerciseMode.WEAK_KEYS)
TEXT_WIDTH_CHARS = 46
TEXT_LINES = 3


class TrainingScreen(tk.Frame):
    """Passive view of the training tab."""

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
        inner = theme.frame(self)
        inner.place(relx=0.5, rely=0.47, anchor="center")
        self._build_params(inner)
        self.metrics = MetricsPanel(inner, theme, METRIC_CAPTIONS)
        self.metrics.pack(pady=(26, 30))
        self._build_text(inner)
        self.hint = theme.label(inner, "", role="muted", font="small")
        self.hint.pack(pady=(18, 12))
        self.keyboard = KeyboardCanvas(inner, theme)
        self.keyboard.pack()
        self._build_buttons(inner)
        self.message = theme.label(inner, "", role="muted", font="small")
        self.message.pack(pady=(10, 0))
        self.show_metrics(None)

    # ------------------------------------------------------------ build
    def _emit(self, name: str, *args) -> None:
        """Call a controller callback if it is set.

        Args:
            name: Callback name.
            *args: Arguments.
        """
        callback = self.callbacks.get(name)
        if callback:
            callback(*args)

    def _build_params(self, parent: tk.Misc) -> None:
        """Create the row of exercise parameters.

        Args:
            parent: Container.
        """
        row = self.theme.frame(parent)
        row.pack()
        self.mode_button = TextButton(
            row,
            self.theme,
            "",
            lambda: self._popup(self._mode_menu, self.mode_button),
            role="text",
        )
        self.layout_button = TextButton(
            row, self.theme, "", lambda: self._emit("layout")
        )
        self.level_button = TextButton(
            row,
            self.theme,
            "",
            lambda: self._popup(self._level_menu, self.level_button),
        )
        self.length_button = TextButton(
            row,
            self.theme,
            "",
            lambda: self._popup(self._length_menu, self.length_button),
        )
        self.option_buttons = {
            name: TextButton(
                row, self.theme, title, lambda n=name: self._emit("toggle", n)
            )
            for name, title in (
                ("capitals", "заглавные"),
                ("digits", "цифры"),
                ("punctuation", "знаки"),
            )
        }
        self._param_widgets = [
            self.mode_button,
            self.layout_button,
            self.level_button,
            self.length_button,
            *self.option_buttons.values(),
        ]
        modes = [
            (MODE_TITLES[mode], lambda m=mode: self._emit("mode", m))
            for mode in ExerciseMode
        ]
        levels = [
            (f"{level}: {title}", lambda lv=level: self._emit("level", lv))
            for level, title in KEY_LEVEL_TITLES.items()
        ]
        lengths = [
            (f"{count} слов", lambda n=count: self._emit("length", n, None))
            for count in WORD_COUNTS
        ]
        lengths += [
            (f"{seconds} секунд", lambda s=seconds: self._emit("length", None, s))
            for seconds in TIME_LIMITS
        ]
        self._mode_menu = self._menu(modes)
        self._level_menu = self._menu(levels)
        self._length_menu = self._menu(lengths)

    def _menu(self, items: list[tuple[str, Callable]]) -> tk.Menu:
        """Create a themed drop-down menu.

        Args:
            items: Captions and commands.

        Returns:
            Menu ready for ``tk_popup``.
        """
        menu = tk.Menu(self, tearoff=False, bd=0, font=self.theme.fonts["ui"])
        self.theme.style(
            menu,
            bg="surface",
            fg="text",
            activebackground="surface_active",
            activeforeground="text",
        )
        for caption, command in items:
            menu.add_command(label=caption, command=command)
        return menu

    @staticmethod
    def _popup(menu: tk.Menu, anchor: tk.Widget) -> None:
        """Open a menu under a widget.

        Args:
            menu: Menu to open.
            anchor: Widget the menu is attached to.
        """
        menu.tk_popup(
            anchor.winfo_rootx(), anchor.winfo_rooty() + anchor.winfo_height()
        )

    def _build_text(self, parent: tk.Misc) -> None:
        """Create the exercise text area with a caret and a pause cover.

        Args:
            parent: Container.
        """
        holder = self.theme.frame(parent)
        holder.pack()
        self.text = tk.Text(
            holder,
            width=TEXT_WIDTH_CHARS,
            height=TEXT_LINES,
            wrap="word",
            bd=0,
            highlightthickness=0,
            cursor="arrow",
            font=self.theme.fonts["text"],
            spacing2=14,
            spacing3=14,
            takefocus=False,
        )
        self.theme.style(self.text, bg="bg", fg="dim", selectbackground="bg")
        self.text.pack()
        self.text.bind("<Button-1>", lambda _e: "break")
        self.caret = self.theme.frame(self.text, role="text", width=2)
        self.pause_cover = self.theme.label(
            holder,
            "пауза — нажмите любую клавишу или щелкните, чтобы продолжить",
            role="muted",
        )
        self.pause_cover.bind("<Button-1>", lambda _e: self._emit("resume"))
        self.theme.on_change(lambda _p: self._color_tags())
        self._color_tags()

    def _color_tags(self) -> None:
        """Set colors of the text tags from the palette."""
        palette = self.theme.palette
        self.text.tag_configure("correct", foreground=palette.text)
        self.text.tag_configure("error", foreground=palette.error)

    def _build_buttons(self, parent: tk.Misc) -> None:
        """Create the start, abort and new exercise buttons.

        Args:
            parent: Container.
        """
        row = self.theme.frame(parent)
        row.pack(pady=(30, 0))
        self.start_button = TextButton(
            row, self.theme, "старт", lambda: self._emit("start"), role="text"
        )
        self.abort_button = TextButton(
            row, self.theme, "прервать", lambda: self._emit("abort"), role="text"
        )
        self.new_button = TextButton(
            row, self.theme, "новое упражнение", lambda: self._emit("new"), role="text"
        )
        for column, button in enumerate(
            (self.start_button, self.abort_button, self.new_button)
        ):
            button.grid(row=0, column=column, padx=50)

    # ----------------------------------------------------------- update
    def show_params(self, params: ExerciseParams) -> None:
        """Show the chosen parameters.

        Args:
            params: Current exercise parameters.
        """
        self.mode_button.configure(text=MODE_TITLES[params.mode])
        self.layout_button.configure(text=LAYOUT_TITLES[params.layout_name])
        self.level_button.configure(text=f"уровень {params.level}")
        if params.time_limit_sec:
            self.length_button.configure(text=f"{params.time_limit_sec} с")
        else:
            self.length_button.configure(text=f"{params.word_count} слов")
        for name, button in self.option_buttons.items():
            button.set_state(selected=getattr(params, name))
        visible = {
            self.mode_button: True,
            self.layout_button: True,
            self.level_button: params.mode == ExerciseMode.KEYS,
            self.length_button: params.mode != ExerciseMode.CUSTOM,
        }
        for widget in self._param_widgets:
            widget.pack_forget()
        for widget in self._param_widgets:
            if visible.get(widget, params.mode in DECORATED_MODES):
                widget.pack(side="left", padx=18)

    def show_text(self, text: str) -> None:
        """Show a new exercise text, nothing typed yet.

        Args:
            text: Exercise text.
        """
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", text)
        self.text.configure(state="disabled")
        self.text.yview_moveto(0)
        self.move_caret(0)

    def mark(self, position: int, is_correct: bool | None) -> None:
        """Color one character after a key press or Backspace.

        Args:
            position: Index of the character.
            is_correct: ``True``/``False`` after a press, ``None`` after
                Backspace (back to "not typed").
        """
        index = f"1.0 + {position} chars"
        self.text.tag_remove("correct", index)
        self.text.tag_remove("error", index)
        if is_correct is not None:
            self.text.tag_add("correct" if is_correct else "error", index)

    def move_caret(self, position: int) -> None:
        """Move the caret before a character and scroll to its line.

        Args:
            position: Index of the next character.
        """
        index = f"1.0 + {position} chars"
        self.text.see(index)
        self.text.update_idletasks()
        box = self.text.bbox(index)
        if box:
            x, y, _w, height = box
            self.caret.place(x=x - 1, y=y, height=height)
        else:
            self.caret.place_forget()

    def show_metrics(self, snapshot: SessionSnapshot | None) -> None:
        """Show live metrics.

        Args:
            snapshot: Current metrics, ``None`` before the first key press.
        """
        if snapshot is None or snapshot.keystrokes == 0:
            values = dict(
                wpm="0",
                cpm="0",
                errors="0",
                error_rate="0 %",
                time="00:00",
                accuracy="—",
            )
        else:
            values = {
                "wpm": f"{snapshot.wpm:.0f}",
                "cpm": f"{snapshot.cpm:.0f}",
                "errors": str(snapshot.errors),
                "error_rate": f"{format_number(snapshot.error_rate)} %",
                "time": format_duration(snapshot.elapsed_sec),
                "accuracy": f"{format_number(snapshot.accuracy)} %",
            }
        self.metrics.set_values(values)

    def show_time_left(self, seconds_left: float) -> None:
        """Show the remaining time of a timed exercise instead of elapsed time.

        Args:
            seconds_left: Remaining seconds.
        """
        self.metrics.set_values({"time": format_duration(max(0.0, seconds_left))})

    def set_keyboard(self, keys: list[Key], show_digits: bool) -> None:
        """Draw the on-screen keyboard of the layout.

        Args:
            keys: Keys of the layout.
            show_digits: Whether the digit row is needed.
        """
        self.keyboard.set_keys(keys, show_digits)

    def show_next_key(self, key_char: str | None, finger: str | None) -> None:
        """Highlight the next key and show the finger hint.

        Args:
            key_char: Base character of the next key, ``None`` to hide.
            finger: Finger name in Russian, ``None`` to hide.
        """
        self.keyboard.highlight(key_char)
        if key_char is None or finger is None:
            self.hint.configure(text=" ")
        else:
            shown = "пробел" if key_char == " " else f"«{key_char}»"
            self.hint.configure(text=f"следующая клавиша {shown} — {finger}")

    def set_running(self, running: bool) -> None:
        """Switch buttons between "ready" and "exercise in progress".

        Args:
            running: ``True`` while the exercise is being typed.
        """
        self.start_button.configure(text="идёт…" if running else "старт")
        self.start_button.set_state(enabled=not running)
        self.abort_button.set_state(enabled=running)
        for widget in self._param_widgets:
            widget.set_state(enabled=not running)

    def show_pause(self, visible: bool) -> None:
        """Cover the text while the session is paused.

        Args:
            visible: ``True`` to show the pause cover.
        """
        if visible:
            self.pause_cover.place(relx=0.5, rely=0.5, anchor="center")
            self.pause_cover.lift()
        else:
            self.pause_cover.place_forget()

    def show_message(self, text: str, is_error: bool = False) -> None:
        """Show a short message under the buttons.

        Args:
            text: Message text, empty string to clear.
            is_error: Color the message as an error.
        """
        palette = self.theme.palette
        self.message.configure(
            text=text, fg=palette.error if is_error else palette.muted
        )
