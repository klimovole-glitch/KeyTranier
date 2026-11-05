from __future__ import annotations
"""Репозиторий для ``tbl_words``."""

import sqlite3

from keytrainer.data.exceptions import DuplicateNameError, ValidationError
from keytrainer.data.models import Word
from keytrainer.data.repositories.base import BaseRepository


class WordRepository(BaseRepository[Word]):
    """Операции CRUD для словаря режима «Случайные слова»."""

    table = "tbl_words"

    def _to_entity(self, row: sqlite3.Row) -> Word:
        """Преобразовать строку в :class:`Word`.

        Args:
            row: Строка ``tbl_words``.

        Returns:
            Сущность слова.
        """
        return Word(id=row["id"], layout_id=row["layout_id"], word=row["word"])

    @staticmethod
    def _normalize(word: str) -> str:
        """Обрезать пробелы и привести слово к нижнему регистру, отклоняя пустые значения.

        Args:
            word: Исходное слово.

        Returns:
            Нормализованное слово.

        Raises:
            ValidationError: Если слово пустое или содержит пробелы.
        """
        word = word.strip().lower()
        if not word or " " in word:
            raise ValidationError("Слово должно быть непустым и без пробелов")
        return word

    def create(self, layout_id: int, word: str) -> Word:
        """Добавить слово в словарь.

        Args:
            layout_id: Язык (раскладка) слова.
            word: Слово.

        Returns:
            Созданное слово.

        Raises:
            DuplicateNameError: Если слово уже есть для этой раскладки.
        """
        word = self._normalize(word)
        try:
            cursor = self._execute(
                "INSERT INTO tbl_words (layout_id, word) VALUES (?, ?)",
                (layout_id, word),
            )
        except sqlite3.IntegrityError as error:
            raise DuplicateNameError(f"Слово «{word}» уже есть") from error
        return Word(id=cursor.lastrowid, layout_id=layout_id, word=word)

    def get_words(self, layout_id: int) -> list[str]:
        """Прочитать все слова языка в виде простых строк.

        Args:
            layout_id: Идентификатор раскладки.

        Returns:
            Слова; генератор держит их в памяти для быстрой выборки.
        """
        with self._db.connection() as conn:
            rows = conn.execute(
                "SELECT word FROM tbl_words WHERE layout_id = ? ORDER BY id",
                (layout_id,),
            ).fetchall()
        return [row["word"] for row in rows]

    def count_by_layout(self, layout_id: int) -> int:
        """Подсчитать слова одного языка.

        Args:
            layout_id: Идентификатор раскладки.

        Returns:
            Количество слов.
        """
        with self._db.connection() as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM tbl_words WHERE layout_id = ?", (layout_id,)
            ).fetchone()[0]

    def update(self, word_id: int, new_word: str) -> bool:
        """Исправить написание слова.

        Args:
            word_id: Идентификатор слова.
            new_word: Новое написание.

        Returns:
            ``True``, если слово обновлено.
        """
        cursor = self._execute(
            "UPDATE tbl_words SET word = ? WHERE id = ?",
            (self._normalize(new_word), word_id),
        )
        return cursor.rowcount > 0
