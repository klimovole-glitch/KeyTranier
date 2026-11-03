"""History of sessions: summary, chart data and deletion (ТЗ, п. 4.2.1)."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from keytrainer.data.models import Session
from keytrainer.data.repositories import SessionRepository
from keytrainer.engine.csv_importer import read_sessions
from keytrainer.engine.metrics import moving_average

SMOOTHING_WINDOW = 5  # N of the moving average (ТЗ, п. 4.3.1)
CHART_SESSIONS = 100
LAST_SESSIONS = 10


@dataclass(frozen=True)
class HistorySummary:
    """Numbers above the chart."""

    total_sessions: int
    best_wpm: float | None
    avg_wpm_last: float | None


@dataclass(frozen=True)
class ChartData:
    """Smoothed series for the WPM and error rate chart."""

    dates: tuple[datetime, ...]
    wpm: tuple[float, ...]
    error_rate: tuple[float, ...]


@dataclass(frozen=True)
class ImportSummary:
    """Result of the CSV import shown to the user."""

    added: int
    duplicates: int
    invalid: int


@dataclass(frozen=True)
class HistoryData:
    """Everything the history screen shows."""

    sessions: tuple[Session, ...]
    summary: HistorySummary
    chart: ChartData


class HistoryService:
    """Reads, imports and deletes sessions of a profile."""

    def __init__(self, sessions: SessionRepository) -> None:
        """Store the repository.

        Args:
            sessions: Session repository.
        """
        self._sessions = sessions

    def load(self, user_id: int, order_by: str, descending: bool) -> HistoryData:
        """Read the whole history of a profile (runs in a background thread).

        Args:
            user_id: Profile id.
            order_by: Column for sorting (white list of the repository).
            descending: Sort direction.

        Returns:
            Sessions, summary and chart data.
        """
        sessions = self._sessions.get_by_user(
            user_id, order_by=order_by, descending=descending
        )
        return HistoryData(
            sessions=tuple(sessions),
            summary=summarize(sessions),
            chart=chart_data(sessions),
        )

    def import_csv(
        self, path: Path, user_id: int, layout_id: int | None
    ) -> ImportSummary:
        """Add sessions from a CSV file; already existing ones are skipped.

        A session is a duplicate if the profile already has a session with
        the same start (to the minute, as in the file) and the same mode.

        Args:
            path: CSV file written by the export.
            user_id: Profile that receives the sessions.
            layout_id: Layout of the profile.

        Returns:
            Counts of added, duplicate and unreadable rows.

        Raises:
            ValidationError: The file is not a KeyTrainer history.
        """
        result = read_sessions(path, user_id, layout_id)
        known = {
            (s.started_at[:16], s.exercise_mode)
            for s in self._sessions.get_by_user(user_id)
        }
        fresh: list[Session] = []
        for session in result.sessions:
            key = (session.started_at[:16], session.exercise_mode)
            if key not in known:
                known.add(key)
                fresh.append(session)
        self._sessions.create_many(fresh)
        return ImportSummary(
            added=len(fresh),
            duplicates=len(result.sessions) - len(fresh),
            invalid=result.invalid,
        )

    def delete(self, session_ids: Sequence[int]) -> int:
        """Delete sessions (key statistics are removed by CASCADE).

        Args:
            session_ids: Ids of the sessions.

        Returns:
            Number of deleted sessions.
        """
        return self._sessions.delete_many(session_ids)


def _chronological(sessions: Sequence[Session]) -> list[Session]:
    """Completed sessions sorted from old to new.

    Args:
        sessions: Sessions in any order.

    Returns:
        Sorted completed sessions.
    """
    return sorted(
        (s for s in sessions if s.is_completed), key=lambda s: (s.started_at, s.id or 0)
    )


def summarize(sessions: Sequence[Session]) -> HistorySummary:
    """Calculate the summary of a history.

    Args:
        sessions: All sessions of a profile.

    Returns:
        Count, record and average WPM of the last 10 completed sessions.
    """
    completed = _chronological(sessions)
    last = completed[-LAST_SESSIONS:]
    return HistorySummary(
        total_sessions=len(sessions),
        best_wpm=max((s.wpm for s in completed), default=None),
        avg_wpm_last=sum(s.wpm for s in last) / len(last) if last else None,
    )


def chart_data(sessions: Sequence[Session]) -> ChartData:
    """Prepare smoothed WPM and error rate series for the chart.

    Args:
        sessions: All sessions of a profile.

    Returns:
        Series of the last 100 completed sessions, smoothed with N = 5.
    """
    recent = _chronological(sessions)[-CHART_SESSIONS:]
    return ChartData(
        dates=tuple(datetime.fromisoformat(s.started_at) for s in recent),
        wpm=tuple(moving_average([s.wpm for s in recent], SMOOTHING_WINDOW)),
        error_rate=tuple(
            moving_average([s.error_rate for s in recent], SMOOTHING_WINDOW)
        ),
    )
