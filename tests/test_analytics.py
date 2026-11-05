"""Тепловая карта, проблемные клавиши и режим слабых клавиш (ТЗ, п. 4.3.1, 6.1)."""

import time
from datetime import datetime

import pytest

from keytrainer.data.demo_data import generate
from keytrainer.data.repositories import (
    KeyRepository,
    KeyStatRepository,
    SessionRepository,
)
from keytrainer.engine.analytics_engine import (
    AnalyticsEngine,
    Metric,
    Period,
    heat_color,
    heat_ratio,
)


@pytest.fixture
def engine(database):
    """Движок аналитики поверх тестовой базы данных.

    Args:
        database: Инициализированная тестовая база данных.

    Returns:
        Движок аналитики.
    """
    return AnalyticsEngine(
        KeyStatRepository(database),
        KeyRepository(database),
        SessionRepository(database),
    )


def test_colors_from_green_to_red():
    """0 — зелёный, 1 — красный, значения за пределами шкалы обрезаются."""
    assert heat_color(0.0, 1.0, 1.0) == "#00ff00"
    assert heat_color(1.0, 1.0, 1.0) == "#ff0000"
    assert heat_ratio(45, 0, 30) == 1.0
    assert heat_ratio(-5, 0, 30) == 0.0


def test_weak_keys_are_red_and_ranked(database, engine):
    """20 сессий с ошибками на «ф», «ы», «в»: они возглавляют рейтинг."""
    user_id = generate(database, "Тест", 20)
    data = engine.build_heatmap(user_id, "RU_JCUKEN", Metric.ERROR_RATE, Period.ALL)
    assert {c.key.key_char for c in data.top[:3]} == {"ф", "ы", "в"}
    for char in "фыв":
        assert data.ratio(data.cells[char]) > 0.6
    assert data.ratio(data.cells["о"]) < 0.3


def test_keys_with_few_presses_are_grey(database, engine):
    """Клавиши, нажатые менее 5 раз, не получают ни цвета, ни места в рейтинге."""
    user_id = generate(database, "Тест", 20)
    data = engine.build_heatmap(user_id, "RU_JCUKEN", Metric.ERROR_RATE, Period.ALL)
    digit = data.cells["1"]
    assert digit.attempts == 0 and data.ratio(digit) is None
    assert digit not in data.top


def test_periods_and_latency(database, engine):
    """Периоды фильтруют сессии; шкала задержки охватывает диапазон от минимума до максимума."""
    user_id = generate(database, "Тест", 20)
    future = datetime(2100, 1, 1)
    empty = engine.build_heatmap(
        user_id, "RU_JCUKEN", Metric.ERROR_RATE, Period.DAYS_7, now=future
    )
    assert not empty.sessions_found
    last = engine.build_heatmap(
        user_id, "RU_JCUKEN", Metric.LATENCY, Period.LAST_SESSION
    )
    assert last.sessions_found and last.scale_min < last.scale_max
    assert last.top[0].key.key_char in "фыв"


def test_weak_key_rates_for_generator(database, engine):
    """Режим слабых клавиш получает доли ошибок проблемных клавиш."""
    user_id = generate(database, "Тест", 20)
    rates = engine.weak_key_rates(user_id, "RU_JCUKEN")
    assert {"ф", "ы", "в"} <= set(rates)


def test_heatmap_over_1000_sessions_is_fast(database, engine):
    """Карта по 1000 сессий строится менее чем за 1 с (ТЗ, п. 4.1.3)."""
    user_id = generate(database, "Нагрузка", 1000)
    start = time.perf_counter()
    engine.build_heatmap(user_id, "RU_JCUKEN", Metric.ERROR_RATE, Period.ALL)
    assert time.perf_counter() - start < 1.0
