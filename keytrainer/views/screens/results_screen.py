from __future__ import annotations
"""Карточка результатов, показываемая после упражнения (Figma: рисунок 7)."""

import tkinter as tk
from collections.abc import Callable

from keytrainer.engine.session_service import SessionResult
from keytrainer.labels import format_duration, format_number, plural
from keytrainer.views.animation import Animator
from keytrainer.views.display import px
from keytrainer.views.theme import ThemeManager
from keytrainer.views.widgets.metrics_panel import MetricsPanel
from keytrainer.views.widgets.text_button import TextButton

RESULT_CAPTIONS = {
    "wpm": "wpm",
    "cpm": "cpm",
    "errors": "ошибки",
    "error_rate": "% ошибок",
    "time": "время",
}


class ResultsScreen(tk.Frame):
    """Итоговые метрики, сравнение с рекордом и средним, худшие клавиши."""

    def __init__(self, parent: tk.Misc, theme: ThemeManager) -> None:
        """Построить виджеты.

        Args:
            parent: Область содержимого главного окна.
            theme: Менеджер тем.
        """
        super().__init__(parent, bd=0)
        self.theme = theme
        theme.style(self, bg="bg")
        self.callbacks: dict[str, Callable[[], None]] = {}
        self.animator = Animator(self)
        self.buttons: list[TextButton] = []
        inner = theme.frame(self)
        inner.place(relx=0.5, rely=0.45, anchor="center")
        self.title = theme.label(inner, "упражнение завершено", role="muted")
        self.title.pack(pady=px((0, 40)))
        self.metrics = MetricsPanel(
            inner, theme, RESULT_CAPTIONS, value_font="metric_big", cell_width=8
        )
        self.metrics.pack()
        compare = theme.frame(inner)
        compare.pack(pady=px((50, 40)))
        self.record = self._comparison(compare, "личный рекорд", 0)
        self.average = self._comparison(compare, "среднее за 10 сессий", 1)
        theme.label(
            inner, "клавиши с наибольшим числом ошибок", role="muted", font="small"
        ).pack()
        self.worst = theme.frame(inner)
        self.worst.pack(pady=px((14, 50)))
        buttons = theme.frame(inner)
        buttons.pack()
        self.stats_button = None
        for column, (name, caption) in enumerate(
            (
                ("repeat", "повторить"),
                ("new", "новое упражнение"),
                ("stats", "к статистике"),
            )
        ):
            button = TextButton(
                buttons, theme, caption, lambda n=name: self._emit(n), role="text"
            )
            button.grid(row=0, column=column, padx=px(50))
            self.buttons.append(button)
            if name == "stats":
                self.stats_button = button

    def _emit(self, name: str) -> None:
        """Вызвать обратный вызов контроллера.

        Args:
            name: Имя обратного вызова.
        """
        callback = self.callbacks.get(name)
        if callback:
            callback()

    def _comparison(self, parent: tk.Misc, caption: str, column: int) -> dict:
        """Создать блок «подпись / значение / разница / цветная линия».

        Args:
            parent: Контейнер.
            caption: Подпись блока.
            column: Столбец сетки.

        Returns:
            Виджеты блока.
        """
        block = self.theme.frame(parent)
        block.grid(row=0, column=column, padx=px(120))
        self.theme.label(block, caption, role="muted", font="small").pack()
        row = self.theme.frame(block)
        row.pack(pady=px((6, 4)))
        value = self.theme.label(row, "—", font="title")
        value.pack(side="left")
        delta = self.theme.label(row, "", font="title")
        delta.pack(side="left", padx=px((24, 0)))
        line = tk.Frame(block, height=px(2), width=0)
        line.pack()
        return {"value": value, "delta": delta, "line": line}

    def _show_comparison(self, block: dict, base: float | None, current: float) -> None:
        """Заполнить блок сравнения.

        Args:
            block: Виджеты из :meth:`_comparison`.
            base: Значение для сравнения, ``None``, если сессий нет.
            current: WPM завершённой сессии.
        """
        palette = self.theme.palette
        if base is None:
            block["value"].configure(text="—")
            block["delta"].configure(text="")
            block["line"].configure(bg=palette.bg)
            return
        diff = round(current - base)
        block["value"].configure(text=f"{base:.0f} wpm")
        block["delta"].configure(text=f"{diff:+d}")
        color = palette.success if diff >= 0 else palette.error
        line = block["line"]
        line.configure(bg=color, width=0)
        self.animator.run(
            f"line{id(line)}",
            420,
            lambda t: line.configure(width=round(px(30) * t)),
            delay_ms=520,
        )
        self.animator.fade(
            f"delta{id(line)}", block["delta"], "fg", palette.bg, palette.text, 300, 520
        )

    def show_result(self, result: SessionResult) -> None:
        """Показать результат завершённого упражнения.

        Args:
            result: Данные, подготовленные ``SessionService``.
        """
        session = result.session
        self.title.configure(
            text="новый личный рекорд!" if result.is_record else "упражнение завершено"
        )
        self.metrics.count_up(
            {
                "wpm": (session.wpm, lambda v: f"{v:.0f}"),
                "cpm": (session.cpm, lambda v: f"{v:.0f}"),
                "errors": (session.errors_count, lambda v: str(round(v))),
                "error_rate": (session.error_rate, lambda v: f"{format_number(v)} %"),
                "time": (session.duration_sec, format_duration),
            }
        )
        palette = self.theme.palette
        self.animator.fade("title", self.title, "fg", palette.bg, palette.muted, 400)
        self._show_comparison(self.record, result.best_wpm_before, session.wpm)
        self._show_comparison(self.average, result.avg_wpm_last, session.wpm)
        for child in self.worst.winfo_children():
            child.destroy()
        if not result.worst_keys:
            self.theme.label(self.worst, "ошибок нет", role="success").pack()
        for index, worst in enumerate(result.worst_keys):
            box = self.theme.label(
                self.worst,
                worst.key_char,
                role="error",
                font="title",
                bg="surface",
                width=3,
                height=1,
            )
            box.pack(side="left", padx=px((30, 10)), ipady=px(8))
            self.animator.fade(
                f"worst{index}",
                box,
                "bg",
                palette.bg,
                palette.surface,
                320,
                700 + index * 90,
            )
            caption = plural(worst.errors, "ошибка", "ошибки", "ошибок")
            self.theme.label(self.worst, caption, role="muted", font="small").pack(
                side="left"
            )

    def on_shown(self) -> None:
        """Показать кнопки одну за другой."""
        for index, button in enumerate(self.buttons):
            button.fade_in(delay_ms=800 + index * 90)

    def set_stats_available(self, available: bool) -> None:
        """Включить «к статистике», когда экран статистики существует.

        Args:
            available: Зарегистрирован ли экран статистики.
        """
        if self.stats_button is not None:
            self.stats_button.set_state(enabled=available)
