"""Base class for repositories (pattern Repository, ТЗ, п. 1.2).

Every SQL statement in the project uses ``?`` placeholders: values typed by
the user are never concatenated into SQL text, which rules out SQL
injection. Table and column names cannot be parameters in SQLite, so they
come only from class constants or from white lists.
"""

import sqlite3
from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any, ClassVar, Generic, TypeVar

from keytrainer.data.database import Database

EntityT = TypeVar("EntityT")


class BaseRepository(ABC, Generic[EntityT]):
    """Common Read and Delete operations for one table.

    Subclasses set :attr:`table`, implement :meth:`_to_entity` and add
    their own Create and Update methods.
    """

    table: ClassVar[str]

    def __init__(self, database: Database) -> None:
        """Store the database gateway.

        Args:
            database: Initialized :class:`Database`.
        """
        self._db = database

    @abstractmethod
    def _to_entity(self, row: sqlite3.Row) -> EntityT:
        """Convert a database row to an entity object.

        Args:
            row: Row returned by ``SELECT *``.

        Returns:
            Entity dataclass instance.
        """

    def _fetch_all(self, sql: str, params: Sequence[Any] = ()) -> list[EntityT]:
        """Run a SELECT and convert every row to an entity.

        Args:
            sql: Parameterized SQL query.
            params: Values for the ``?`` placeholders.

        Returns:
            List of entities (empty if nothing found).
        """
        with self._db.connection() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._to_entity(row) for row in rows]

    def _fetch_one(self, sql: str, params: Sequence[Any] = ()) -> EntityT | None:
        """Run a SELECT and convert the first row to an entity.

        Args:
            sql: Parameterized SQL query.
            params: Values for the ``?`` placeholders.

        Returns:
            Entity or ``None`` if nothing found.
        """
        with self._db.connection() as conn:
            row = conn.execute(sql, params).fetchone()
        return self._to_entity(row) if row else None

    def _execute(self, sql: str, params: Sequence[Any] = ()) -> sqlite3.Cursor:
        """Run a data-changing statement in its own transaction.

        Args:
            sql: Parameterized INSERT, UPDATE or DELETE.
            params: Values for the ``?`` placeholders.

        Returns:
            Cursor with ``lastrowid`` and ``rowcount``.
        """
        with self._db.connection() as conn:
            return conn.execute(sql, params)

    def get_by_id(self, entity_id: int) -> EntityT | None:
        """Read one record by primary key.

        Args:
            entity_id: Value of the ``id`` column.

        Returns:
            Entity or ``None``.
        """
        return self._fetch_one(f"SELECT * FROM {self.table} WHERE id = ?", (entity_id,))

    def get_all(self) -> list[EntityT]:
        """Read all records ordered by id.

        Returns:
            List of entities.
        """
        return self._fetch_all(f"SELECT * FROM {self.table} ORDER BY id")

    def count(self) -> int:
        """Count records in the table.

        Returns:
            Number of rows.
        """
        with self._db.connection() as conn:
            return conn.execute(f"SELECT COUNT(*) FROM {self.table}").fetchone()[0]

    def delete(self, entity_id: int) -> bool:
        """Delete one record by primary key.

        Args:
            entity_id: Value of the ``id`` column.

        Returns:
            ``True`` if a record was deleted.
        """
        cursor = self._execute(f"DELETE FROM {self.table} WHERE id = ?", (entity_id,))
        return cursor.rowcount > 0
