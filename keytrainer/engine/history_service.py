from __future__ import annotations
"""История сессий: сводка, данные графика и удаление (ТЗ, п. 4.2.1)."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from keytrainer.data.models import Session
from keytrainer.data.repositories import SessionRepository
from keytrainer.engine.csv_importer import read_sessions
from keytrainer.engine.metrics import moving_average

SMOOTHING_WINDOW = 5  # N скользящего среднего (ТЗ, п. 4.3.1)
CHART_SESSIONS = 100
LAST_SESSIONS = 10


@dataclass(frozen=True)
class HistorySummary:
    """Числа над графиком."""

    total_sessions: int
    best_wpm: float | None
    avg_wpm_last: float | None


@dataclass(frozen=True)
class ChartData:
    """Сглаженные ряды для графика WPM и доли ошибок."""

    dates: tuple[datetime, ...]
    wpm: tuple[float, ...]
    error_rate: tuple[float, ...]


@dataclass(frozen=True)
class ImportSummary:
    """Результат импорта CSV, показываемый пользователю."""

    added: int
    duplicates: int
    invalid: int


@dataclass(frozen=True)
class HistoryData:
    """Всё, что показывает экран истории."""

    sessions: tuple[Session, ...]
    summary: HistorySummary
    chart: ChartData


class HistoryService:
    """Читает, импортирует и удаляет сессии профиля."""

    def __init__(self, sessions: SessionRepository) -> None:
        """Сохранить репозиторий.

        Args:
            sessions: Репозиторий сессий.
        """
        self._sessions = sessions

    def load(self, user_id: int, order_by: str, descending: bool) -> HistoryData:
        """Прочитать всю историю профиля (выполняется в фоновом потоке).

        Args:
            user_id: Идентификатор профиля.
            order_by: Столбец сортировки (белый список репозитория).
            descending: Направление сортировки.

        Returns:
            Сессии, сводка и данные графика.
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
        """Добавить сессии из файла CSV; уже существующие пропускаются.

        Сессия считается дубликатом, если у профиля уже есть сессия с тем же
        началом (с точностью до минуты, как в файле) и тем же режимом.

        Args:
            path: Файл CSV, записанный экспортом.
            user_id: Профиль, получающий сессии.
            layout_id: Раскладка профиля.

        Returns:
            Количество добавленных, повторяющихся и нечитаемых строк.

        Raises:
            ValidationError: Файл не является историей KeyTrainer.
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
        """Удалить сессии (статистика клавиш удаляется через CASCADE).

        Args:
            session_ids: Идентификаторы сессий.

        Returns:
            Количество удалённых сессий.
        """
        return self._sessions.delete_many(session_ids)


def _chronological(sessions: Sequence[Session]) -> list[Session]:
    """Завершённые сессии, отсортированные от старых к новым.

    Args:
        sessions: Сессии в произвольном порядке.

    Returns:
        Отсортированные завершённые сессии.
    """
    return sorted(
        (s for s in sessions if s.is_completed), key=lambda s: (s.started_at, s.id or 0)
    )


def summarize(sessions: Sequence[Session]) -> HistorySummary:
    """Вычислить сводку по истории.

    Args:
        sessions: Все сессии профиля.

    Returns:
        Количество, рекорд и средняя WPM последних 10 завершённых сессий.
    """
    completed = _chronological(sessions)
    last = completed[-LAST_SESSIONS:]
    return HistorySummary(
        total_sessions=len(sessions),
        best_wpm=max((s.wpm for s in completed), default=None),
        avg_wpm_last=sum(s.wpm for s in last) / len(last) if last else None,
    )


def chart_data(sessions: Sequence[Session]) -> ChartData:
    """Подготовить сглаженные ряды WPM и доли ошибок для графика.

    Args:
        sessions: Все сессии профиля.

    Returns:
        Ряды последних 100 завершённых сессий, сглаженные с N = 5.
    """
    recent = _chronological(sessions)[-CHART_SESSIONS:]
    return ChartData(
        dates=tuple(datetime.fromisoformat(s.started_at) for s in recent),
        wpm=tuple(moving_average([s.wpm for s in recent], SMOOTHING_WINDOW)),
        error_rate=tuple(
            moving_average([s.error_rate for s in recent], SMOOTHING_WINDOW)
        ),
    )
