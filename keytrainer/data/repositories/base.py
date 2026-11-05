from __future__ import annotations
"""Базовый класс репозиториев (паттерн «Репозиторий», ТЗ, п. 1.2).

Каждая SQL-инструкция в проекте использует плейсхолдеры ``?``: значения,
введённые пользователем, никогда не вставляются в текст SQL, что исключает
SQL-инъекции. Имена таблиц и столбцов в SQLite не могут быть параметрами,
поэтому они берутся только из констант класса или из белых списков.
"""

import sqlite3
from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any, ClassVar, Generic, TypeVar

from keytrainer.data.database import Database

EntityT = TypeVar("EntityT")


class BaseRepository(ABC, Generic[EntityT]):
    """Общие операции чтения и удаления для одной таблицы.

    Подклассы задают :attr:`table`, реализуют :meth:`_to_entity` и добавляют
    собственные методы создания и обновления.
    """

    table: ClassVar[str]

    def __init__(self, database: Database) -> None:
        """Сохранить шлюз к базе данных.

        Args:
            database: Инициализированная :class:`Database`.
        """
        self._db = database

    @abstractmethod
    def _to_entity(self, row: sqlite3.Row) -> EntityT:
        """Преобразовать строку базы данных в объект сущности.

        Args:
            row: Строка, возвращённая ``SELECT *``.

        Returns:
            Экземпляр dataclass сущности.
        """

    def _fetch_all(self, sql: str, params: Sequence[Any] = ()) -> list[EntityT]:
        """Выполнить SELECT и преобразовать каждую строку в сущность.

        Args:
            sql: Параметризованный SQL-запрос.
            params: Значения для плейсхолдеров ``?``.

        Returns:
            Список сущностей (пустой, если ничего не найдено).
        """
        with self._db.connection() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._to_entity(row) for row in rows]

    def _fetch_one(self, sql: str, params: Sequence[Any] = ()) -> EntityT | None:
        """Выполнить SELECT и преобразовать первую строку в сущность.

        Args:
            sql: Параметризованный SQL-запрос.
            params: Значения для плейсхолдеров ``?``.

        Returns:
            Сущность или ``None``, если ничего не найдено.
        """
        with self._db.connection() as conn:
            row = conn.execute(sql, params).fetchone()
        return self._to_entity(row) if row else None

    def _execute(self, sql: str, params: Sequence[Any] = ()) -> sqlite3.Cursor:
        """Выполнить изменяющую данные инструкцию в отдельной транзакции.

        Args:
            sql: Параметризованные INSERT, UPDATE или DELETE.
            params: Значения для плейсхолдеров ``?``.

        Returns:
            Курсор с ``lastrowid`` и ``rowcount``.
        """
        with self._db.connection() as conn:
            return conn.execute(sql, params)

    def get_by_id(self, entity_id: int) -> EntityT | None:
        """Прочитать одну запись по первичному ключу.

        Args:
            entity_id: Значение столбца ``id``.

        Returns:
            Сущность или ``None``.
        """
        return self._fetch_one(f"SELECT * FROM {self.table} WHERE id = ?", (entity_id,))

    def get_all(self) -> list[EntityT]:
        """Прочитать все записи, упорядоченные по id.

        Returns:
            Список сущностей.
        """
        return self._fetch_all(f"SELECT * FROM {self.table} ORDER BY id")

    def count(self) -> int:
        """Подсчитать записи в таблице.

        Returns:
            Количество строк.
        """
        with self._db.connection() as conn:
            return conn.execute(f"SELECT COUNT(*) FROM {self.table}").fetchone()[0]

    def delete(self, entity_id: int) -> bool:
        """Удалить одну запись по первичному ключу.

        Args:
            entity_id: Значение столбца ``id``.

        Returns:
            ``True``, если запись удалена.
        """
        cursor = self._execute(f"DELETE FROM {self.table} WHERE id = ?", (entity_id,))
        return cursor.rowcount > 0
