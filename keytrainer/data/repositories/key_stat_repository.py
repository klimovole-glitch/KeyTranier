from __future__ import annotations
"""Репозиторий для ``tbl_key_stats`` (статистика клавиш в сессии)."""

import sqlite3
from dataclasses import dataclass

from keytrainer.data.models import KeyStat
from keytrainer.data.repositories.base import BaseRepository


@dataclass(frozen=True)
class KeyAggregate:
    """Сводка по одной клавише за много сессий (входные данные тепловой карты)."""

    key_id: int
    attempts: int
    errors: int
    avg_latency_ms: float | None


class KeyStatRepository(BaseRepository[KeyStat]):
    """Операции CRUD и агрегация статистики по клавишам."""

    table = "tbl_key_stats"

    def _to_entity(self, row: sqlite3.Row) -> KeyStat:
        """Преобразовать строку в :class:`KeyStat`.

        Args:
            row: Строка ``tbl_key_stats``.

        Returns:
            Сущность KeyStat.
        """
        return KeyStat(
            id=row["id"],
            session_id=row["session_id"],
            key_id=row["key_id"],
            attempts=row["attempts"],
            errors=row["errors"],
            avg_latency_ms=row["avg_latency_ms"],
        )

    def create(self, stat: KeyStat) -> KeyStat:
        """Добавить статистику одной клавиши в существующую сессию.

        Args:
            stat: Статистика с заданным ``session_id``.

        Returns:
            Статистика с идентификатором, присвоенным базой данных.
        """
        cursor = self._execute(
            "INSERT INTO tbl_key_stats "
            "(session_id, key_id, attempts, errors, avg_latency_ms) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                stat.session_id,
                stat.key_id,
                stat.attempts,
                stat.errors,
                stat.avg_latency_ms,
            ),
        )
        stat.id = cursor.lastrowid
        return stat

    def get_by_session(self, session_id: int) -> list[KeyStat]:
        """Прочитать статистику всех клавиш одной сессии.

        Args:
            session_id: Идентификатор сессии.

        Returns:
            Список статистики.
        """
        return self._fetch_all(
            "SELECT * FROM tbl_key_stats WHERE session_id = ? ORDER BY key_id",
            (session_id,),
        )

    def update(self, stat: KeyStat) -> bool:
        """Перезаписать счётчики записи статистики.

        Args:
            stat: Статистика с существующим id.

        Returns:
            ``True``, если запись обновлена.
        """
        cursor = self._execute(
            "UPDATE tbl_key_stats SET attempts = ?, errors = ?, avg_latency_ms = ? "
            "WHERE id = ?",
            (stat.attempts, stat.errors, stat.avg_latency_ms, stat.id),
        )
        return cursor.rowcount > 0

    def aggregate(
        self,
        user_id: int,
        layout_id: int,
        since: str | None = None,
        session_id: int | None = None,
    ) -> list[KeyAggregate]:
        """Просуммировать статистику каждой клавиши по сессиям периода.

        Средняя задержка взвешивается по числу попыток, поэтому сессия
        со 100 нажатиями весит больше, чем сессия с 2 нажатиями.

        Args:
            user_id: Идентификатор профиля.
            layout_id: Раскладка, клавиши которой агрегируются.
            since: Дата и время начала периода в формате ISO, ``None`` — всё время.
            session_id: Только эта сессия (период «последняя сессия»).

        Returns:
            По одному агрегату на каждую клавишу, нажатую хотя бы раз.
        """
        sql = (
            "SELECT ks.key_id, SUM(ks.attempts) AS attempts, "
            "SUM(ks.errors) AS errors, "
            "SUM(ks.avg_latency_ms * ks.attempts) / SUM(ks.attempts) AS latency "
            "FROM tbl_key_stats ks "
            "JOIN tbl_sessions s ON s.id = ks.session_id "
            "WHERE s.user_id = ? AND s.layout_id = ?"
        )
        params: list = [user_id, layout_id]
        if since is not None:
            sql += " AND s.started_at >= ?"
            params.append(since)
        if session_id is not None:
            sql += " AND s.id = ?"
            params.append(session_id)
        sql += " GROUP BY ks.key_id"
        with self._db.connection() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [
            KeyAggregate(row["key_id"], row["attempts"], row["errors"], row["latency"])
            for row in rows
        ]
