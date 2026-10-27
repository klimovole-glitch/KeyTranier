"""Saving sessions and the results card."""

from datetime import datetime

from keytrainer.data.models import ExerciseMode
from keytrainer.data.repositories import (
    KeyRepository,
    KeyStatRepository,
    LayoutRepository,
    SessionRepository,
    UserRepository,
)
from keytrainer.engine.session_service import SessionService
from keytrainer.engine.typing_session import TypingSession
from tests.test_metrics import FakeClock


def _finished_session(text: str, keys: str) -> TypingSession:
    """Type keys into a new session.

    Args:
        text: Exercise text.
        keys: Keystrokes.

    Returns:
        Finished session.
    """
    session = TypingSession(text, "RU_JCUKEN", clock=FakeClock(0.2))
    for key in keys:
        session._clock.tick()
        session.press(key)
    return session


def test_save_and_compare(database):
    """A session is saved with key stats and compared with the previous ones."""
    user = UserRepository(database).create("Олег")
    sessions = SessionRepository(database)
    service = SessionService(
        sessions, KeyRepository(database), LayoutRepository(database)
    )
    first = service.save(
        _finished_session("фыва", "фыва"), user.id, ExerciseMode.KEYS, datetime.now()
    )
    assert first.is_record and first.avg_wpm_last is None

    second = service.save(
        _finished_session("фыва", "фыпа"),
        user.id,
        ExerciseMode.KEYS,
        datetime.now(),
    )
    assert second.avg_wpm_last == first.session.wpm
    assert second.worst_keys[0].key_char == "в"
    stats = KeyStatRepository(database).get_by_session(second.session.id)
    assert sum(s.errors for s in stats) == 1
    assert sessions.count_by_user(user.id) == 2
