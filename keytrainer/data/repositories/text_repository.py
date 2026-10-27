"""Repository for ``tbl_texts``."""

import sqlite3

from keytrainer.data.exceptions import ValidationError
from keytrainer.data.models import Text
from keytrainer.data.repositories.base import BaseRepository

MAX_TEXT_LENGTH = 10_000


class TextRepository(BaseRepository[Text]):
    """CRUD operations for built-in and user texts."""

    table = "tbl_texts"

    def _to_entity(self, row: sqlite3.Row) -> Text:
        """Convert a row to :class:`Text`.

        Args:
            row: Row of ``tbl_texts``.

        Returns:
            Text entity.
        """
        return Text(
            id=row["id"],
            layout_id=row["layout_id"],
            title=row["title"],
            content=row["content"],
            is_custom=bool(row["is_custom"]),
        )

    @staticmethod
    def _validate(title: str, content: str) -> tuple[str, str]:
        """Check title and content of a text.

        Args:
            title: Text title.
            content: Text body.

        Returns:
            Stripped title and content; whitespace is collapsed to single spaces.

        Raises:
            ValidationError: If a field is empty or the text is too long.
        """
        title = title.strip()
        content = " ".join(content.split())
        if not title or not content:
            raise ValidationError("Название и текст не могут быть пустыми")
        if len(content) > MAX_TEXT_LENGTH:
            raise ValidationError(
                f"Текст длиннее {MAX_TEXT_LENGTH} символов, сократите его"
            )
        return title, content

    def create(
        self, layout_id: int, title: str, content: str, is_custom: bool = True
    ) -> Text:
        """Add a text (by default — a user text for the "Own text" mode).

        Args:
            layout_id: Language of the text.
            title: Title.
            content: Text body.
            is_custom: ``True`` for texts added by the user.

        Returns:
            Created text.
        """
        title, content = self._validate(title, content)
        cursor = self._execute(
            "INSERT INTO tbl_texts (layout_id, title, content, is_custom) "
            "VALUES (?, ?, ?, ?)",
            (layout_id, title, content, int(is_custom)),
        )
        return Text(cursor.lastrowid, layout_id, title, content, is_custom)

    def get_by_layout(self, layout_id: int, custom: bool | None = None) -> list[Text]:
        """Read texts of one language.

        Args:
            layout_id: Layout id.
            custom: ``True`` — only user texts, ``False`` — only built-in,
                ``None`` — all texts.

        Returns:
            List of texts.
        """
        if custom is None:
            return self._fetch_all(
                "SELECT * FROM tbl_texts WHERE layout_id = ? ORDER BY id", (layout_id,)
            )
        return self._fetch_all(
            "SELECT * FROM tbl_texts WHERE layout_id = ? AND is_custom = ? "
            "ORDER BY id",
            (layout_id, int(custom)),
        )

    def get_random(self, layout_id: int) -> Text | None:
        """Pick a random built-in text for the "Connected text" mode.

        Args:
            layout_id: Layout id.

        Returns:
            Random text or ``None`` if the library is empty.
        """
        return self._fetch_one(
            "SELECT * FROM tbl_texts WHERE layout_id = ? AND is_custom = 0 "
            "ORDER BY RANDOM() LIMIT 1",
            (layout_id,),
        )

    def update(self, text: Text) -> bool:
        """Change title and content of a text.

        Args:
            text: Text with an existing id.

        Returns:
            ``True`` if the text was updated.
        """
        title, content = self._validate(text.title, text.content)
        cursor = self._execute(
            "UPDATE tbl_texts SET title = ?, content = ? WHERE id = ?",
            (title, content, text.id),
        )
        return cursor.rowcount > 0
