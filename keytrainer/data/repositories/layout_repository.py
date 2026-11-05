from __future__ import annotations
"""Репозиторий для ``tbl_layouts``."""

import sqlite3

from keytrainer.data.exceptions import DuplicateNameError
from keytrainer.data.models import Layout
from keytrainer.data.repositories.base import BaseRepository


class LayoutRepository(BaseRepository[Layout]):
    """Операции CRUD для раскладок клавиатуры."""

    table = "tbl_layouts"

    def _to_entity(self, row: sqlite3.Row) -> Layout:
        """Преобразовать строку в :class:`Layout`.

        Args:
            row: Строка ``tbl_layouts``.

        Returns:
            Сущность раскладки.
        """
        return Layout(id=row["id"], layout_name=row["layout_name"])

    def create(self, layout_name: str) -> Layout:
        """Добавить раскладку.

        Args:
            layout_name: Уникальное имя, например ``"RU_JCUKEN"``.

        Returns:
            Созданная раскладка.

        Raises:
            DuplicateNameError: Если имя уже используется.
        """
        try:
            cursor = self._execute(
                "INSERT INTO tbl_layouts (layout_name) VALUES (?)", (layout_name,)
            )
        except sqlite3.IntegrityError as error:
            raise DuplicateNameError(f"Раскладка {layout_name} уже есть") from error
        return Layout(id=cursor.lastrowid, layout_name=layout_name)

    def get_by_name(self, layout_name: str) -> Layout | None:
        """Найти раскладку по имени.

        Args:
            layout_name: Имя, например ``"EN_QWERTY"``.

        Returns:
            Раскладка или ``None``.
        """
        return self._fetch_one(
            "SELECT * FROM tbl_layouts WHERE layout_name = ?", (layout_name,)
        )

    def rename(self, layout_id: int, new_name: str) -> bool:
        """Изменить имя раскладки.

        Args:
            layout_id: Идентификатор раскладки.
            new_name: Новое уникальное имя.

        Returns:
            ``True``, если раскладка существовала и была переименована.
        """
        cursor = self._execute(
            "UPDATE tbl_layouts SET layout_name = ? WHERE id = ?", (new_name, layout_id)
        )
        return cursor.rowcount > 0
