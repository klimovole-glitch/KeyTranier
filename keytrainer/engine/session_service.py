"""Saving a finished session and preparing the results card (ТЗ, п. 4.2.1)."""

from dataclasses import dataclass
from datetime import datetime

from keytrainer.data.models import ExerciseMode, KeyStat, Session
from keytrainer.data.repositories import (
    KeyRepository,
    LayoutRepository,
    SessionRepository,
)
from keytrainer.engine.typing_session import TypingSession

COMPARE_LAST_SESSIONS = 10
WORST_KEYS_ON_CARD = 3


@dataclass(frozen=True)
class WorstKey:
    """A key with many errors in the finished session."""

    key_char: str
    errors: int
    attempts: int


@dataclass(frozen=True)
class SessionResult:
    """Everything the results card shows."""

    session: Session
    best_wpm_before: float | None
    avg_wpm_last: float | None
    avg_error_rate_last: float | None
    worst_keys: tuple[WorstKey, ...]

    @property
    def is_record(self) -> bool:
        """``True`` if the session beats the personal record."""
        return self.session.is_completed and (
            self.best_wpm_before is None or self.session.wpm > self.best_wpm_before
        )


class SessionService:
    """Turns a :class:`TypingSession` into database records."""

    def __init__(
        self,
        sessions: SessionRepository,
        keys: KeyRepository,
        layouts: LayoutRepository,
    ) -> None:
        """Store repositories.

        Args:
            sessions: Session repository.
            keys: Key repository (character -> key id).
            layouts: Layout repository (layout name -> id).
        """
        self._sessions = sessions
        self._keys = keys
        self._layouts = layouts
        self._key_ids: dict[str, dict[str, int]] = {}

    def _key_id_map(self, layout_name: str, layout_id: int) -> dict[str, int]:
        """Return the cached map "character -> key id" of a layout.

        Args:
            layout_name: Layout name.
            layout_id: Layout id.

        Returns:
            Map of base characters to key ids.
        """
        if layout_name not in self._key_ids:
            self._key_ids[layout_name] = {
                key.key_char: key.id for key in self._keys.get_by_layout(layout_id)
            }
        return self._key_ids[layout_name]

    def build_session(
        self,
        typing: TypingSession,
        user_id: int,
        layout_id: int,
        mode: ExerciseMode,
        started_at: datetime,
    ) -> Session:
        """Create a :class:`Session` from the metrics of a typing session.

        Args:
            typing: Finished typing session.
            user_id: Profile id.
            layout_id: Layout id.
            mode: Exercise mode.
            started_at: Wall-clock start time.

        Returns:
            Unsaved session with rounded metrics.
        """
        snap = typing.snapshot()
        return Session(
            user_id=user_id,
            layout_id=layout_id,
            started_at=started_at.isoformat(timespec="seconds"),
            exercise_mode=mode,
            text_length=len(typing.text),
            duration_sec=round(snap.elapsed_sec, 2),
            wpm=round(snap.wpm, 1),
            cpm=round(snap.cpm, 1),
            error_rate=round(snap.error_rate, 1),
            errors_count=snap.errors,
            is_completed=typing.is_completed,
        )

    def build_key_stats(self, typing: TypingSession, layout_id: int) -> list[KeyStat]:
        """Convert per-character counters into ``KeyStat`` rows.

        Args:
            typing: Finished typing session.
            layout_id: Layout id.

        Returns:
            Statistics for keys that exist in ``tbl_keys``.
        """
        key_ids = self._key_id_map(typing.layout_name, layout_id)
        stats = []
        for char, counter in typing.key_counters.items():
            if char in key_ids:
                latency = counter.avg_latency_ms
                stats.append(
                    KeyStat(
                        key_id=key_ids[char],
                        attempts=counter.attempts,
                        errors=counter.errors,
                        avg_latency_ms=round(latency, 1) if latency else None,
                    )
                )
        return stats

    def save(
        self,
        typing: TypingSession,
        user_id: int,
        mode: ExerciseMode,
        started_at: datetime,
    ) -> SessionResult:
        """Save a finished session in one transaction and compare it.

        The record and the average are read BEFORE saving, so the card
        compares the new result with previous sessions only.

        Args:
            typing: Finished typing session.
            user_id: Profile id.
            mode: Exercise mode.
            started_at: Wall-clock start time.

        Returns:
            Data for the results card.

        Raises:
            ValueError: If the layout is unknown.
        """
        layout = self._layouts.get_by_name(typing.layout_name)
        if layout is None:
            raise ValueError(f"Unknown layout {typing.layout_name}")
        best_before = self._sessions.get_best_wpm(user_id)
        previous = [
            s
            for s in self._sessions.get_by_user(user_id, limit=COMPARE_LAST_SESSIONS)
            if s.is_completed
        ]
        session = self.build_session(typing, user_id, layout.id, mode, started_at)
        self._sessions.create(session, self.build_key_stats(typing, layout.id))
        return SessionResult(
            session=session,
            best_wpm_before=best_before,
            avg_wpm_last=_average([s.wpm for s in previous]),
            avg_error_rate_last=_average([s.error_rate for s in previous]),
            worst_keys=worst_keys(typing),
        )


def worst_keys(typing: TypingSession, limit: int = WORST_KEYS_ON_CARD) -> tuple:
    """Pick the keys with the most errors in a session.

    Args:
        typing: Typing session.
        limit: How many keys to return.

    Returns:
        Keys with at least one error, worst first.
    """
    ranked = sorted(
        (
            WorstKey(char, counter.errors, counter.attempts)
            for char, counter in typing.key_counters.items()
            if counter.errors
        ),
        key=lambda k: (k.errors, k.errors / k.attempts),
        reverse=True,
    )
    return tuple(ranked[:limit])


def _average(values: list[float]) -> float | None:
    """Average of a list, ``None`` for an empty list.

    Args:
        values: Numbers.

    Returns:
        Arithmetic mean or ``None``.
    """
    return sum(values) / len(values) if values else None
