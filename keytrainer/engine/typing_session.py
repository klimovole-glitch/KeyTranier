from __future__ import annotations
"""Сессия набора: учёт нажатий и метрики в реальном времени (ТЗ, п. 4.1.1, 4.1.4).

Реализованные здесь правила:

* таймер запускается с первым нажатием клавиши;
* неверный символ показывается в тексте и сразу считается ошибкой —
  стирание его клавишей Backspace ошибку не убирает;
* время, проведённое на паузе, не учитывается;
* интервал перед нажатием клавиши дольше 2000 мс считается выбросом и не
  используется при расчёте среднего времени реакции;
* статистика хранится на базовой клавише ОЖИДАЕМОГО символа
  («А» и «а» — одна клавиша).

Клавиши-модификаторы и автоповтор фильтруются контроллером, поэтому этот
класс получает только печатные символы и Backspace.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum

from keytrainer.data.keyboard_layouts import base_key_char
from keytrainer.engine import metrics

LATENCY_OUTLIER_MS = 2000.0


class SessionState(str, Enum):
    """Жизненный цикл сессии."""

    READY = "READY"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    FINISHED = "FINISHED"


@dataclass
class KeyCounter:
    """Попытки, ошибки и время реакции одной клавиши."""

    attempts: int = 0
    errors: int = 0
    latencies_ms: list[float] = field(default_factory=list)

    def register(self, is_correct: bool, latency_ms: float | None) -> None:
        """Учесть одно нажатие клавиши.

        Args:
            is_correct: Был ли введён правильный символ.
            latency_ms: Интервал с предыдущего нажатия, ``None`` для
                первого нажатия сессии.
        """
        self.attempts += 1
        if not is_correct:
            self.errors += 1
        if latency_ms is not None and latency_ms <= LATENCY_OUTLIER_MS:
            self.latencies_ms.append(latency_ms)

    @property
    def avg_latency_ms(self) -> float | None:
        """Среднее время реакции без выбросов, ``None``, если оно неизвестно."""
        if not self.latencies_ms:
            return None
        return sum(self.latencies_ms) / len(self.latencies_ms)


@dataclass(frozen=True)
class KeyResult:
    """Что произошло после одного нажатия клавиши (используется представлением для перерисовки)."""

    position: int
    expected: str
    typed: str
    is_correct: bool
    finished: bool


@dataclass(frozen=True)
class SessionSnapshot:
    """Метрики в реальном времени, показываемые на панели метрик."""

    elapsed_sec: float
    correct_chars: int
    keystrokes: int
    errors: int
    wpm: float
    cpm: float
    error_rate: float
    accuracy: float
    progress: float


class TypingSession:
    """Один проход одного текста упражнения."""

    def __init__(
        self,
        text: str,
        layout_name: str,
        time_limit_sec: float | None = None,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        """Подготовить сессию; таймер запускается с первым нажатием клавиши.

        Args:
            text: Текст упражнения.
            layout_name: Раскладка, на которой набирается текст.
            time_limit_sec: Лимит времени для режима «по времени».
            clock: Источник времени в секундах (``time.perf_counter``);
                в тестах передаются поддельные часы.

        Raises:
            ValueError: Если текст пустой.
        """
        if not text:
            raise ValueError("Exercise text is empty")
        self.text = text
        self.layout_name = layout_name
        self.time_limit_sec = time_limit_sec
        self._clock = clock
        self._typed: list[str] = []
        self._keystrokes = 0
        self._errors = 0
        self._counters: dict[str, KeyCounter] = {}
        self._state = SessionState.READY
        self._started_at: float | None = None
        self._finished_at: float | None = None
        self._paused_at: float | None = None
        self._paused_total = 0.0
        self._last_press_at: float | None = None
        self.is_completed = False

    # ----------------------------------------------------------- состояние
    @property
    def state(self) -> SessionState:
        """Текущее состояние сессии."""
        return self._state

    @property
    def position(self) -> int:
        """Индекс следующего набираемого символа."""
        return len(self._typed)

    @property
    def is_finished(self) -> bool:
        """``True`` после :meth:`finish`."""
        return self._state == SessionState.FINISHED

    @property
    def elapsed_sec(self) -> float:
        """Время набора в секундах без пауз."""
        if self._started_at is None:
            return 0.0
        if self._finished_at is not None:
            end = self._finished_at
        elif self._paused_at is not None:
            end = self._paused_at
        else:
            end = self._clock()
        return max(0.0, end - self._started_at - self._paused_total)

    @property
    def is_time_over(self) -> bool:
        """``True``, если достигнут лимит времени упражнения."""
        return (
            self.time_limit_sec is not None and self.elapsed_sec >= self.time_limit_sec
        )

    @property
    def key_counters(self) -> dict[str, KeyCounter]:
        """Статистика по символам базовых клавиш."""
        return self._counters

    def char_states(self) -> list[bool]:
        """Вернуть правильность каждого введённого символа (для подсветки).

        Returns:
            ``True`` для правильного символа в каждой введённой позиции.
        """
        return [typed == self.text[i] for i, typed in enumerate(self._typed)]

    # --------------------------------------------------------- действия
    def press(self, char: str) -> KeyResult:
        """Учесть нажатие печатной клавиши.

        Args:
            char: Введённый символ.

        Returns:
            Результат нажатия.

        Raises:
            RuntimeError: Если сессия завершена или приостановлена.
        """
        if self._state in (SessionState.FINISHED, SessionState.PAUSED):
            raise RuntimeError(f"Cannot type in state {self._state.value}")
        now = self._clock()
        if self._state == SessionState.READY:
            self._started_at = now
            self._state = SessionState.RUNNING

        position = self.position
        expected = self.text[position]
        is_correct = char == expected
        latency = None
        if self._last_press_at is not None:
            latency = (now - self._last_press_at) * 1000
        self._last_press_at = now

        self._keystrokes += 1
        if not is_correct:
            self._errors += 1  # остаётся учтённой даже после Backspace
        key = base_key_char(expected, self.layout_name)
        self._counters.setdefault(key, KeyCounter()).register(is_correct, latency)

        self._typed.append(char)
        finished = self.position >= len(self.text)
        if finished:
            self.finish(completed=True)
        return KeyResult(position, expected, char, is_correct, finished)

    def backspace(self) -> int:
        """Стереть последний введённый символ (ошибки остаются учтёнными).

        Returns:
            Новая позиция.
        """
        if self._typed and self._state == SessionState.RUNNING:
            self._typed.pop()
        return self.position

    def pause(self) -> None:
        """Остановить таймер (потеря фокуса или клавиша паузы)."""
        if self._state == SessionState.RUNNING:
            self._paused_at = self._clock()
            self._state = SessionState.PAUSED

    def resume(self) -> None:
        """Продолжить после паузы; пауза не учитывается во времени набора."""
        if self._state == SessionState.PAUSED and self._paused_at is not None:
            now = self._clock()
            self._paused_total += now - self._paused_at
            # первое нажатие после паузы не должно получать паузу как задержку
            if self._last_press_at is not None:
                self._last_press_at += now - self._paused_at
            self._paused_at = None
            self._state = SessionState.RUNNING

    def finish(self, completed: bool) -> None:
        """Остановить сессию.

        Args:
            completed: ``True``, если набран весь текст или истёк лимит
                времени, ``False``, если пользователь прервал упражнение.
        """
        if self._state == SessionState.FINISHED:
            return
        self.resume()
        self._finished_at = self._clock()
        self._state = SessionState.FINISHED
        self.is_completed = completed

    # --------------------------------------------------------- метрики
    def snapshot(self) -> SessionSnapshot:
        """Вычислить метрики на текущий момент.

        Returns:
            Значения для панели метрик и карточки результатов.
        """
        correct = sum(self.char_states())
        minutes = self.elapsed_sec / 60
        rate = metrics.error_rate(self._errors, self._keystrokes)
        return SessionSnapshot(
            elapsed_sec=self.elapsed_sec,
            correct_chars=correct,
            keystrokes=self._keystrokes,
            errors=self._errors,
            wpm=metrics.wpm(correct, minutes),
            cpm=metrics.cpm(correct, minutes),
            error_rate=rate,
            accuracy=metrics.accuracy(rate),
            progress=self.position / len(self.text),
        )
