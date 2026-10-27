"""Typing session: keystroke accounting and live metrics (ТЗ, п. 4.1.1, 4.1.4).

Rules implemented here:

* the timer starts with the first key press;
* a wrong character is shown in the text and counted as an error at once —
  erasing it with Backspace does not remove the error;
* time spent in pause is not counted;
* the interval before a key press longer than 2000 ms is an outlier and is
  not used for the average reaction time;
* statistics are stored on the base key of the EXPECTED character
  ("А" and "а" are one key).

Modifier keys and auto-repeat are filtered by the controller, so this class
receives only printable characters and Backspace.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum

from keytrainer.data.keyboard_layouts import base_key_char
from keytrainer.engine import metrics

LATENCY_OUTLIER_MS = 2000.0


class SessionState(str, Enum):
    """Life cycle of a session."""

    READY = "READY"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    FINISHED = "FINISHED"


@dataclass
class KeyCounter:
    """Attempts, errors and reaction times of one key."""

    attempts: int = 0
    errors: int = 0
    latencies_ms: list[float] = field(default_factory=list)

    def register(self, is_correct: bool, latency_ms: float | None) -> None:
        """Account one press of the key.

        Args:
            is_correct: Whether the right character was typed.
            latency_ms: Interval since the previous press, ``None`` for the
                first press of the session.
        """
        self.attempts += 1
        if not is_correct:
            self.errors += 1
        if latency_ms is not None and latency_ms <= LATENCY_OUTLIER_MS:
            self.latencies_ms.append(latency_ms)

    @property
    def avg_latency_ms(self) -> float | None:
        """Average reaction time without outliers, ``None`` if unknown."""
        if not self.latencies_ms:
            return None
        return sum(self.latencies_ms) / len(self.latencies_ms)


@dataclass(frozen=True)
class KeyResult:
    """What happened after one key press (used by the view to repaint)."""

    position: int
    expected: str
    typed: str
    is_correct: bool
    finished: bool


@dataclass(frozen=True)
class SessionSnapshot:
    """Live metrics shown on the metrics panel."""

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
    """One pass of one exercise text."""

    def __init__(
        self,
        text: str,
        layout_name: str,
        time_limit_sec: float | None = None,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        """Prepare a session; the timer starts on the first key press.

        Args:
            text: Exercise text.
            layout_name: Layout the text is typed on.
            time_limit_sec: Time limit for the "по времени" mode.
            clock: Source of time in seconds (``time.perf_counter``);
                tests pass a fake clock.

        Raises:
            ValueError: If the text is empty.
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

    # ----------------------------------------------------------- state
    @property
    def state(self) -> SessionState:
        """Current state of the session."""
        return self._state

    @property
    def position(self) -> int:
        """Index of the next character to type."""
        return len(self._typed)

    @property
    def is_finished(self) -> bool:
        """``True`` after :meth:`finish`."""
        return self._state == SessionState.FINISHED

    @property
    def elapsed_sec(self) -> float:
        """Typing time in seconds without pauses."""
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
        """``True`` if the time limit of the exercise is reached."""
        return (
            self.time_limit_sec is not None and self.elapsed_sec >= self.time_limit_sec
        )

    @property
    def key_counters(self) -> dict[str, KeyCounter]:
        """Statistics by base key character."""
        return self._counters

    def char_states(self) -> list[bool]:
        """Return correctness of every typed character (for highlighting).

        Returns:
            ``True`` for a correct character at each typed position.
        """
        return [typed == self.text[i] for i, typed in enumerate(self._typed)]

    # --------------------------------------------------------- actions
    def press(self, char: str) -> KeyResult:
        """Account a printable key press.

        Args:
            char: Typed character.

        Returns:
            Result of the press.

        Raises:
            RuntimeError: If the session is finished or paused.
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
            self._errors += 1  # stays counted even after Backspace
        key = base_key_char(expected, self.layout_name)
        self._counters.setdefault(key, KeyCounter()).register(is_correct, latency)

        self._typed.append(char)
        finished = self.position >= len(self.text)
        if finished:
            self.finish(completed=True)
        return KeyResult(position, expected, char, is_correct, finished)

    def backspace(self) -> int:
        """Erase the last typed character (errors stay counted).

        Returns:
            New position.
        """
        if self._typed and self._state == SessionState.RUNNING:
            self._typed.pop()
        return self.position

    def pause(self) -> None:
        """Stop the timer (focus lost or pause key)."""
        if self._state == SessionState.RUNNING:
            self._paused_at = self._clock()
            self._state = SessionState.PAUSED

    def resume(self) -> None:
        """Continue after a pause; the pause is not counted as typing time."""
        if self._state == SessionState.PAUSED and self._paused_at is not None:
            now = self._clock()
            self._paused_total += now - self._paused_at
            # the first press after a pause must not get the pause as latency
            if self._last_press_at is not None:
                self._last_press_at += now - self._paused_at
            self._paused_at = None
            self._state = SessionState.RUNNING

    def finish(self, completed: bool) -> None:
        """Stop the session.

        Args:
            completed: ``True`` if the whole text was typed or the time limit
                ended, ``False`` if the user aborted the exercise.
        """
        if self._state == SessionState.FINISHED:
            return
        self.resume()
        self._finished_at = self._clock()
        self._state = SessionState.FINISHED
        self.is_completed = completed

    # --------------------------------------------------------- metrics
    def snapshot(self) -> SessionSnapshot:
        """Calculate metrics at the current moment.

        Returns:
            Values for the metrics panel and the results card.
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
