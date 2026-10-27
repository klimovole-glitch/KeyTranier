"""Repository for ``tbl_keys``."""

import sqlite3

from keytrainer.data.models import Key
from keytrainer.data.repositories.base import BaseRepository


class KeyRepository(BaseRepository[Key]):
    """CRUD operations for keys of the layouts."""

    table = "tbl_keys"

    def _to_entity(self, row: sqlite3.Row) -> Key:
        """Convert a row to :class:`Key`.

        Args:
            row: Row of ``tbl_keys``.

        Returns:
            Key entity.
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
        """Add a key (``key.id`` is ignored).

        Args:
            key: Key data.

        Returns:
            Key with the id assigned by the database.
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
        """Read all keys of a layout in drawing order.

        Args:
            layout_id: Layout id.

        Returns:
            Keys sorted by row and position.
        """
        return self._fetch_all(
            "SELECT * FROM tbl_keys WHERE layout_id = ? ORDER BY row_num, pos_x",
            (layout_id,),
        )

    def get_by_char(self, layout_id: int, key_char: str) -> Key | None:
        """Find a key by the character printed on it.

        Args:
            layout_id: Layout id.
            key_char: Base (lowercase, unshifted) character.

        Returns:
            Key or ``None``.
        """
        return self._fetch_one(
            "SELECT * FROM tbl_keys WHERE layout_id = ? AND key_char = ?",
            (layout_id, key_char),
        )

    def update(self, key: Key) -> bool:
        """Change finger and position of a key.

        Args:
            key: Key with an existing id.

        Returns:
            ``True`` if the key was updated.
        """
        cursor = self._execute(
            "UPDATE tbl_keys SET finger = ?, row_num = ?, pos_x = ?, pos_y = ? "
            "WHERE id = ?",
            (key.finger, key.row_num, key.pos_x, key.pos_y, key.id),
        )
        return cursor.rowcount > 0
