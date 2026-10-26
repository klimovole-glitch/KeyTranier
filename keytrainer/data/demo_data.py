"""Generator of test sessions for demonstration and acceptance tests.

Usage::

    python -m keytrainer.data.demo_data --user Тест --sessions 20
    python -m keytrainer.data.demo_data --user Нагрузка --sessions 10000

Keys "ф", "ы", "в" (ТЗ, п. 6.1) get a high error rate, so they must turn red
on the heatmap and appear in the top of problem keys.
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
    """Create random statistics for every key of a layout.

    Args:
        keys: Keys of the layout.
        rng: Random generator.

    Returns:
        Statistics with intentionally high error rate on :data:`WEAK_KEYS`.
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
    """Build a session whose metrics agree with the key statistics.

    Args:
        user_id: Profile id.
        started: Start time of the session.
        stats: Generated key statistics.
        rng: Random generator.

    Returns:
        Session ready to be saved.
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
    """Create a profile (if needed) and fill it with random sessions.

    Args:
        database: Initialized database.
        user_name: Profile that receives the sessions.
        count: Number of sessions.
        seed: Seed of the random generator for reproducible data.

    Returns:
        Id of the profile.
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
    """Parse command-line arguments and generate the data."""
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
