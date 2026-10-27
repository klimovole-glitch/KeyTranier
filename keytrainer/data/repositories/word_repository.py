"""Repository for ``tbl_words``."""

import sqlite3

from keytrainer.data.exceptions import DuplicateNameError, ValidationError
from keytrainer.data.models import Word
from keytrainer.data.repositories.base import BaseRepository


class WordRepository(BaseRepository[Word]):
    """CRUD operations for the dictionary of the "Random words" mode."""

    table = "tbl_words"

    def _to_entity(self, row: sqlite3.Row) -> Word:
        """Convert a row to :class:`Word`.

        Args:
            row: Row of ``tbl_words``.

        Returns:
            Word entity.
        """
        return Word(id=row["id"], layout_id=row["layout_id"], word=row["word"])

    @staticmethod
    def _normalize(word: str) -> str:
        """Strip and lowercase a word, rejecting empty values.

        Args:
            word: Raw word.

        Returns:
            Normalized word.

        Raises:
            ValidationError: If the word is empty or contains spaces.
        """
        word = word.strip().lower()
        if not word or " " in word:
            raise ValidationError("Слово должно быть непустым и без пробелов")
        return word

    def create(self, layout_id: int, word: str) -> Word:
        """Add a word to the dictionary.

        Args:
            layout_id: Language (layout) of the word.
            word: The word.

        Returns:
            Created word.

        Raises:
            DuplicateNameError: If the word already exists for this layout.
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
        """Read all words of a language as plain strings.

        Args:
            layout_id: Layout id.

        Returns:
            Words; the generator keeps them in memory for fast sampling.
        """
        with self._db.connection() as conn:
            rows = conn.execute(
                "SELECT word FROM tbl_words WHERE layout_id = ? ORDER BY id",
                (layout_id,),
            ).fetchall()
        return [row["word"] for row in rows]

    def count_by_layout(self, layout_id: int) -> int:
        """Count words of one language.

        Args:
            layout_id: Layout id.

        Returns:
            Number of words.
        """
        with self._db.connection() as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM tbl_words WHERE layout_id = ?", (layout_id,)
            ).fetchone()[0]

    def update(self, word_id: int, new_word: str) -> bool:
        """Correct the spelling of a word.

        Args:
            word_id: Word id.
            new_word: New spelling.

        Returns:
            ``True`` if the word was updated.
        """
        cursor = self._execute(
            "UPDATE tbl_words SET word = ? WHERE id = ?",
            (self._normalize(new_word), word_id),
        )
        return cursor.rowcount > 0
