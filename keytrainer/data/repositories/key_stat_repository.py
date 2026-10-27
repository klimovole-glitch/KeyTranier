"""Repository for ``tbl_key_stats`` (статистика клавиш в сессии)."""

import sqlite3
from dataclasses import dataclass

from keytrainer.data.models import KeyStat
from keytrainer.data.repositories.base import BaseRepository


@dataclass(frozen=True)
class KeyAggregate:
    """Summary of one key over many sessions (input for the heatmap)."""

    key_id: int
    attempts: int
    errors: int
    avg_latency_ms: float | None


class KeyStatRepository(BaseRepository[KeyStat]):
    """CRUD operations and aggregation of per-key statistics."""

    table = "tbl_key_stats"

    def _to_entity(self, row: sqlite3.Row) -> KeyStat:
        """Convert a row to :class:`KeyStat`.

        Args:
            row: Row of ``tbl_key_stats``.

        Returns:
            KeyStat entity.
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
        """Add statistics of one key to an existing session.

        Args:
            stat: Statistics with ``session_id`` set.

        Returns:
            Statistics with the id assigned by the database.
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
        """Read statistics of all keys of one session.

        Args:
            session_id: Session id.

        Returns:
            List of statistics.
        """
        return self._fetch_all(
            "SELECT * FROM tbl_key_stats WHERE session_id = ? ORDER BY key_id",
            (session_id,),
        )

    def update(self, stat: KeyStat) -> bool:
        """Overwrite counters of a statistics record.

        Args:
            stat: Statistics with an existing id.

        Returns:
            ``True`` if the record was updated.
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
        """Sum statistics of every key over the sessions of a period.

        The average latency is weighted by the number of attempts, so a
        session with 100 presses counts more than a session with 2 presses.

        Args:
            user_id: Profile id.
            layout_id: Layout whose keys are aggregated.
            since: ISO date-time of the period start, ``None`` — all time.
            session_id: Only this session (period "последняя сессия").

        Returns:
            One aggregate per key that was pressed at least once.
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
