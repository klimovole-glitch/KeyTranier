from __future__ import annotations
"""Экранная клавиатура, нарисованная на Canvas по координатам из ``tbl_keys``.

Клавиатура рисуется один раз; затем перекрашиваются только изменившиеся
клавиши (без полной перерисовки на каждое нажатие), а цвета меняются плавно.
Figma «СПЕЦИФИКАЦИЯ»: наведение — фон 6 %, нажатие — фон 10 % и
масштаб 0,96 на 0,1 с, следующая клавиша — фон 12 % с более яркой рамкой,
ошибка — приглушённый красный.
"""

import tkinter as tk

from keytrainer.data.keyboard_layouts import SPACE_CHAR
from keytrainer.data.models import Key
from keytrainer.views.animation import KEY_PRESS_MS, Animator, ease_in_out, mix_colors
from keytrainer.views.display import px
from keytrainer.views.theme import Palette, ThemeManager

SPACE_WIDTH_UNITS = 6
HIGHLIGHT_MS = 140
FLASH_MS = 320
PRESS_SCALE = 0.96
HOVER_MIX = 0.06


def rounded_rect(
    canvas: tk.Canvas, x0: float, y0: float, x1: float, y1: float, radius: float, **kw
) -> int:
    """Нарисовать прямоугольник со скруглёнными углами.

    Args:
        canvas: Целевой холст.
        x0: Левый край.
        y0: Верхний край.
        x1: Правый край.
        y1: Нижний край.
        radius: Радиус угла.
        **kw: Параметры полигона Canvas (fill, outline, tags...).

    Returns:
        Идентификатор элемента холста.
    """
    points = [
        x0 + radius,
        y0,
        x1 - radius,
        y0,
        x1,
        y0,
        x1,
        y0 + radius,
        x1,
        y1 - radius,
        x1,
        y1,
        x1 - radius,
        y1,
        x0 + radius,
        y1,
        x0,
        y1,
        x0,
        y1 - radius,
        x0,
        y0 + radius,
        x0,
        y0,
    ]
    return canvas.create_polygon(points, smooth=True, **kw)


class KeyboardCanvas(tk.Canvas):
    """Клавиатура с подсвеченной следующей клавишей (ТЗ, п. 4.1.6)."""

    key_size = 46
    gap = 7
    padding = 4
    radius = 9

    def __init__(self, parent: tk.Misc, theme: ThemeManager) -> None:
        """Создать пустую клавиатуру.

        Args:
            parent: Родительский виджет.
            theme: Менеджер тем.
        """
        super().__init__(parent, bd=0, highlightthickness=0)
        cls = type(self)
        # размеры макета, пересчитанные в пиксели экрана (экраны с высоким DPI)
        self.key_size = px(cls.key_size)
        self.gap = px(cls.gap)
        self.padding = px(cls.padding)
        self.radius = px(cls.radius)
        self.theme = theme
        theme.style(self, bg="bg")
        theme.on_change(lambda _p: self.redraw())
        self._keys: list[Key] = []
        self._show_digits = False
        self._highlighted: str | None = None
        self._shapes: dict[str, int] = {}
        self._texts: dict[str, list[int]] = {}
        self._fills: dict[str, str] = {}
        self._by_char: dict[str, Key] = {}
        self._boxes: dict[str, tuple[float, float, float, float]] = {}
        self._hovered: str | None = None
        self._scales: dict[str, float] = {}
        self.animator = Animator(self)
        self.tag_bind("key", "<Enter>", self._on_enter, add="+")
        self.tag_bind("key", "<Leave>", self._on_leave, add="+")

    @property
    def unit(self) -> int:
        """Расстояние между соседними клавишами в пикселях."""
        return self.key_size + self.gap

    def set_keys(self, keys: list[Key], show_digits: bool = False) -> None:
        """Задать рисуемую раскладку.

        Args:
            keys: Клавиши раскладки.
            show_digits: Рисовать цифровой ряд (упражнения с цифрами).
        """
        self._keys = keys
        self._show_digits = show_digits
        self.redraw()

    def visible_keys(self) -> list[Key]:
        """Рисуемые клавиши (цифровой ряд необязателен).

        Returns:
            Клавиши для отрисовки.
        """
        return [k for k in self._keys if self._show_digits or k.row_num != 0]

    def key_box(self, key: Key) -> tuple[float, float, float, float]:
        """Вычислить прямоугольник клавиши.

        Args:
            key: Размещаемая клавиша.

        Returns:
            Координаты ``x0, y0, x1, y1``.
        """
        keys = self.visible_keys()
        min_x = min(k.pos_x for k in keys)
        min_y = min(k.pos_y for k in keys)
        x0 = self.padding + (key.pos_x - min_x) * self.unit
        y0 = self.padding + (key.pos_y - min_y) * self.unit
        units = SPACE_WIDTH_UNITS if key.key_char == SPACE_CHAR else 1
        width = units * self.unit - self.gap
        return x0, y0, x0 + width, y0 + self.key_size

    def key_fill(self, key: Key, palette: Palette) -> str:
        """Выбрать цвет заливки клавиши (переопределяется тепловой картой).

        Args:
            key: Красимая клавиша.
            palette: Текущая палитра.

        Returns:
            Шестнадцатеричный цвет.
        """
        if key.key_char == self._highlighted:
            return palette.surface_active
        return palette.surface

    def draw_key_text(self, key: Key, box: tuple, palette: Palette) -> None:
        """Нарисовать подпись клавиши (переопределяется тепловой картой).

        Args:
            key: Клавиша.
            box: Прямоугольник клавиши.
            palette: Текущая палитра.
        """
        x0, y0, x1, y1 = box
        self.create_text(
            (x0 + x1) / 2,
            (y0 + y1) / 2,
            text=key.key_char,
            fill=self.key_text_color(key, palette),
            font=self.theme.fonts["key"],
            tags=("key", f"key:{ord(key.key_char)}"),
        )

    def key_text_color(self, key: Key, palette: Palette) -> str:
        """Выбрать цвет подписи клавиши.

        Args:
            key: Клавиша.
            palette: Текущая палитра.

        Returns:
            Шестнадцатеричный цвет.
        """
        return palette.text if key.key_char == self._highlighted else palette.muted

    def key_outline(self, key: Key, palette: Palette) -> str:
        """Выбрать цвет рамки клавиши.

        Args:
            key: Клавиша.
            palette: Текущая палитра.

        Returns:
            Шестнадцатеричный цвет.
        """
        return palette.muted if key.key_char == self._highlighted else palette.border

    def redraw(self) -> None:
        """Заново нарисовать все видимые клавиши (раскладка или тема изменились)."""
        self.animator.cancel_all()
        self.delete("all")
        self._shapes.clear()
        self._texts.clear()
        self._fills.clear()
        self._by_char.clear()
        self._boxes.clear()
        self._scales.clear()
        keys = self.visible_keys()
        if not keys:
            return
        palette = self.theme.palette
        right = bottom = 0.0
        for key in keys:
            box = self.key_box(key)
            char = key.key_char
            fill = self.key_fill(key, palette)
            self._boxes[char] = box
            self._shapes[char] = rounded_rect(
                self,
                *box,
                self.radius,
                fill=fill,
                outline=self.key_outline(key, palette),
                tags=("key", f"key:{ord(char)}"),
            )
            self._fills[char] = fill
            self._by_char[char] = key
            self.draw_key_text(key, box, palette)
            self._texts[char] = [
                item
                for item in self.find_withtag(f"key:{ord(char)}")
                if self.type(item) == "text"
            ]
            right, bottom = max(right, box[2]), max(bottom, box[3])
        self.configure(width=right + self.padding, height=bottom + self.padding)

    # ------------------------------------------------------- анимация
    def _paint(self, char: str, fill: str) -> None:
        """Задать заливку одной клавиши без перерисовки клавиатуры.

        Args:
            char: Базовый символ клавиши.
            fill: Новый цвет заливки.
        """
        self.itemconfigure(self._shapes[char], fill=fill)
        self._fills[char] = fill

    def fade_key(
        self, char: str, start: str, duration_ms: int, delay_ms: int = 0
    ) -> None:
        """Плавно изменить заливку клавиши от ``start`` к её обычному цвету.

        Целевой цвет запрашивается на каждом кадре, поэтому, если клавиша
        перестаёт подсвечиваться посреди анимации, она плавно переходит к новому цвету.

        Args:
            char: Базовый символ клавиши.
            start: Цвет первого кадра.
            duration_ms: Длительность анимации.
            delay_ms: Пауза перед началом (волны по клавиатуре).
        """
        key = self._by_char.get(char)
        if key is None:
            return

        def step(t: float) -> None:
            end = self.target_fill(key)
            self._paint(char, mix_colors(start, end, t))

        self.animator.run(f"fill:{char}", duration_ms, step, delay_ms=delay_ms)

    def _restyle(self, char: str | None) -> None:
        """Обновить рамку и подпись клавиши и плавно изменить её заливку.

        Args:
            char: Базовый символ клавиши.
        """
        key = self._by_char.get(char) if char is not None else None
        if key is None:
            return
        palette = self.theme.palette
        self.itemconfigure(self._shapes[char], outline=self.key_outline(key, palette))
        for item in self._texts.get(char, []):
            self.itemconfigure(item, fill=self.key_text_color(key, palette))
        if not self.animator.is_running(f"fill:{char}"):
            # уже идущая вспышка плавно гаснет к новому целевому цвету
            self.fade_key(char, self._fills[char], HIGHLIGHT_MS)

    def highlight(self, char: str | None) -> None:
        """Подсветить клавишу, которую нужно нажать следующей.

        Перекрашиваются только две клавиши: старая и новая.

        Args:
            char: Базовый символ клавиши, ``None`` — снять подсветку.
        """
        if char == self._highlighted:
            return
        old, self._highlighted = self._highlighted, char
        self._restyle(old)
        self._restyle(char)

    def flash(self, char: str | None, is_correct: bool) -> None:
        """Кратко подсветить нажатую клавишу и дать ей погаснуть.

        Args:
            char: Базовый символ нажатой клавиши.
            is_correct: Зелёно-серая вспышка для верного нажатия, красная для ошибки.
        """
        if char is None or char not in self._shapes:
            return
        palette = self.theme.palette
        if is_correct:
            start = mix_colors(palette.surface, palette.muted, 0.55)
        else:
            start = mix_colors(palette.surface, palette.error, 0.8)
        self._paint(char, start)
        self.fade_key(char, start, FLASH_MS)

    def press(self, char: str | None, is_correct: bool) -> None:
        """Анимировать нажатие клавиши: вспышка и короткий «толчок» (масштаб 0,96).

        Args:
            char: Базовый символ нажатой клавиши.
            is_correct: Было ли нажатие правильным.
        """
        if char is None or char not in self._shapes:
            return
        self.flash(char, is_correct)
        x0, y0, x1, y1 = self._boxes[char]
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        tag = f"key:{ord(char)}"

        def set_scale(target: float) -> None:
            # нажатие, прерванное следующим, продолжается с его масштаба
            factor = target / self._scales.get(char, 1.0)
            self.scale(tag, cx, cy, factor, factor)
            self._scales[char] = target

        def step(t: float) -> None:
            # до 0,96 в первой половине, обратно до 1,0 во второй
            set_scale(1 - (1 - PRESS_SCALE) * (1 - abs(2 * t - 1)))

        def done() -> None:
            set_scale(1.0)

        self.animator.run(
            f"press:{char}", KEY_PRESS_MS * 2, step, done, easing=ease_in_out
        )

    # ----------------------------------------------------------- наведение
    def target_fill(self, key: Key) -> str:
        """Заливка, к которой должна прийти клавиша: её цвет, светлее под мышью.

        Args:
            key: Клавиша.

        Returns:
            Шестнадцатеричный цвет.
        """
        palette = self.theme.palette
        fill = self.key_fill(key, palette)
        if key.key_char == self._hovered:
            fill = mix_colors(fill, palette.text, HOVER_MIX)
        return fill

    def _char_under_mouse(self) -> str | None:
        """Найти клавишу под указателем мыши.

        Returns:
            Базовый символ или ``None``.
        """
        item = self.find_withtag("current")
        if not item:
            return None
        for tag in self.gettags(item[0]):
            if tag.startswith("key:"):
                return chr(int(tag[4:]))
        return None

    def _on_enter(self, _event: tk.Event) -> None:
        """Осветлить клавишу под мышью.

        Args:
            _event: Событие Tk (не используется).
        """
        char = self._char_under_mouse()
        if char == self._hovered:
            return
        old, self._hovered = self._hovered, char
        for key_char in (old, char):
            if key_char in self._fills and not self.animator.is_running(
                f"fill:{key_char}"
            ):
                self.fade_key(key_char, self._fills[key_char], HIGHLIGHT_MS)

    def _on_leave(self, _event: tk.Event) -> None:
        """Вернуть цвет клавиши, когда мышь её покидает.

        Args:
            _event: Событие Tk (не используется).
        """
        old, self._hovered = self._hovered, None
        if old in self._fills:
            self.fade_key(old, self._fills[old], HIGHLIGHT_MS)
