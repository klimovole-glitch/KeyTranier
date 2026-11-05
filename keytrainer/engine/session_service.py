from __future__ import annotations
"""Сохранение завершённой сессии и подготовка карточки результатов (ТЗ, п. 4.2.1)."""

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
    """Клавиша с большим числом ошибок в завершённой сессии."""

    key_char: str
    errors: int
    attempts: int


@dataclass(frozen=True)
class SessionResult:
    """Всё, что показывает карточка результатов."""

    session: Session
    best_wpm_before: float | None
    avg_wpm_last: float | None
    avg_error_rate_last: float | None
    worst_keys: tuple[WorstKey, ...]

    @property
    def is_record(self) -> bool:
        """``True``, если сессия побила личный рекорд."""
        return self.session.is_completed and (
            self.best_wpm_before is None or self.session.wpm > self.best_wpm_before
        )


class SessionService:
    """Превращает :class:`TypingSession` в записи базы данных."""

    def __init__(
        self,
        sessions: SessionRepository,
        keys: KeyRepository,
        layouts: LayoutRepository,
    ) -> None:
        """Сохранить репозитории.

        Args:
            sessions: Репозиторий сессий.
            keys: Репозиторий клавиш (символ -> id клавиши).
            layouts: Репозиторий раскладок (имя раскладки -> id).
        """
        self._sessions = sessions
        self._keys = keys
        self._layouts = layouts
        self._key_ids: dict[str, dict[str, int]] = {}

    def _key_id_map(self, layout_name: str, layout_id: int) -> dict[str, int]:
        """Вернуть кэшированное соответствие «символ -> id клавиши» для раскладки.

        Args:
            layout_name: Имя раскладки.
            layout_id: Идентификатор раскладки.

        Returns:
            Соответствие базовых символов идентификаторам клавиш.
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
        """Создать :class:`Session` из метрик сессии набора.

        Args:
            typing: Завершённая сессия набора.
            user_id: Идентификатор профиля.
            layout_id: Идентификатор раскладки.
            mode: Режим упражнения.
            started_at: Время начала по настенным часам.

        Returns:
            Несохранённая сессия с округлёнными метриками.
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
        """Преобразовать счётчики по символам в строки ``KeyStat``.

        Args:
            typing: Завершённая сессия набора.
            layout_id: Идентификатор раскладки.

        Returns:
            Статистика для клавиш, существующих в ``tbl_keys``.
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
        """Сохранить завершённую сессию в одной транзакции и сравнить её.

        Рекорд и среднее считываются ДО сохранения, поэтому карточка
        сравнивает новый результат только с предыдущими сессиями.

        Args:
            typing: Завершённая сессия набора.
            user_id: Идентификатор профиля.
            mode: Режим упражнения.
            started_at: Время начала по настенным часам.

        Returns:
            Данные для карточки результатов.

        Raises:
            ValueError: Если раскладка неизвестна.
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
    """Выбрать клавиши с наибольшим числом ошибок в сессии.

    Args:
        typing: Сессия набора.
        limit: Сколько клавиш вернуть.

    Returns:
        Клавиши хотя бы с одной ошибкой, худшие первыми.
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
    """Среднее значение списка, ``None`` для пустого списка.

    Args:
        values: Числа.

    Returns:
        Среднее арифметическое или ``None``.
    """
    return sum(values) / len(values) if values else None
