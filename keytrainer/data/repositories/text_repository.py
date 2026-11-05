from __future__ import annotations
"""Репозиторий для ``tbl_texts``."""

import sqlite3

from keytrainer.data.exceptions import ValidationError
from keytrainer.data.models import Text
from keytrainer.data.repositories.base import BaseRepository

MAX_TEXT_LENGTH = 10_000


class TextRepository(BaseRepository[Text]):
    """Операции CRUD для встроенных и пользовательских текстов."""

    table = "tbl_texts"

    def _to_entity(self, row: sqlite3.Row) -> Text:
        """Преобразовать строку в :class:`Text`.

        Args:
            row: Строка ``tbl_texts``.

        Returns:
            Сущность текста.
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
        """Проверить заголовок и содержимое текста.

        Args:
            title: Заголовок текста.
            content: Тело текста.

        Returns:
            Заголовок и содержимое без лишних пробелов; пробельные символы
            сворачиваются в одиночные пробелы.

        Raises:
            ValidationError: Если поле пустое или текст слишком длинный.
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
        """Добавить текст (по умолчанию — пользовательский для режима «Свой текст»).

        Args:
            layout_id: Язык текста.
            title: Заголовок.
            content: Тело текста.
            is_custom: ``True`` для текстов, добавленных пользователем.

        Returns:
            Созданный текст.
        """
        title, content = self._validate(title, content)
        cursor = self._execute(
            "INSERT INTO tbl_texts (layout_id, title, content, is_custom) "
            "VALUES (?, ?, ?, ?)",
            (layout_id, title, content, int(is_custom)),
        )
        return Text(cursor.lastrowid, layout_id, title, content, is_custom)

    def get_by_layout(self, layout_id: int, custom: bool | None = None) -> list[Text]:
        """Прочитать тексты одного языка.

        Args:
            layout_id: Идентификатор раскладки.
            custom: ``True`` — только пользовательские тексты, ``False`` — только
                встроенные, ``None`` — все тексты.

        Returns:
            Список текстов.
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

    def get_random(
        self, layout_id: int, exclude_title: str | None = None
    ) -> Text | None:
        """Выбрать случайный встроенный текст для режима «Связный текст».

        Args:
            layout_id: Идентификатор раскладки.
            exclude_title: Заголовок предыдущего текста, чтобы один и тот же текст
                не выдавался дважды подряд (игнорируется, если он единственный).

        Returns:
            Случайный текст или ``None``, если библиотека пуста.
        """
        text = self._fetch_one(
            "SELECT * FROM tbl_texts WHERE layout_id = ? AND is_custom = 0 "
            "AND title != ? ORDER BY RANDOM() LIMIT 1",
            (layout_id, exclude_title or ""),
        )
        if text is None and exclude_title:
            return self.get_random(layout_id)
        return text

    def update(self, text: Text) -> bool:
        """Изменить заголовок и содержимое текста.

        Args:
            text: Текст с существующим id.

        Returns:
            ``True``, если текст обновлён.
        """
        title, content = self._validate(text.title, text.content)
        cursor = self._execute(
            "UPDATE tbl_texts SET title = ?, content = ? WHERE id = ?",
            (title, content, text.id),
        )
        return cursor.rowcount > 0
