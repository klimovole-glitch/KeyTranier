"""Tests of CRUD operations in the repositories."""

import pytest

from keytrainer.data.demo_data import generate
from keytrainer.data.exceptions import DuplicateNameError, ValidationError
from keytrainer.data.models import ExerciseMode, KeyStat, Session, Theme
from keytrainer.data.repositories import (
    KeyStatRepository,
    SessionRepository,
    TextRepository,
    UserRepository,
    WordRepository,
)


def _session(user_id: int, started_at: str = "2026-10-26T10:00:00") -> Session:
    """Build a session with fixed metrics.

    Args:
        user_id: Profile id.
        started_at: Start time.

    Returns:
        Unsaved session.
    """
    return Session(
        user_id=user_id,
        layout_id=1,
        started_at=started_at,
        exercise_mode=ExerciseMode.WORDS,
        text_length=250,
        duration_sec=60.0,
        wpm=48.0,
        cpm=240.0,
        error_rate=4.0,
        errors_count=10,
    )


def test_user_crud(database):
    """A profile can be created, read, renamed, configured and deleted."""
    users = UserRepository(database)
    user = users.create("  Олег ", layout_id=1)
    assert user.user_name == "Олег"
    assert user.theme == Theme.LIGHT and user.font_size == 18

    assert users.rename(user.id, "Олег К.")
    user.theme, user.font_size = Theme.DARK, 22
    assert users.update_settings(user)
    loaded = users.get_by_name("Олег К.")
    assert loaded.theme == Theme.DARK and loaded.font_size == 22

    assert users.delete(user.id)
    assert users.get_by_id(user.id) is None


def test_user_name_rules(database):
    """Empty and duplicate profile names are rejected."""
    users = UserRepository(database)
    with pytest.raises(ValidationError):
        users.create("   ")
    users.create("Анна")
    with pytest.raises(DuplicateNameError):
        users.create("Анна")


def test_sql_injection_is_stored_as_plain_text(database):
    """A malicious name is saved literally and does not drop tables."""
    users = UserRepository(database)
    evil = "x'); DROP TABLE tbl_users;--"
    users.create(evil)
    assert users.get_by_name(evil) is not None
    assert users.count() == 2  # default "Гость" + the new profile


def test_session_saved_with_stats_in_one_transaction(database):
    """Session and its key statistics are written together."""
    user = UserRepository(database).create("Тест")
    sessions = SessionRepository(database)
    stats = [KeyStat(key_id=1, attempts=10, errors=2, avg_latency_ms=210.0)]
    session_id = sessions.create(_session(user.id), stats)

    saved = KeyStatRepository(database).get_by_session(session_id)
    assert len(saved) == 1 and saved[0].errors == 2


def test_failed_stats_roll_back_session(database):
    """If a key statistics row is invalid, the session is not saved either."""
    user = UserRepository(database).create("Тест")
    sessions = SessionRepository(database)
    bad_stats = [KeyStat(key_id=99999, attempts=1, errors=0, avg_latency_ms=None)]
    with pytest.raises(Exception):
        sessions.create(_session(user.id), bad_stats)
    assert sessions.count_by_user(user.id) == 0


def test_session_filter_and_sort(database):
    """Sessions are filtered by period and sorted by a white-listed column."""
    user = UserRepository(database).create("Тест")
    sessions = SessionRepository(database)
    old = _session(user.id, "2026-01-01T09:00:00")
    new = _session(user.id, "2026-10-25T09:00:00")
    new.wpm = 60.0
    sessions.create(old)
    sessions.create(new)

    recent = sessions.get_by_user(user.id, since="2026-10-01")
    assert [s.started_at for s in recent] == ["2026-10-25T09:00:00"]
    by_wpm = sessions.get_by_user(user.id, order_by="wpm", descending=True)
    assert by_wpm[0].wpm == 60.0
    assert sessions.get_best_wpm(user.id) == 60.0
    with pytest.raises(ValidationError):
        sessions.get_by_user(user.id, order_by="wpm; DROP TABLE tbl_users")


def test_session_update_and_delete_many(database):
    """Session metrics can be updated and several sessions deleted at once."""
    user = UserRepository(database).create("Тест")
    sessions = SessionRepository(database)
    first = _session(user.id)
    sessions.create(first)
    second_id = sessions.create(_session(user.id))

    first.wpm = 55.5
    assert sessions.update(first)
    assert sessions.get_by_id(first.id).wpm == 55.5
    assert sessions.delete_many([first.id, second_id]) == 2


def test_cascade_delete_profile(database):
    """Deleting a profile deletes its sessions and key statistics."""
    users = UserRepository(database)
    user = users.create("Удаляемый")
    session_id = SessionRepository(database).create(
        _session(user.id), [KeyStat(1, 5, 1, 200.0)]
    )
    users.delete(user.id)
    assert SessionRepository(database).get_by_id(session_id) is None
    assert KeyStatRepository(database).get_by_session(session_id) == []


def test_word_and_text_crud(database):
    """Words and user texts support create, update and delete."""
    words = WordRepository(database)
    word = words.create(1, "Клавиатурный")
    assert word.word == "клавиатурный"
    with pytest.raises(DuplicateNameError):
        words.create(1, "клавиатурный")
    assert words.update(word.id, "тренажерный")
    assert words.delete(word.id)

    texts = TextRepository(database)
    text = texts.create(1, "Мой текст", "Первая  строка\nвторая строка")
    assert text.content == "Первая строка вторая строка"
    assert texts.get_by_layout(1, custom=True) == [text]
    text.title = "Новое название"
    assert texts.update(text)
    assert texts.delete(text.id)


def test_demo_data_makes_weak_keys_visible(database):
    """Demo sessions produce high error rate on "ф", "ы", "в"."""
    user_id = generate(database, "Демо", 20)
    aggregates = KeyStatRepository(database).aggregate(user_id, layout_id=1)
    with database.connection() as conn:
        chars = dict(conn.execute("SELECT id, key_char FROM tbl_keys").fetchall())
    worst = sorted(aggregates, key=lambda a: a.errors / a.attempts, reverse=True)
    assert {chars[a.key_id] for a in worst[:3]} == {"ф", "ы", "в"}
