"""Repository for ``tbl_sessions`` (журнал сессий)."""

import sqlite3
from collections.abc import Sequence

from keytrainer.data.exceptions import ValidationError
from keytrainer.data.models import ExerciseMode, KeyStat, Session
from keytrainer.data.repositories.base import BaseRepository

# ORDER BY cannot be parameterized, so sorting columns come from a white list.
SORTABLE_COLUMNS = frozenset(
    {"started_at", "exercise_mode", "wpm", "cpm", "error_rate", "duration_sec"}
)


class SessionRepository(BaseRepository[Session]):
    """CRUD operations for training sessions."""

    table = "tbl_sessions"

    def _to_entity(self, row: sqlite3.Row) -> Session:
        """Convert a row to :class:`Session`.

        Args:
            row: Row of ``tbl_sessions``.

        Returns:
            Session entity.
        """
        return Session(
            id=row["id"],
            user_id=row["user_id"],
            layout_id=row["layout_id"],
            started_at=row["started_at"],
            exercise_mode=ExerciseMode(row["exercise_mode"]),
            text_length=row["text_length"],
            duration_sec=row["duration_sec"],
            wpm=row["wpm"],
            cpm=row["cpm"],
            error_rate=row["error_rate"],
            errors_count=row["errors_count"],
            is_completed=bool(row["is_completed"]),
        )

    @staticmethod
    def _session_values(session: Session) -> tuple:
        """Collect column values of a session in INSERT order.

        Args:
            session: Session to save.

        Returns:
            Tuple of values for the placeholders.
        """
        return (
            session.user_id,
            session.layout_id,
            session.started_at,
            ExerciseMode(session.exercise_mode).value,
            session.text_length,
            session.duration_sec,
            session.wpm,
            session.cpm,
            session.error_rate,
            session.errors_count,
            int(session.is_completed),
        )

    def create(self, session: Session, key_stats: Sequence[KeyStat] = ()) -> int:
        """Save a session together with its per-key statistics.

        Both inserts run in ONE transaction (ТЗ, п. 3.2): if writing the
        statistics fails, the session is rolled back too, so the history
        never contains a session without its key data.

        Args:
            session: Session result.
            key_stats: Statistics of every pressed key.

        Returns:
            Id of the created session.
        """
        with self._db.connection() as conn:
            cursor = conn.execute(
                "INSERT INTO tbl_sessions (user_id, layout_id, started_at, "
                "exercise_mode, text_length, duration_sec, wpm, cpm, error_rate, "
                "errors_count, is_completed) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                self._session_values(session),
            )
            session_id = cursor.lastrowid
            conn.executemany(
                "INSERT INTO tbl_key_stats "
                "(session_id, key_id, attempts, errors, avg_latency_ms) "
                "VALUES (?, ?, ?, ?, ?)",
                [
                    (session_id, s.key_id, s.attempts, s.errors, s.avg_latency_ms)
                    for s in key_stats
                ],
            )
        session.id = session_id
        return session_id

    def get_by_user(
        self,
        user_id: int,
        since: str | None = None,
        order_by: str = "started_at",
        descending: bool = True,
        limit: int | None = None,
    ) -> list[Session]:
        """Read sessions of a profile with filtering and sorting.

        Args:
            user_id: Profile id.
            since: ISO date-time; only sessions started at or after it.
            order_by: Column from :data:`SORTABLE_COLUMNS`.
            descending: Sort direction.
            limit: Maximum number of sessions.

        Returns:
            List of sessions.

        Raises:
            ValidationError: If ``order_by`` is not in the white list.
        """
        if order_by not in SORTABLE_COLUMNS:
            raise ValidationError(f"Недопустимое поле сортировки: {order_by}")
        sql = "SELECT * FROM tbl_sessions WHERE user_id = ?"
        params: list = [user_id]
        if since is not None:
            sql += " AND started_at >= ?"
            params.append(since)
        sql += f" ORDER BY {order_by} {'DESC' if descending else 'ASC'}, id DESC"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        return self._fetch_all(sql, params)

    def get_last(self, user_id: int, layout_id: int) -> Session | None:
        """Return the latest session of a profile on a layout.

        Args:
            user_id: Profile id.
            layout_id: Layout id.

        Returns:
            Session or ``None``.
        """
        return self._fetch_one(
            "SELECT * FROM tbl_sessions WHERE user_id = ? AND layout_id = ? "
            "ORDER BY started_at DESC, id DESC LIMIT 1",
            (user_id, layout_id),
        )

    def get_best_wpm(self, user_id: int) -> float | None:
        """Return the personal record of a profile (completed sessions only).

        Args:
            user_id: Profile id.

        Returns:
            Maximal WPM or ``None`` if there are no sessions.
        """
        with self._db.connection() as conn:
            return conn.execute(
                "SELECT MAX(wpm) FROM tbl_sessions "
                "WHERE user_id = ? AND is_completed = 1",
                (user_id,),
            ).fetchone()[0]

    def count_by_user(self, user_id: int) -> int:
        """Count sessions of a profile.

        Args:
            user_id: Profile id.

        Returns:
            Number of sessions.
        """
        with self._db.connection() as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM tbl_sessions WHERE user_id = ?", (user_id,)
            ).fetchone()[0]

    def update(self, session: Session) -> bool:
        """Overwrite metrics of an existing session.

        Args:
            session: Session with an existing id.

        Returns:
            ``True`` if the session was updated.
        """
        cursor = self._execute(
            "UPDATE tbl_sessions SET duration_sec = ?, wpm = ?, cpm = ?, "
            "error_rate = ?, errors_count = ?, is_completed = ? WHERE id = ?",
            (
                session.duration_sec,
                session.wpm,
                session.cpm,
                session.error_rate,
                session.errors_count,
                int(session.is_completed),
                session.id,
            ),
        )
        return cursor.rowcount > 0

    def delete_many(self, session_ids: Sequence[int]) -> int:
        """Delete several sessions (their key statistics go by CASCADE).

        Args:
            session_ids: Ids of the sessions.

        Returns:
            Number of deleted sessions.
        """
        with self._db.connection() as conn:
            cursor = conn.executemany(
                "DELETE FROM tbl_sessions WHERE id = ?",
                [(session_id,) for session_id in session_ids],
            )
            return cursor.rowcount
