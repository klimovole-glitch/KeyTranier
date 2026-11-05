from __future__ import annotations
"""Тепловая карта клавиатуры (ТЗ, п. 4.2.1; Figma: рисунок 8)."""

import tkinter as tk
from collections.abc import Callable

from keytrainer.data.models import Key
from keytrainer.engine.analytics_engine import (
    HeatmapData,
    KeyCell,
    Metric,
    heat_color,
)
from keytrainer.views.display import px
from keytrainer.views.theme import Palette, ThemeManager
from keytrainer.views.widgets.keyboard_canvas import KeyboardCanvas


class HeatmapCanvas(KeyboardCanvas):
    """Клавиатура, клавиши которой окрашены по доле ошибок или времени реакции.

    Наследует отрисовку клавиш от :class:`KeyboardCanvas` (DRY) и
    переопределяет только заливку и подпись клавиши.
    """

    key_size = 54
    reveal_ms = 460

    def __init__(self, parent: tk.Misc, theme: ThemeManager) -> None:
        """Создать пустую тепловую карту.

        Args:
            parent: Родительский виджет.
            theme: Менеджер тем.
        """
        super().__init__(parent, theme)
        self.data: HeatmapData | None = None
        self.on_hover: Callable[[KeyCell | None, int, int], None] | None = None
        self.tag_bind("key", "<Motion>", self._motion, add="+")
        self.tag_bind(
            "key", "<Leave>", lambda _e: self._emit_hover(None, 0, 0), add="+"
        )

    def show(self, data: HeatmapData, keys: list[Key]) -> None:
        """Нарисовать новую статистику.

        Args:
            data: Данные тепловой карты.
            keys: Клавиши раскладки.
        """
        old_fills = dict(self._fills)
        self.data = data
        digits_used = any(c.attempts for c in data.cells.values() if c.key.row_num == 0)
        self.set_keys(keys, show_digits=digits_used)
        self._reveal(old_fills)

    def _reveal(self, old_fills: dict[str, str]) -> None:
        """Пустить цвета по клавиатуре слева направо.

        При первом показе клавиши начинают серыми; после смены фильтра каждая
        клавиша перетекает из прежнего цвета в новый.

        Args:
            old_fills: Цвета клавиш до перерисовки.
        """
        palette = self.theme.palette
        for char, key in self._by_char.items():
            start = old_fills.get(char, palette.heat_empty)
            self._paint(char, start)
            delay = int(key.pos_x * 26 + key.pos_y * 34)
            self.fade_key(char, start, self.reveal_ms, delay_ms=delay)

    def color_for(self, cell: KeyCell, palette: Palette) -> str:
        """Цвет клавиши на шкале (серый, если данных слишком мало).

        Args:
            cell: Статистика клавиши.
            palette: Текущая палитра.

        Returns:
            Шестнадцатеричный цвет.
        """
        ratio = self.data.ratio(cell) if self.data else None
        if ratio is None:
            return palette.heat_empty
        return heat_color(ratio, palette.heat_saturation, palette.heat_value)

    def key_fill(self, key: Key, palette: Palette) -> str:
        """Залить клавишу её тепловым цветом.

        Args:
            key: Красимая клавиша.
            palette: Текущая палитра.

        Returns:
            Шестнадцатеричный цвет.
        """
        cell = self.data.cells.get(key.key_char) if self.data else None
        return self.color_for(cell, palette) if cell else palette.heat_empty

    def draw_key_text(self, key: Key, box: tuple, palette: Palette) -> None:
        """Нарисовать символ и значение под ним («27%», «412», «<5»).

        Args:
            key: Клавиша.
            box: Прямоугольник клавиши.
            palette: Текущая палитра.
        """
        x0, y0, x1, y1 = box
        cell = self.data.cells.get(key.key_char) if self.data else None
        tags = ("key", f"key:{ord(key.key_char)}")
        center = (x0 + x1) / 2
        self.create_text(
            center,
            y0 + px(18),
            text=key.key_char,
            fill=palette.text,
            font=self.theme.fonts["key"],
            tags=tags,
        )
        caption = value_caption(cell, self.data.metric) if cell else ""
        self.create_text(
            center,
            y1 - px(11),
            text=caption,
            fill=palette.muted,
            font=self.theme.fonts["tiny"],
            tags=tags,
        )

    def _motion(self, event: tk.Event) -> None:
        """Найти клавишу под указателем и сообщить о ней.

        Args:
            event: Событие движения Tk.
        """
        item = self.find_withtag("current")
        if not item or self.data is None:
            return
        for tag in self.gettags(item[0]):
            if tag.startswith("key:"):
                cell = self.data.cells.get(chr(int(tag[4:])))
                self._emit_hover(cell, event.x_root, event.y_root)
                return

    def _emit_hover(self, cell: KeyCell | None, x: int, y: int) -> None:
        """Передать экрану клавишу, над которой находится указатель.

        Args:
            cell: Клавиша под указателем или ``None``.
            x: X указателя (экранный).
            y: Y указателя (экранный).
        """
        if self.on_hover:
            self.on_hover(cell, x, y)


def value_caption(cell: KeyCell, metric: Metric) -> str:
    """Короткое значение, написанное на клавише.

    Args:
        cell: Статистика клавиши.
        metric: Выбранная метрика.

    Returns:
        «<5» при слишком малом количестве данных, иначе «27%» или «412».
    """
    if not cell.enough_data:
        return "<5"
    if metric == Metric.ERROR_RATE:
        return f"{cell.error_rate:.0f}%"
    return f"{cell.avg_latency_ms:.0f}" if cell.avg_latency_ms else "—"
