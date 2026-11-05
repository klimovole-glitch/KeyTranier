from __future__ import annotations
"""Репозиторий для ``tbl_keys``."""

import sqlite3

from keytrainer.data.models import Key
from keytrainer.data.repositories.base import BaseRepository


class KeyRepository(BaseRepository[Key]):
    """Операции CRUD для клавиш раскладок."""

    table = "tbl_keys"

    def _to_entity(self, row: sqlite3.Row) -> Key:
        """Преобразовать строку в :class:`Key`.

        Args:
            row: Строка ``tbl_keys``.

        Returns:
            Сущность клавиши.
        """
        return Key(
            id=row["id"],
            layout_id=row["layout_id"],
            key_char=row["key_char"],
            row_num=row["row_num"],
            finger=row["finger"],
            pos_x=row["pos_x"],
            pos_y=row["pos_y"],
        )

    def create(self, key: Key) -> Key:
        """Добавить клавишу (``key.id`` игнорируется).

        Args:
            key: Данные клавиши.

        Returns:
            Клавиша с идентификатором, присвоенным базой данных.
        """
        cursor = self._execute(
            "INSERT INTO tbl_keys (layout_id, key_char, row_num, finger, pos_x, pos_y) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                key.layout_id,
                key.key_char,
                key.row_num,
                key.finger,
                key.pos_x,
                key.pos_y,
            ),
        )
        return Key(
            cursor.lastrowid,
            key.layout_id,
            key.key_char,
            key.row_num,
            key.finger,
            key.pos_x,
            key.pos_y,
        )

    def get_by_layout(self, layout_id: int) -> list[Key]:
        """Прочитать все клавиши раскладки в порядке отрисовки.

        Args:
            layout_id: Идентификатор раскладки.

        Returns:
            Клавиши, отсортированные по ряду и позиции.
        """
        return self._fetch_all(
            "SELECT * FROM tbl_keys WHERE layout_id = ? ORDER BY row_num, pos_x",
            (layout_id,),
        )

    def get_by_char(self, layout_id: int, key_char: str) -> Key | None:
        """Найти клавишу по напечатанному на ней символу.

        Args:
            layout_id: Идентификатор раскладки.
            key_char: Базовый (строчный, без Shift) символ.

        Returns:
            Клавиша или ``None``.
        """
        return self._fetch_one(
            "SELECT * FROM tbl_keys WHERE layout_id = ? AND key_char = ?",
            (layout_id, key_char),
        )

    def update(self, key: Key) -> bool:
        """Изменить палец и позицию клавиши.

        Args:
            key: Клавиша с существующим id.

        Returns:
            ``True``, если клавиша обновлена.
        """
        cursor = self._execute(
            "UPDATE tbl_keys SET finger = ?, row_num = ?, pos_x = ?, pos_y = ? "
            "WHERE id = ?",
            (key.finger, key.row_num, key.pos_x, key.pos_y, key.id),
        )
        return cursor.rowcount > 0
