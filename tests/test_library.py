"""Built-in library: classic texts, dictionaries and the connected text mode."""

import random

import pytest

from keytrainer.config import RESOURCES_DIR
from keytrainer.data.keyboard_layouts import LAYOUT_EN, LAYOUT_RU, is_typeable
from keytrainer.data.models import ExerciseMode
from keytrainer.data.repositories import (
    LayoutRepository,
    TextRepository,
    WordRepository,
)
from keytrainer.data.seed import load_words, parse_texts
from keytrainer.engine.exercise_generator import (
    ExerciseGenerator,
    ExerciseParams,
    RepositoryWordSource,
    sentence_starts,
)
from keytrainer.views.screens.training_screen import format_source

LANGS = {LAYOUT_RU: "ru", LAYOUT_EN: "en"}


@pytest.mark.parametrize("layout", [LAYOUT_RU, LAYOUT_EN])
def test_every_text_can_be_typed(layout):
    """No built-in text needs a character that is missing on its keyboard."""
    texts = parse_texts(RESOURCES_DIR / f"texts_{LANGS[layout]}.txt")
    assert len(texts) >= 20
    for title, content in texts:
        missing = {c for c in content if not is_typeable(c, layout)}
        assert not missing, f"{title}: {missing}"


@pytest.mark.parametrize("layout", [LAYOUT_RU, LAYOUT_EN])
def test_dictionaries_are_large_and_typeable(layout):
    """Dictionaries have well over 1000 words of the right alphabet."""
    words = load_words(RESOURCES_DIR / f"words_{LANGS[layout]}.txt")
    assert len(words) >= 1300
    assert all(is_typeable(c, layout) for word in words for c in word)


def test_sync_adds_texts_to_an_old_database(database):
    """A database created by an older version gets new texts on start."""
    with database.connection() as conn:
        conn.execute("DELETE FROM tbl_texts WHERE title LIKE '%Толстой%'")
        conn.execute(
            "INSERT INTO tbl_texts (layout_id, title, content, is_custom) "
            "VALUES (1, 'мой текст', 'свой текст пользователя', 1)"
        )
    database.initialize()
    with database.connection() as conn:
        tolstoy = conn.execute(
            "SELECT COUNT(*) FROM tbl_texts WHERE title LIKE '%Толстой%'"
        ).fetchone()[0]
        custom = conn.execute(
            "SELECT COUNT(*) FROM tbl_texts WHERE is_custom = 1"
        ).fetchone()[0]
    assert tolstoy == 3
    assert custom == 1


def test_sentence_starts():
    """Sentences start after ".", "!" and "?", also before closing quotes."""
    words = 'Он пришел. "Кто там?" спросила она! А дальше'.split()
    assert sentence_starts(words) == [0, 2, 4, 6]


def test_connected_text_variety(database):
    """Texts are not repeated in a row and fragments start with a sentence."""
    source = RepositoryWordSource(
        LayoutRepository(database), WordRepository(database), TextRepository(database)
    )
    generator = ExerciseGenerator(source, random.Random(3))
    params = ExerciseParams(mode=ExerciseMode.TEXT, layout_name=LAYOUT_RU)
    sources = [generator.generate(params).source for _ in range(12)]
    assert all(sources)
    assert all(a != b for a, b in zip(sources, sources[1:], strict=False))
    assert len(set(sources)) >= 6
    text = generator.generate(params).text
    assert text[0].isupper() or text[0] in '-"'


def test_format_source():
    """Library titles become captions under the text."""
    assert format_source("Л. Н. Толстой - Война и мир") == (
        "— Л. Н. Толстой, «Война и мир»"
    )
    assert format_source("Река") == "«Река»"
    assert format_source("") == ""
