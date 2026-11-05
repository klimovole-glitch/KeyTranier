from __future__ import annotations
"""Экран тренировки (Figma: рисунки 4-6, 11).

Сверху вниз: параметры упражнения, метрики в реальном времени, текст
упражнения с кареткой, подсказка следующей клавиши, экранная клавиатура,
кнопки и строка сообщения. Экран не знает, как создаются упражнения: каждое
действие передаётся через обратный вызов, который задаёт :class:`TrainingController`.

Анимации (Figma «СПЕЦИФИКАЦИЯ»): каретка мигает и скользит между буквами
за 0,09 с; после ошибки она краснеет на 0,26 с, а текст трясётся 0,22 с;
новый текст и пауза плавно появляются и исчезают.
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
from keytrainer.views.animation import (
    CARET_BLINK_MS,
    CARET_ERROR_MS,
    CARET_SLIDE_MS,
    FADE_MS,
    SHAKE_MS,
    Animator,
    linear,
    mix_colors,
    shake_offset,
)
from keytrainer.views.display import px
from keytrainer.views.theme import ThemeManager
from keytrainer.views.widgets.dropdown import Dropdown
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
SHAKE_PAD = 10
BLINK_AFTER_MS = 650
PAUSE_DIM = 0.22
MIN_SPEED_SEC = 2.0


class TrainingScreen(tk.Frame):
    """Пассивное представление вкладки тренировки."""

    def __init__(self, parent: tk.Misc, theme: ThemeManager) -> None:
        """Построить виджеты.

        Args:
            parent: Область содержимого главного окна.
            theme: Менеджер тем.
        """
        super().__init__(parent, bd=0)
        self.theme = theme
        theme.style(self, bg="bg")
        self.callbacks: dict[str, Callable] = {}
        self.animator = Animator(self)
        self._params: ExerciseParams | None = None
        self._text_alpha = 1.0
        self._caret_xy: tuple[int, int] | None = None
        inner = theme.frame(self)
        inner.place(relx=0.5, rely=0.47, anchor="center")
        self._build_params(inner)
        self.metrics = MetricsPanel(inner, theme, METRIC_CAPTIONS)
        self.metrics.pack(pady=px((26, 30)))
        self._build_text(inner)
        # под текстом и по его правому краю
        self.source = theme.label(self._holder, "", role="dim", font="small")
        self.source.pack(anchor="e", pady=px((4, 0)))
        self.hint = theme.label(inner, "", role="muted", font="small")
        self.hint.pack(pady=px((18, 12)))
        self.keyboard = KeyboardCanvas(inner, theme)
        self.keyboard.pack()
        self._build_buttons(inner)
        self.message = theme.label(inner, "", role="muted", font="small")
        self.message.pack(pady=px((10, 0)))
        self.show_metrics(None)

    # ------------------------------------------------------------ построение
    def _emit(self, name: str, *args) -> None:
        """Вызвать обратный вызов контроллера, если он задан.

        Args:
            name: Имя обратного вызова.
            *args: Аргументы.
        """
        callback = self.callbacks.get(name)
        if callback:
            callback(*args)

    def _build_params(self, parent: tk.Misc) -> None:
        """Создать строку параметров упражнения.

        Args:
            parent: Контейнер.
        """
        row = self.theme.frame(parent)
        row.pack()
        self.mode_button = TextButton(
            row,
            self.theme,
            "",
            lambda: self._popup(self._mode_items, self.mode_button, self._mode_title()),
            role="text",
        )
        self.layout_button = TextButton(
            row, self.theme, "", lambda: self._emit("layout")
        )
        self.level_button = TextButton(
            row,
            self.theme,
            "",
            lambda: self._popup(
                self._level_items, self.level_button, self._level_title()
            ),
        )
        self.length_button = TextButton(
            row,
            self.theme,
            "",
            lambda: self._popup(
                self._length_items, self.length_button, self._length_title()
            ),
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
        self._mode_items = modes
        self._level_items = levels
        self._length_items = lengths

    def _mode_title(self) -> str | None:
        """Подпись выбранного режима для галочки.

        Returns:
            Подпись или ``None`` до первого упражнения.
        """
        return MODE_TITLES[self._params.mode] if self._params else None

    def _level_title(self) -> str | None:
        """Подпись выбранного уровня клавиш.

        Returns:
            Подпись или ``None``.
        """
        if self._params is None:
            return None
        level = self._params.level
        return f"{level}: {KEY_LEVEL_TITLES.get(level, '')}"

    def _length_title(self) -> str | None:
        """Подпись выбранной длины.

        Returns:
            Подпись или ``None``.
        """
        if self._params is None:
            return None
        if self._params.time_limit_sec:
            return f"{self._params.time_limit_sec} секунд"
        return f"{self._params.word_count} слов"

    def _popup(
        self,
        items: list[tuple[str, Callable]],
        anchor: tk.Widget,
        selected: str | None,
    ) -> None:
        """Открыть выпадающий список под параметром.

        Args:
            items: Подписи и команды.
            anchor: Кнопка параметра.
            selected: Подпись текущего значения.
        """
        if getattr(anchor, "enabled", True):
            Dropdown(anchor, self.theme, items, selected).open()

    def _build_text(self, parent: tk.Misc) -> None:
        """Создать область текста упражнения с кареткой и крышкой паузы.

        Args:
            parent: Контейнер.
        """
        holder = self.theme.frame(parent)
        holder.pack(padx=px(SHAKE_PAD))
        self._holder = holder
        self.text = tk.Text(
            holder,
            width=TEXT_WIDTH_CHARS,
            height=TEXT_LINES,
            wrap="word",
            bd=0,
            highlightthickness=0,
            cursor="arrow",
            font=self.theme.fonts["text"],
            spacing2=px(14),
            spacing3=px(14),
            takefocus=False,
        )
        self.theme.style(self.text, bg="bg", fg="dim", selectbackground="bg")
        self.text.pack()
        self.text.bind("<Button-1>", lambda _e: "break")
        self.caret = tk.Frame(self.text, width=px(2), bd=0, highlightthickness=0)
        self.caret.configure(bg=self.theme.palette.text)
        self.pause_cover = self.theme.label(
            holder,
            "пауза · нажмите любую клавишу",
            role="muted",
        )
        self.pause_cover.bind("<Button-1>", lambda _e: self._emit("resume"))
        self.theme.on_change(lambda _p: self._color_tags())
        self._color_tags()

    def _color_tags(self) -> None:
        """Задать цвета текста и его тегов из палитры."""
        self._set_text_alpha(self._text_alpha)
        self.caret.configure(bg=self.theme.palette.text)

    def _set_text_alpha(self, alpha: float) -> None:
        """Смешать весь текст упражнения с фоном.

        Args:
            alpha: 1 — обычные цвета, 0 — невидимый.
        """
        self._text_alpha = alpha
        palette = self.theme.palette
        bg = palette.bg
        self.text.configure(fg=mix_colors(bg, palette.dim, alpha))
        self.text.tag_configure(
            "correct", foreground=mix_colors(bg, palette.text, alpha)
        )
        self.text.tag_configure(
            "error", foreground=mix_colors(bg, palette.error, alpha)
        )

    def _fade_text(self, end: float, duration_ms: int = FADE_MS, done=None) -> None:
        """Плавно показать или скрыть текст упражнения.

        Args:
            end: Конечная прозрачность.
            duration_ms: Длительность анимации.
            done: Вызывается в конце.
        """
        start = self._text_alpha
        self.animator.run(
            "text",
            duration_ms,
            lambda t: self._set_text_alpha(start + (end - start) * t),
            done,
        )

    def _build_buttons(self, parent: tk.Misc) -> None:
        """Создать кнопки старта, прерывания и нового упражнения.

        Args:
            parent: Контейнер.
        """
        row = self.theme.frame(parent)
        row.pack(pady=px((30, 0)))
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
            button.grid(row=0, column=column, padx=px(50))

    # ----------------------------------------------------------- обновление
    def show_params(self, params: ExerciseParams) -> None:
        """Показать выбранные параметры.

        Args:
            params: Текущие параметры упражнения.
        """
        self._params = params
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
                widget.pack(side="left", padx=px(18))

    def show_text(self, text: str) -> None:
        """Показать текст нового упражнения, пока ничего не набрано.

        Args:
            text: Текст упражнения.
        """
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", text)
        self.text.configure(state="disabled")
        self.text.yview_moveto(0)
        self._caret_xy = None
        self.move_caret(0)
        self._set_text_alpha(0.0)
        self._fade_text(1.0, 320)

    def show_source(self, source: str) -> None:
        """Показать автора и произведение под связным текстом.

        Args:
            source: Заголовок из библиотеки, например «Л. Н. Толстой - Война и мир»;
                пусто для других режимов.
        """
        self.source.configure(text=format_source(source))
        if source:
            palette = self.theme.palette
            self.animator.fade(
                "source", self.source, "fg", palette.bg, palette.dim, 600
            )

    def mark(self, position: int, is_correct: bool | None) -> None:
        """Раскрасить один символ после нажатия клавиши или Backspace.

        Args:
            position: Индекс символа.
            is_correct: ``True``/``False`` после нажатия, ``None`` после
                Backspace (возврат к «не набрано»).
        """
        index = f"1.0 + {position} chars"
        self.text.tag_remove("correct", index)
        self.text.tag_remove("error", index)
        if is_correct is not None:
            self.text.tag_add("correct" if is_correct else "error", index)

    def move_caret(self, position: int) -> None:
        """Переместить каретку перед символом и прокрутить до его строки.

        Внутри строки каретка скользит; на новой строке — прыгает.

        Args:
            position: Индекс следующего символа.
        """
        index = f"1.0 + {position} chars"
        self.text.see(index)
        self.text.update_idletasks()
        box = self.text.bbox(index)
        if not box:
            self.caret.place_forget()
            self._caret_xy = None
            return
        x, y, _w, height = box
        x -= 1
        old = self._caret_xy
        self._caret_xy = (x, y)
        self._caret_solid()
        if old is None or old[1] != y:
            self.animator.cancel("caret")
            self.caret.place(x=x, y=y, height=height)
            return
        start_x = old[0]
        self.animator.run(
            "caret",
            CARET_SLIDE_MS,
            lambda t: self.caret.place_configure(x=round(start_x + (x - start_x) * t)),
        )

    def _caret_solid(self) -> None:
        """Показывать каретку без мигания, пока пользователь печатает."""
        self.animator.cancel("blink")
        if not self.animator.is_running("caret_error"):
            self.caret.configure(bg=self.theme.palette.text)
        self.animator.later("blink_start", BLINK_AFTER_MS, self._start_blink)

    def _start_blink(self) -> None:
        """Мигать кареткой после паузы в наборе."""
        state = {"on": True}

        def tick() -> None:
            state["on"] = not state["on"]
            palette = self.theme.palette
            self.animator.fade(
                "caret_fade",
                self.caret,
                "bg",
                self.caret.cget("bg"),
                palette.text if state["on"] else palette.bg,
                160,
            )

        self.animator.repeat("blink", CARET_BLINK_MS, tick)

    def error_feedback(self) -> None:
        """Красная каретка на 0,26 с и короткая тряска текста (ошибка набора)."""
        palette = self.theme.palette
        self.animator.cancel("caret_fade")
        self.animator.fade(
            "caret_error", self.caret, "bg", palette.error, palette.text, CARET_ERROR_MS
        )
        holder = self._holder
        self.animator.run(
            "shake",
            SHAKE_MS,
            lambda t: holder.pack_configure(
                padx=(
                    px(SHAKE_PAD) + round(shake_offset(t, px(7))),
                    px(SHAKE_PAD) - round(shake_offset(t, px(7))),
                )
            ),
            done=lambda: holder.pack_configure(padx=px(SHAKE_PAD)),
            easing=linear,
        )

    def key_feedback(self, key_char: str | None, is_correct: bool) -> None:
        """Анимировать нажатую клавишу на клавиатуре.

        Args:
            key_char: Базовый символ нажатой клавиши.
            is_correct: Было ли нажатие правильным.
        """
        self.keyboard.press(key_char, is_correct)

    def show_metrics(self, snapshot: SessionSnapshot | None) -> None:
        """Показать метрики в реальном времени.

        Args:
            snapshot: Текущие метрики, ``None`` до первого нажатия.
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
            # в первые секунды 3 буквы за 0,5 с дают «120 wpm»;
            # скорость показывается, когда времени достаточно для измерения
            early = snapshot.elapsed_sec < MIN_SPEED_SEC
            values = {
                "wpm": "—" if early else f"{snapshot.wpm:.0f}",
                "cpm": "—" if early else f"{snapshot.cpm:.0f}",
                "errors": str(snapshot.errors),
                "error_rate": f"{format_number(snapshot.error_rate)} %",
                "time": format_duration(snapshot.elapsed_sec),
                "accuracy": f"{format_number(snapshot.accuracy)} %",
            }
        self.metrics.set_values(values)

    def show_time_left(self, seconds_left: float) -> None:
        """Показать оставшееся время упражнения на время вместо прошедшего.

        Args:
            seconds_left: Оставшиеся секунды.
        """
        self.metrics.set_values({"time": format_duration(max(0.0, seconds_left))})

    def set_keyboard(self, keys: list[Key], show_digits: bool) -> None:
        """Нарисовать экранную клавиатуру раскладки.

        Args:
            keys: Клавиши раскладки.
            show_digits: Нужен ли цифровой ряд.
        """
        self.keyboard.set_keys(keys, show_digits)

    def show_next_key(self, key_char: str | None, finger: str | None) -> None:
        """Подсветить следующую клавишу и показать подсказку пальца.

        Args:
            key_char: Базовый символ следующей клавиши, ``None`` — скрыть.
            finger: Название пальца по-русски, ``None`` — скрыть.
        """
        self.keyboard.highlight(key_char)
        if key_char is None or finger is None:
            self.hint.configure(text=" ")
        else:
            shown = "пробел" if key_char == " " else f"«{key_char}»"
            self.hint.configure(text=f"следующая клавиша {shown} — {finger}")

    def set_running(self, running: bool) -> None:
        """Переключить кнопки между «готово» и «упражнение идёт».

        Args:
            running: ``True``, пока набирается упражнение.
        """
        self.start_button.configure(text="идёт…" if running else "старт")
        self.start_button.set_state(enabled=not running)
        self.abort_button.set_state(enabled=running)
        for widget in self._param_widgets:
            widget.set_state(enabled=not running)

    def show_pause(self, visible: bool) -> None:
        """Закрыть текст, пока сессия на паузе.

        Args:
            visible: ``True``, чтобы показать крышку паузы.
        """
        palette = self.theme.palette
        if visible:
            self.animator.cancel("blink")
            self._fade_text(PAUSE_DIM)
            self.pause_cover.place(relx=0.5, rely=0.5, anchor="center")
            self.pause_cover.lift()
            self.animator.fade(
                "pause", self.pause_cover, "fg", palette.bg, palette.muted, 260
            )
        else:
            self.animator.cancel("pause")
            self.pause_cover.place_forget()
            self._fade_text(1.0)

    def show_message(self, text: str, is_error: bool = False) -> None:
        """Показать короткое сообщение под кнопками.

        Args:
            text: Текст сообщения, пустая строка — очистить.
            is_error: Окрасить сообщение как ошибку.
        """
        palette = self.theme.palette
        color = palette.error if is_error else palette.muted
        self.message.configure(text=text)
        if text:
            self.animator.fade("message", self.message, "fg", palette.bg, color, 240)
        else:
            self.animator.cancel("message")


def format_source(title: str) -> str:
    """Составить подпись к тексту по его заголовку в библиотеке.

    Args:
        title: «Автор - Произведение» или просто заголовок текста.

    Returns:
        «— Л. Н. Толстой, «Война и мир»», «Утро в городе» или "".
    """
    if not title:
        return ""
    author, sep, work = title.partition(" - ")
    if sep:
        return f"— {author}, «{work}»"
    return f"«{title}»"
