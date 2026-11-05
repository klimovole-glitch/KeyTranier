from __future__ import annotations
"""Репозиторий для ``tbl_sessions`` (журнал сессий)."""

import sqlite3
from collections.abc import Sequence

from keytrainer.data.exceptions import ValidationError
from keytrainer.data.models import ExerciseMode, KeyStat, Session
from keytrainer.data.repositories.base import BaseRepository

# ORDER BY нельзя параметризовать, поэтому столбцы сортировки берутся из белого списка.
SORTABLE_COLUMNS = frozenset(
    {"started_at", "exercise_mode", "wpm", "cpm", "error_rate", "duration_sec"}
)


class SessionRepository(BaseRepository[Session]):
    """Операции CRUD для тренировочных сессий."""

    table = "tbl_sessions"

    def _to_entity(self, row: sqlite3.Row) -> Session:
        """Преобразовать строку в :class:`Session`.

        Args:
            row: Строка ``tbl_sessions``.

        Returns:
            Сущность сессии.
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
        """Собрать значения столбцов сессии в порядке INSERT.

        Args:
            session: Сохраняемая сессия.

        Returns:
            Кортеж значений для плейсхолдеров.
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
        """Сохранить сессию вместе со статистикой по клавишам.

        Оба INSERT выполняются в ОДНОЙ транзакции (ТЗ, п. 3.2): если запись
        статистики не удалась, сессия тоже откатывается, поэтому в истории
        никогда не бывает сессии без данных по клавишам.

        Args:
            session: Результат сессии.
            key_stats: Статистика каждой нажатой клавиши.

        Returns:
            Идентификатор созданной сессии.
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

    def create_many(self, sessions: Sequence[Session]) -> int:
        """Сохранить много сессий без статистики клавиш в ОДНОЙ транзакции.

        Args:
            sessions: Сохраняемые сессии (используется при импорте CSV).

        Returns:
            Количество сохранённых сессий.
        """
        with self._db.connection() as conn:
            conn.executemany(
                "INSERT INTO tbl_sessions (user_id, layout_id, started_at, "
                "exercise_mode, text_length, duration_sec, wpm, cpm, error_rate, "
                "errors_count, is_completed) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [self._session_values(s) for s in sessions],
            )
        return len(sessions)

    def get_by_user(
        self,
        user_id: int,
        since: str | None = None,
        order_by: str = "started_at",
        descending: bool = True,
        limit: int | None = None,
    ) -> list[Session]:
        """Прочитать сессии профиля с фильтрацией и сортировкой.

        Args:
            user_id: Идентификатор профиля.
            since: Дата и время в формате ISO; только сессии, начатые не раньше неё.
            order_by: Столбец из :data:`SORTABLE_COLUMNS`.
            descending: Направление сортировки.
            limit: Максимальное количество сессий.

        Returns:
            Список сессий.

        Raises:
            ValidationError: Если ``order_by`` нет в белом списке.
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
        """Вернуть последнюю сессию профиля на раскладке.

        Args:
            user_id: Идентификатор профиля.
            layout_id: Идентификатор раскладки.

        Returns:
            Сессия или ``None``.
        """
        return self._fetch_one(
            "SELECT * FROM tbl_sessions WHERE user_id = ? AND layout_id = ? "
            "ORDER BY started_at DESC, id DESC LIMIT 1",
            (user_id, layout_id),
        )

    def get_best_wpm(self, user_id: int) -> float | None:
        """Вернуть личный рекорд профиля (только завершённые сессии).

        Args:
            user_id: Идентификатор профиля.

        Returns:
            Максимальная WPM или ``None``, если сессий нет.
        """
        with self._db.connection() as conn:
            return conn.execute(
                "SELECT MAX(wpm) FROM tbl_sessions "
                "WHERE user_id = ? AND is_completed = 1",
                (user_id,),
            ).fetchone()[0]

    def count_by_user(self, user_id: int) -> int:
        """Подсчитать сессии профиля.

        Args:
            user_id: Идентификатор профиля.

        Returns:
            Количество сессий.
        """
        with self._db.connection() as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM tbl_sessions WHERE user_id = ?", (user_id,)
            ).fetchone()[0]

    def update(self, session: Session) -> bool:
        """Перезаписать метрики существующей сессии.

        Args:
            session: Сессия с существующим id.

        Returns:
            ``True``, если сессия обновлена.
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
        """Удалить несколько сессий (их статистика по клавишам удаляется через CASCADE).

        Args:
            session_ids: Идентификаторы сессий.

        Returns:
            Количество удалённых сессий.
        """
        with self._db.connection() as conn:
            cursor = conn.executemany(
                "DELETE FROM tbl_sessions WHERE id = ?",
                [(session_id,) for session_id in session_ids],
            )
            return cursor.rowcount
