"""Правила учёта нажатий клавиш (ТЗ, п. 4.1.4)."""

import pytest

from keytrainer.engine.typing_session import SessionState, TypingSession
from tests.test_metrics import FakeClock


def test_error_stays_after_backspace():
    """Неверная клавиша — это ошибка, даже если её стёрли."""
    session = TypingSession("ab", "EN_QWERTY", clock=FakeClock(0.1))
    session.press("x")
    session.backspace()
    session.press("a")
    session.press("b")
    snap = session.snapshot()
    assert snap.errors == 1 and snap.keystrokes == 3
    assert snap.correct_chars == 2
    assert session.key_counters["a"].errors == 1


def test_pause_is_not_counted():
    """Время на паузе не входит в длительность."""
    clock = FakeClock(1.0)
    session = TypingSession("abc", "EN_QWERTY", clock=clock)
    session.press("a")
    clock.tick()
    session.pause()
    clock.now += 100
    session.resume()
    clock.tick()
    session.press("b")
    assert session.state == SessionState.RUNNING
    assert session.elapsed_sec == pytest.approx(2.0)
    assert session.key_counters["b"].latencies_ms == [pytest.approx(2000.0)]


def test_long_interval_is_outlier():
    """Интервалы дольше 2000 мс не входят в среднее время реакции."""
    clock = FakeClock(0.2)
    session = TypingSession("abc", "EN_QWERTY", clock=clock)
    session.press("a")
    clock.now += 2.5
    session.press("b")
    clock.tick()
    session.press("c")
    assert session.key_counters["b"].avg_latency_ms is None
    assert session.key_counters["c"].avg_latency_ms == pytest.approx(200.0)


def test_capital_letter_counts_on_base_key():
    """Заглавные и строчные буквы учитываются на одной клавише."""
    session = TypingSession("Фф", "RU_JCUKEN", clock=FakeClock(0.1))
    session.press("Ф")
    session.press("ф")
    assert session.key_counters["ф"].attempts == 2


def test_time_limit_and_abort():
    """Сессия на время сообщает об окончании времени; прерывание помечает её незавершённой."""
    clock = FakeClock(0.0)
    session = TypingSession("a" * 100, "EN_QWERTY", time_limit_sec=30, clock=clock)
    session.press("a")
    clock.now = 31
    assert session.is_time_over
    session.finish(completed=False)
    assert session.is_finished and not session.is_completed
    with pytest.raises(RuntimeError):
        session.press("a")


def test_empty_text_rejected():
    """Пустое упражнение нельзя запустить."""
    with pytest.raises(ValueError):
        TypingSession("", "EN_QWERTY")
