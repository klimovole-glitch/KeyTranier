"""Accuracy of metrics against reference values (ТЗ, п. 6.1)."""

import pytest

from keytrainer.engine import metrics
from keytrainer.engine.typing_session import TypingSession

# text, typed keystrokes ("<" = Backspace), seconds per key,
# expected WPM, CPM, error rate
CONTROL_EXERCISES = [
    ("мама мыла раму", "мама мыла раму", 0.5, 25.85, 129.23, 0.0),
    ("hello world", "hellp<o world", 0.25, 44.0, 220.0, 8.33),
    ("abc def", "abd<c dx<ef", 1.0, 8.4, 42.0, 22.22),
    ("слово", "слово", 2.0, 7.5, 37.5, 0.0),
    ("тест тест", "тесь<т тест", 0.4, 27.0, 135.0, 10.0),
]


class FakeClock:
    """Clock that moves forward by a fixed step on every call."""

    def __init__(self, step: float) -> None:
        """Create the clock.

        Args:
            step: Seconds added on each call after the first one.
        """
        self.now = 0.0
        self.step = step

    def tick(self) -> None:
        """Advance the time by one step."""
        self.now += self.step

    def __call__(self) -> float:
        """Return current time."""
        return self.now


def _type(session: TypingSession, clock: FakeClock, keys: str) -> None:
    """Feed keystrokes to a session, one step of time per key.

    Args:
        session: Typing session.
        clock: Fake clock.
        keys: Characters; "<" means Backspace.
    """
    for index, key in enumerate(keys):
        if index:
            clock.tick()
        if key == "<":
            session.backspace()
        else:
            session.press(key)


@pytest.mark.parametrize(
    "text, keys, step, exp_wpm, exp_cpm, exp_rate", CONTROL_EXERCISES
)
def test_control_exercises(text, keys, step, exp_wpm, exp_cpm, exp_rate):
    """Metrics differ from the reference by no more than 0.1."""
    clock = FakeClock(step)
    session = TypingSession(text, "RU_JCUKEN", clock=clock)
    _type(session, clock, keys)
    assert session.is_finished
    snap = session.snapshot()
    assert snap.wpm == pytest.approx(exp_wpm, abs=0.1)
    assert snap.cpm == pytest.approx(exp_cpm, abs=0.1)
    assert snap.error_rate == pytest.approx(exp_rate, abs=0.1)


def test_formulas_with_zero_values():
    """No division by zero for an empty session."""
    assert metrics.wpm(10, 0) == 0.0
    assert metrics.error_rate(0, 0) == 0.0
    assert metrics.accuracy(12.5) == 87.5


def test_moving_average():
    """The series keeps its length; the first points use what is available."""
    assert metrics.moving_average([10, 20, 30, 40], 2) == [10, 15, 25, 35]
    with pytest.raises(ValueError):
        metrics.moving_average([1], 0)
