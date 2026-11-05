"""Генератор упражнений во всех режимах (ТЗ, п. 4.2.1, 6.1)."""

import random
import time

import pytest

from keytrainer.data.keyboard_layouts import LAYOUT_EN, LAYOUT_RU, row_chars
from keytrainer.data.models import ExerciseMode
from keytrainer.data.repositories import (
    LayoutRepository,
    TextRepository,
    WordRepository,
)
from keytrainer.engine.exercise_generator import (
    ExerciseGenerator,
    ExerciseParams,
    RepositoryWordSource,
    clean_custom_text,
    weak_share,
)


@pytest.fixture
def generator(database):
    """Генератор поверх тестовой базы данных.

    Args:
        database: Инициализированная тестовая база данных.

    Returns:
        Генератор с фиксированным seed.
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
    """В упражнении ровно запрошенное количество слов."""
    params = ExerciseParams(mode=mode, layout_name=layout, word_count=25)
    exercise = generator.generate(params)
    assert len(exercise.text.split()) == 25
    assert not exercise.warnings


@pytest.mark.parametrize("layout", [LAYOUT_RU, LAYOUT_EN])
def test_weak_keys_share(generator, layout):
    """В режиме WEAK_KEYS не менее 50 % символов приходится на слабые клавиши."""
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
    """Без статистики программа объясняет это и использует случайные слова."""
    params = ExerciseParams(mode=ExerciseMode.WEAK_KEYS, word_count=10)
    exercise = generator.generate(params)
    assert exercise.warnings and len(exercise.text.split()) == 10


def test_keys_level_one_uses_home_row(generator):
    """Уровень 1 режима KEYS содержит только буквы домашнего ряда."""
    params = ExerciseParams(mode=ExerciseMode.KEYS, layout_name=LAYOUT_RU, level=1)
    text = generator.generate(params).text
    assert set(text.replace(" ", "")) <= set(row_chars(LAYOUT_RU, 2))


def test_options_capitals_digits_punctuation(generator):
    """Заглавные буквы, цифры и знаки препинания появляются, когда включены."""
    params = ExerciseParams(
        word_count=200, capitals=True, digits=True, punctuation=True
    )
    text = generator.generate(params).text
    assert any(c.isupper() for c in text)
    assert any(c.isdigit() for c in text)
    assert any(c in ",.!?:;" for c in text)


def test_invalid_length_replaced_by_default(generator):
    """Неверная длина исправляется с сообщением вместо сбоя."""
    exercise = generator.generate(ExerciseParams(word_count=5000))
    assert exercise.params.word_count == 30 and exercise.warnings


def test_timed_exercise_has_reserve(generator):
    """В упражнении на 60 секунд достаточно слов для 150 WPM."""
    exercise = generator.generate(ExerciseParams(time_limit_sec=60))
    assert len(exercise.text.split()) >= 150


def test_custom_text_cleaning():
    """Типографика упрощается, а ненабираемые символы удаляются."""
    text, removed = clean_custom_text("«Привет» —\nмир ☺", LAYOUT_RU)
    assert text == '"Привет" - мир'
    assert removed == 1


def test_custom_mode(generator):
    """Режим CUSTOM возвращает текст пользователя."""
    params = ExerciseParams(mode=ExerciseMode.CUSTOM, custom_text="Мой  текст")
    assert generator.generate(params).text == "Мой текст"


def test_generation_is_fast(generator):
    """Генерация занимает менее 0,1 с (ТЗ, п. 4.1.3)."""
    generator.generate(ExerciseParams(layout_name=LAYOUT_EN))  # прогретый кэш
    start = time.perf_counter()
    generator.generate(ExerciseParams(word_count=200, layout_name=LAYOUT_EN))
    assert time.perf_counter() - start < 0.1
