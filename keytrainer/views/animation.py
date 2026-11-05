"""Небольшие помощники анимации для Tkinter (без дополнительных библиотек).

В Tkinter нет встроенных анимаций, поэтому каждая анимация — это цепочка
вызовов ``after()`` примерно 60 раз в секунду. :class:`Animator` хранит
одну запущенную анимацию на имя: запуск новой с тем же именем останавливает
старую, поэтому при быстром наборе не накапливаются сотни таймеров.

Длительности взяты со страницы Figma «СПЕЦИФИКАЦИЯ»: нажатие клавиши
длится 0,1 с, каретка скользит 0,09 с, ошибка трясёт текст 0,22 с, а
боковая панель выезжает за 0,38 с.
"""

from __future__ import annotations
import math
import tkinter as tk
from collections.abc import Callable

FRAME_MS = 16  # ~60 кадров в секунду

# Длительности из спецификации (миллисекунды)
KEY_PRESS_MS = 100
CARET_SLIDE_MS = 90
CARET_ERROR_MS = 260
SHAKE_MS = 220
PANEL_MS = 380
SCREEN_MS = 260
HOVER_MS = 140
FADE_MS = 220
CARET_BLINK_MS = 530


def ease_out(t: float) -> float:
    """Кубическая кривая ease-out: быстрый старт, мягкая остановка.

    Args:
        t: Прогресс от 0 до 1.

    Returns:
        Сглаженный прогресс от 0 до 1.
    """
    t = min(max(t, 0.0), 1.0)
    return 1 - (1 - t) ** 3


def ease_in_out(t: float) -> float:
    """Кубическая кривая ease-in-out: мягкий старт и мягкая остановка.

    Args:
        t: Прогресс от 0 до 1.

    Returns:
        Сглаженный прогресс от 0 до 1.
    """
    t = min(max(t, 0.0), 1.0)
    return 4 * t**3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def linear(t: float) -> float:
    """Линейная кривая (для тряски, у которой своя форма).

    Args:
        t: Прогресс от 0 до 1.

    Returns:
        Тот же прогресс.
    """
    return min(max(t, 0.0), 1.0)


def shake_offset(t: float, amplitude: float = 7.0, waves: float = 3.0) -> float:
    """Горизонтальное смещение затухающей тряски.

    Args:
        t: Прогресс от 0 до 1.
        amplitude: Смещение первого размаха в пикселях.
        waves: Число полных размахов.

    Returns:
        Смещение в пикселях (0 в начале и в конце).
    """
    return amplitude * (1 - t) * math.sin(t * waves * 2 * math.pi)


def lerp(start: float, end: float, t: float) -> float:
    """Линейная интерполяция между двумя числами.

    Args:
        start: Значение при ``t = 0``.
        end: Значение при ``t = 1``.
        t: Прогресс от 0 до 1.

    Returns:
        Промежуточное значение.
    """
    return start + (end - start) * t


def _rgb(color: str) -> tuple[int, int, int]:
    """Преобразовать ``#rrggbb`` в кортеж целых чисел.

    Args:
        color: Цвет в шестнадцатеричном формате.

    Returns:
        Красный, зелёный и синий от 0 до 255.
    """
    color = color.lstrip("#")
    return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)


def mix_colors(start: str, end: str, t: float) -> str:
    """Смешать два шестнадцатеричных цвета.

    Args:
        start: Цвет при ``t = 0`` (``#rrggbb``).
        end: Цвет при ``t = 1`` (``#rrggbb``).
        t: Прогресс от 0 до 1.

    Returns:
        Шестнадцатеричный цвет между ``start`` и ``end``.
    """
    t = min(max(t, 0.0), 1.0)
    channels = (
        round(lerp(a, b, t)) for a, b in zip(_rgb(start), _rgb(end))
    )
    return "#" + "".join(f"{c:02x}" for c in channels)


class Animator:
    """Запускает именованные анимации поверх ``after()``."""

    def __init__(self, widget: tk.Misc) -> None:
        """Привязать аниматор к виджету, чей ``after()`` используется.

        Args:
            widget: Любой виджет, живущий столько же, сколько анимации.
        """
        self._widget = widget
        self._jobs: dict[str, str] = {}

    def is_running(self, name: str) -> bool:
        """Проверить, выполняется ли анимация.

        Args:
            name: Имя анимации.

        Returns:
            ``True``, пока она выполняется.
        """
        return name in self._jobs

    def cancel(self, name: str) -> None:
        """Остановить анимацию (последний нарисованный кадр остаётся на экране).

        Args:
            name: Имя анимации.
        """
        job = self._jobs.pop(name, None)
        if job is not None:
            try:
                self._widget.after_cancel(job)
            except tk.TclError:
                pass  # виджет уничтожается

    def cancel_all(self) -> None:
        """Остановить все анимации этого аниматора."""
        for name in list(self._jobs):
            self.cancel(name)

    def _alive(self) -> bool:
        """Проверить, что виджет всё ещё существует.

        Returns:
            ``False`` после уничтожения виджета.
        """
        try:
            return bool(self._widget.winfo_exists())
        except tk.TclError:
            return False

    def run(
        self,
        name: str,
        duration_ms: int,
        step: Callable[[float], None],
        done: Callable[[], None] | None = None,
        easing: Callable[[float], float] = ease_out,
        delay_ms: int = 0,
        frame_ms: int = FRAME_MS,
    ) -> None:
        """Запустить анимацию, заменив анимацию с тем же именем.

        Args:
            name: Имя анимации (одна анимация на имя).
            duration_ms: Длительность анимации.
            step: Вызывается на каждом кадре со сглаженным прогрессом 0..1.
            done: Вызывается один раз после последнего кадра.
            easing: Кривая сглаживания.
            delay_ms: Пауза перед первым кадром (анимации со сдвигом).
            frame_ms: Интервал между кадрами (больше для тяжёлых перерисовок).
        """
        self.cancel(name)
        frames = max(1, duration_ms // frame_ms)

        def frame(index: int) -> None:
            if not self._alive():
                self._jobs.pop(name, None)
                return
            step(easing(index / frames))
            if index >= frames:
                self._jobs.pop(name, None)
                if done:
                    done()
                return
            self._jobs[name] = self._widget.after(frame_ms, frame, index + 1)

        if delay_ms > 0:
            self._jobs[name] = self._widget.after(delay_ms, frame, 1)
        else:
            frame(1)

    def repeat(self, name: str, interval_ms: int, tick: Callable[[], None]) -> None:
        """Вызывать ``tick`` каждые ``interval_ms`` до отмены (мигание).

        Args:
            name: Имя анимации.
            interval_ms: Интервал между вызовами.
            tick: Вызываемая функция.
        """
        self.cancel(name)

        def again() -> None:
            if not self._alive():
                self._jobs.pop(name, None)
                return
            tick()
            self._jobs[name] = self._widget.after(interval_ms, again)

        self._jobs[name] = self._widget.after(interval_ms, again)

    def later(self, name: str, delay_ms: int, callback: Callable[[], None]) -> None:
        """Вызвать ``callback`` один раз после задержки (отменяется по имени).

        Args:
            name: Имя анимации.
            delay_ms: Задержка.
            callback: Вызываемая функция.
        """
        self.cancel(name)

        def fire() -> None:
            self._jobs.pop(name, None)
            if self._alive():
                callback()

        self._jobs[name] = self._widget.after(delay_ms, fire)

    def fade(
        self,
        name: str,
        widget: tk.Misc,
        option: str,
        start: str,
        end: str,
        duration_ms: int = FADE_MS,
        delay_ms: int = 0,
        done: Callable[[], None] | None = None,
    ) -> None:
        """Плавно изменить параметр цвета виджета.

        Args:
            name: Имя анимации.
            widget: Перекрашиваемый виджет.
            option: Имя параметра, например ``"fg"``.
            start: Первый цвет.
            end: Последний цвет.
            duration_ms: Длительность анимации.
            delay_ms: Пауза перед началом.
            done: Вызывается после последнего кадра.
        """

        def step(t: float) -> None:
            if widget.winfo_exists():
                widget.configure(**{option: mix_colors(start, end, t)})

        if delay_ms > 0:
            widget.configure(**{option: start})
        self.run(name, duration_ms, step, done, delay_ms=delay_ms)
