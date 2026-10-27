"""Repository for ``tbl_layouts``."""

import sqlite3

from keytrainer.data.exceptions import DuplicateNameError
from keytrainer.data.models import Layout
from keytrainer.data.repositories.base import BaseRepository


class LayoutRepository(BaseRepository[Layout]):
    """CRUD operations for keyboard layouts."""

    table = "tbl_layouts"

    def _to_entity(self, row: sqlite3.Row) -> Layout:
        """Convert a row to :class:`Layout`.

        Args:
            row: Row of ``tbl_layouts``.

        Returns:
            Layout entity.
        """
        return Layout(id=row["id"], layout_name=row["layout_name"])

    def create(self, layout_name: str) -> Layout:
        """Add a layout.

        Args:
            layout_name: Unique name such as ``"RU_JCUKEN"``.

        Returns:
            Created layout.

        Raises:
            DuplicateNameError: If the name is already used.
        """
        try:
            cursor = self._execute(
                "INSERT INTO tbl_layouts (layout_name) VALUES (?)", (layout_name,)
            )
        except sqlite3.IntegrityError as error:
            raise DuplicateNameError(f"Раскладка {layout_name} уже есть") from error
        return Layout(id=cursor.lastrowid, layout_name=layout_name)

    def get_by_name(self, layout_name: str) -> Layout | None:
        """Find a layout by its name.

        Args:
            layout_name: Name such as ``"EN_QWERTY"``.

        Returns:
            Layout or ``None``.
        """
        return self._fetch_one(
            "SELECT * FROM tbl_layouts WHERE layout_name = ?", (layout_name,)
        )

    def rename(self, layout_id: int, new_name: str) -> bool:
        """Change the name of a layout.

        Args:
            layout_id: Layout id.
            new_name: New unique name.

        Returns:
            ``True`` if the layout existed and was renamed.
        """
        cursor = self._execute(
            "UPDATE tbl_layouts SET layout_name = ? WHERE id = ?", (new_name, layout_id)
        )
        return cursor.rowcount > 0
