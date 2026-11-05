from __future__ import annotations
"""Генератор тестовых сессий для демонстрации и приёмочных испытаний.

Использование::

    python -m keytrainer.data.demo_data --user Тест --sessions 20
    python -m keytrainer.data.demo_data --user Нагрузка --sessions 10000

Клавиши «ф», «ы», «в» (ТЗ, п. 6.1) получают высокую долю ошибок, поэтому они
должны краснеть на тепловой карте и попадать в топ проблемных клавиш.
"""

import argparse
import random
from datetime import datetime, timedelta

from keytrainer.config import DB_PATH
from keytrainer.data.database import Database
from keytrainer.data.exceptions import DuplicateNameError
from keytrainer.data.keyboard_layouts import LAYOUT_IDS, LAYOUT_RU
from keytrainer.data.models import ExerciseMode, KeyStat, Session
from keytrainer.data.repositories import (
    KeyRepository,
    SessionRepository,
    UserRepository,
)

WEAK_KEYS = ("ф", "ы", "в")
WEAK_ERROR_RATE = 0.35
NORMAL_ERROR_RATE = 0.03


def _make_key_stats(keys: list, rng: random.Random) -> list[KeyStat]:
    """Создать случайную статистику для каждой клавиши раскладки.

    Args:
        keys: Клавиши раскладки.
        rng: Генератор случайных чисел.

    Returns:
        Статистика с намеренно высокой долей ошибок на :data:`WEAK_KEYS`.
    """
    stats = []
    for key in keys:
        attempts = rng.randint(3, 25)
        rate = WEAK_ERROR_RATE if key.key_char in WEAK_KEYS else NORMAL_ERROR_RATE
        errors = sum(rng.random() < rate for _ in range(attempts))
        latency = rng.uniform(180, 260) + (150 if key.key_char in WEAK_KEYS else 0)
        stats.append(KeyStat(key.id, attempts, errors, round(latency, 1)))
    return stats


def _make_session(
    user_id: int, started: datetime, stats: list[KeyStat], rng: random.Random
) -> Session:
    """Построить сессию, метрики которой согласуются со статистикой клавиш.

    Args:
        user_id: Идентификатор профиля.
        started: Время начала сессии.
        stats: Сгенерированная статистика клавиш.
        rng: Генератор случайных чисел.

    Returns:
        Сессия, готовая к сохранению.
    """
    attempts = sum(s.attempts for s in stats)
    errors = sum(s.errors for s in stats)
    duration = round(rng.uniform(40, 120), 1)
    correct = attempts - errors
    return Session(
        user_id=user_id,
        layout_id=LAYOUT_IDS[LAYOUT_RU],
        started_at=started.isoformat(timespec="seconds"),
        exercise_mode=rng.choice(list(ExerciseMode)),
        text_length=attempts,
        duration_sec=duration,
        wpm=round(correct / 5 / (duration / 60), 1),
        cpm=round(correct / (duration / 60), 1),
        error_rate=round(errors / attempts * 100, 1),
        errors_count=errors,
    )


def generate(database: Database, user_name: str, count: int, seed: int = 7) -> int:
    """Создать профиль (при необходимости) и заполнить его случайными сессиями.

    Args:
        database: Инициализированная база данных.
        user_name: Профиль, получающий сессии.
        count: Количество сессий.
        seed: Начальное значение генератора для воспроизводимых данных.

    Returns:
        Идентификатор профиля.
    """
    rng = random.Random(seed)
    users = UserRepository(database)
    try:
        user = users.create(user_name, LAYOUT_IDS[LAYOUT_RU])
    except DuplicateNameError:
        user = users.get_by_name(user_name)
    keys = [
        key
        for key in KeyRepository(database).get_by_layout(LAYOUT_IDS[LAYOUT_RU])
        if key.key_char.isalpha()
    ]
    sessions = SessionRepository(database)
    start = datetime.now() - timedelta(days=30)
    step = timedelta(days=30) / max(count, 1)
    for index in range(count):
        stats = _make_key_stats(keys, rng)
        session = _make_session(user.id, start + step * index, stats, rng)
        sessions.create(session, stats)
    return user.id


def main() -> None:
    """Разобрать аргументы командной строки и сгенерировать данные."""
    parser = argparse.ArgumentParser(description="Генерация тестовых сессий")
    parser.add_argument("--user", default="Тест", help="имя профиля")
    parser.add_argument("--sessions", type=int, default=20, help="число сессий")
    args = parser.parse_args()

    database = Database(DB_PATH)
    database.initialize()
    generate(database, args.user, args.sessions)
    print(f"Профилю «{args.user}» добавлено сессий: {args.sessions}")


if __name__ == "__main__":
    main()
