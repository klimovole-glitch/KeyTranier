"""Exercise generator in all modes (ТЗ, п. 4.2.1, 6.1)."""

import random
import time

import pytest

from keytrainer.data.keyboard_layouts import LAYOUT_EN, LAYOUT_RU, row_chars
from keytrainer.data.models import ExerciseMode
from keytrainer.engine.exercise_generator import (
    ExerciseGenerator,
    ExerciseParams,
    RepositoryWordSource,
    clean_custom_text,
    weak_share,
)
from keytrainer.data.repositories import (
    LayoutRepository,
    TextRepository,
    WordRepository,
)


@pytest.fixture
def generator(database):
    """Generator backed by the test database.

    Args:
        database: Initialized test database.

    Returns:
        Seeded generator.
    """
    source = RepositoryWordSource(
        LayoutRepository(database), WordRepository(database), TextRepository(database)
    )
    return ExerciseGenerator(source, random.Random(1))


@pytest.mark.parametrize("layout", [LAYOUT_RU, LAYOUT_EN])
@pytest.mark.parametrize(
    "mode", [ExerciseMode.KEYS, ExerciseMode.WORDS, ExerciseMode.TEXT]
)
def test_word_count_matches(generator, layout, mode):
    """The exercise has exactly the requested number of words."""
    params = ExerciseParams(mode=mode, layout_name=layout, word_count=25)
    exercise = generator.generate(params)
    assert len(exercise.text.split()) == 25
    assert not exercise.warnings


@pytest.mark.parametrize("layout", [LAYOUT_RU, LAYOUT_EN])
def test_weak_keys_share(generator, layout):
    """In WEAK_KEYS mode at least 50% of characters are weak keys."""
    home = row_chars(layout, 2)
    rates = {home[0]: 40.0, home[1]: 30.0, home[2]: 25.0}
    params = ExerciseParams(
        mode=ExerciseMode.WEAK_KEYS,
        layout_name=layout,
        word_count=50,
        weak_key_rates=rates,
    )
    text = generator.generate(params).text
    assert len(text.split()) == 50
    assert weak_share(text.split(), rates, layout) >= 0.5


def test_weak_keys_without_statistics_falls_back(generator):
    """Without statistics the program explains it and uses random words."""
    params = ExerciseParams(mode=ExerciseMode.WEAK_KEYS, word_count=10)
    exercise = generator.generate(params)
    assert exercise.warnings and len(exercise.text.split()) == 10


def test_keys_level_one_uses_home_row(generator):
    """Level 1 of KEYS mode contains only home row letters."""
    params = ExerciseParams(mode=ExerciseMode.KEYS, layout_name=LAYOUT_RU, level=1)
    text = generator.generate(params).text
    assert set(text.replace(" ", "")) <= set(row_chars(LAYOUT_RU, 2))


def test_options_capitals_digits_punctuation(generator):
    """Capitals, digits and punctuation appear when switched on."""
    params = ExerciseParams(
        word_count=200, capitals=True, digits=True, punctuation=True
    )
    text = generator.generate(params).text
    assert any(c.isupper() for c in text)
    assert any(c.isdigit() for c in text)
    assert any(c in ",.!?:;" for c in text)


def test_invalid_length_replaced_by_default(generator):
    """A wrong length is corrected with a message instead of a crash."""
    exercise = generator.generate(ExerciseParams(word_count=5000))
    assert exercise.params.word_count == 30 and exercise.warnings


def test_timed_exercise_has_reserve(generator):
    """A 60-second exercise has enough words for 150 WPM."""
    exercise = generator.generate(ExerciseParams(time_limit_sec=60))
    assert len(exercise.text.split()) >= 150


def test_custom_text_cleaning():
    """Typography is simplified and untypeable characters are removed."""
    text, removed = clean_custom_text("«Привет» —\nмир ☺", LAYOUT_RU)
    assert text == '"Привет" - мир'
    assert removed == 1


def test_custom_mode(generator):
    """CUSTOM mode returns the user's text."""
    params = ExerciseParams(mode=ExerciseMode.CUSTOM, custom_text="Мой  текст")
    assert generator.generate(params).text == "Мой текст"


def test_generation_is_fast(generator):
    """Generation takes less than 0.1 s (ТЗ, п. 4.1.3)."""
    generator.generate(ExerciseParams(layout_name=LAYOUT_EN))  # warm cache
    start = time.perf_counter()
    generator.generate(ExerciseParams(word_count=200, layout_name=LAYOUT_EN))
    assert time.perf_counter() - start < 0.1
