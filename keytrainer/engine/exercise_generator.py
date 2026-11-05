from __future__ import annotations
"""Генератор упражнений: пять режимов ТЗ, п. 4.2.1 и адаптивные веса 4.3.1.

Генератор ничего не знает о SQLite: слова и тексты приходят через протокол
:class:`WordSource`. В программе его реализуют репозитории
(:class:`RepositoryWordSource`), в тестах — обычный список.
"""

import argparse
import logging
import math
import random
import re
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from typing import Protocol

from keytrainer.data.keyboard_layouts import (
    LAYOUT_RU,
    base_key_char,
    is_typeable,
    row_chars,
)
from keytrainer.data.models import ExerciseMode

logger = logging.getLogger(__name__)

MIN_WORDS, MAX_WORDS, DEFAULT_WORDS = 10, 200, 30
TIME_LIMITS = (30, 60, 120)
MAX_LEVEL = 5
# Слов, генерируемых для упражнения на время: достаточно для 150 WPM.
WORDS_PER_MINUTE_RESERVE = 150
WEAK_BASE_WEIGHT = 1.0  # w_0
WEAK_ERROR_FACTOR = 0.5  # k
WEAK_MIN_SHARE = 0.5  # ТЗ, п. 6.1: не менее 50 % символов на слабых клавишах
PUNCTUATION_MARKS = (",", ".", "!", "?", ":", ";")
_TYPOGRAPHY = str.maketrans(
    {
        "«": '"',
        "»": '"',
        "“": '"',
        "”": '"',
        "„": '"',
        "—": "-",
        "–": "-",
        "’": "'",
        "…": "...",
    }
)


class WordSource(Protocol):
    """Откуда генератор берёт слова словаря и тексты."""

    def get_words(self, layout_name: str) -> list[str]:
        """Вернуть слова словаря раскладки."""

    def get_random_text(
        self, layout_name: str, exclude_title: str | None = None
    ) -> tuple[str, str] | None:
        """Вернуть ``(заголовок, содержимое)`` случайного встроенного текста или ``None``."""


@dataclass(frozen=True)
class ExerciseParams:
    """Параметры, выбранные на вкладке тренировки."""

    mode: ExerciseMode = ExerciseMode.WORDS
    layout_name: str = LAYOUT_RU
    word_count: int = DEFAULT_WORDS
    time_limit_sec: int | None = None
    capitals: bool = False
    digits: bool = False
    punctuation: bool = False
    level: int = 1
    custom_text: str = ""
    weak_key_rates: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class Exercise:
    """Сгенерированное упражнение."""

    text: str
    params: ExerciseParams
    warnings: tuple[str, ...] = ()
    source: str = ""  # автор и название связного текста


def normalize_params(params: ExerciseParams) -> tuple[ExerciseParams, list[str]]:
    """Заменить недопустимые параметры значениями по умолчанию (ТЗ, п. 4.1.4).

    Args:
        params: Параметры из интерфейса.

    Returns:
        Исправленные параметры и сообщения о том, что было исправлено.
    """
    warnings = []
    if not MIN_WORDS <= params.word_count <= MAX_WORDS:
        warnings.append(
            f"Длина {params.word_count} слов вне диапазона {MIN_WORDS}–{MAX_WORDS}, "
            f"установлено {DEFAULT_WORDS}"
        )
        params = replace(params, word_count=DEFAULT_WORDS)
    if params.time_limit_sec is not None and params.time_limit_sec not in TIME_LIMITS:
        warnings.append("Неверное ограничение времени, установлено 60 с")
        params = replace(params, time_limit_sec=60)
    if not 1 <= params.level <= MAX_LEVEL:
        params = replace(params, level=1)
    return params, warnings


def clean_custom_text(text: str, layout_name: str) -> tuple[str, int]:
    """Подготовить пользовательский текст для набора.

    Типографские кавычки и тире заменяются обычными, переводы строк —
    пробелами, символы, которые нельзя набрать на раскладке, удаляются.

    Args:
        text: Исходный пользовательский текст.
        layout_name: Раскладка упражнения.

    Returns:
        Очищенный текст и количество удалённых символов.
    """
    text = " ".join(text.translate(_TYPOGRAPHY).split())
    kept = [char for char in text if is_typeable(char, layout_name)]
    cleaned = re.sub(" +", " ", "".join(kept)).strip()
    return cleaned, len(text) - len(kept)


def sentence_starts(words: list[str]) -> list[int]:
    """Индексы слов, с которых начинаются предложения.

    Предложение начинается с первого слова и после слова, заканчивающегося на
    ".", "!" или "?" (после них допускаются закрывающие кавычки и скобки).

    Args:
        words: Слова текста.

    Returns:
        Индексы первых слов предложений (как минимум ``[0]``).
    """
    starts = [0]
    for index, word in enumerate(words[:-1]):
        if word.rstrip("\"')").endswith((".", "!", "?")):
            starts.append(index + 1)
    return starts


class ExerciseGenerator:
    """Строит тексты упражнений для всех пяти режимов."""

    def __init__(self, source: WordSource, rng: random.Random | None = None) -> None:
        """Создать генератор.

        Args:
            source: Поставщик слов и текстов.
            rng: Генератор случайных чисел (в тестах — с фиксированным seed).
        """
        self._source = source
        self._rng = rng or random.Random()
        self._last_title: str | None = None  # не выдавать один текст дважды подряд
        self._last_source = ""

    def generate(self, params: ExerciseParams) -> Exercise:
        """Сгенерировать упражнение.

        Args:
            params: Параметры упражнения.

        Returns:
            Текст упражнения с предупреждениями об исправленных параметрах.
        """
        params, warnings = normalize_params(params)
        self._last_source = ""
        builders = {
            ExerciseMode.KEYS: self._keys_text,
            ExerciseMode.WORDS: self._words_text,
            ExerciseMode.TEXT: self._connected_text,
            ExerciseMode.WEAK_KEYS: self._weak_keys_text,
            ExerciseMode.CUSTOM: self._custom_text,
        }
        text = builders[ExerciseMode(params.mode)](params, warnings)
        if not text:
            warnings.append("Не удалось составить упражнение, выбраны случайные слова")
            text = self._words_text(replace(params, mode=ExerciseMode.WORDS), [])
        for message in warnings:
            logger.warning(message)
        source = self._last_source if params.mode == ExerciseMode.TEXT else ""
        return Exercise(
            text=text, params=params, warnings=tuple(warnings), source=source
        )

    # ---------------------------------------------------------- помощники
    def _target_words(self, params: ExerciseParams) -> int:
        """Количество генерируемых слов (больше для упражнения на время).

        Args:
            params: Нормализованные параметры.

        Returns:
            Количество слов.
        """
        if params.time_limit_sec:
            minutes = params.time_limit_sec / 60
            return math.ceil(WORDS_PER_MINUTE_RESERVE * minutes)
        return params.word_count

    def _decorate(self, words: list[str], params: ExerciseParams) -> str:
        """Добавить заглавные буквы, цифры и знаки препинания, если они включены.

        Args:
            words: Слова в нижнем регистре.
            params: Параметры с флагами.

        Returns:
            Итоговый текст.
        """
        result = []
        capitalize_next = params.capitals
        for word in words:
            if params.digits and self._rng.random() < 0.15:
                word = str(self._rng.randint(1, 2026))
            elif capitalize_next or (params.capitals and self._rng.random() < 0.1):
                word = word[:1].upper() + word[1:]
            capitalize_next = False
            if params.punctuation and self._rng.random() < 0.2:
                mark = self._rng.choice(PUNCTUATION_MARKS)
                word += mark
                capitalize_next = params.capitals and mark in ".!?"
            result.append(word)
        return " ".join(result)

    # ------------------------------------------------------------ режимы
    def _keys_text(self, params: ExerciseParams, warnings: list[str]) -> str:
        """Режим KEYS: изучение раскладки по рядам.

        Уровень 1 — домашний ряд, 2 — плюс верхний, 3 — плюс нижний, 4 — плюс
        цифры, 5 — плюс знаки препинания. Буквы самого нового ряда встречаются
        вдвое чаще.

        Args:
            params: Нормализованные параметры.
            warnings: Список для сообщений.

        Returns:
            Текст из псевдослов, составленных из символов уровня.
        """
        rows_by_level = (2, 1, 3, 0)
        rows = rows_by_level[: min(params.level, 4)]
        alphabet, weights = [], []
        for row in rows:
            chars = [c for c in row_chars(params.layout_name, row) if c.isalnum()]
            alphabet += chars
            weights += [2.0 if row == rows[-1] else 1.0] * len(chars)
        words = []
        for _ in range(self._target_words(params)):
            length = self._rng.randint(2, 5)
            words.append("".join(self._rng.choices(alphabet, weights, k=length)))
        decorated = replace(params, punctuation=params.level >= MAX_LEVEL)
        return self._decorate(words, decorated)

    def _words_text(self, params: ExerciseParams, warnings: list[str]) -> str:
        """Режим WORDS: случайные слова из словаря.

        Args:
            params: Нормализованные параметры.
            warnings: Список для сообщений.

        Returns:
            Текст из случайных слов.
        """
        dictionary = self._source.get_words(params.layout_name)
        if not dictionary:
            warnings.append("Словарь пуст")
            return ""
        count = self._target_words(params)
        words = [self._rng.choice(dictionary) for _ in range(count)]
        return self._decorate(words, params)

    def _connected_text(self, params: ExerciseParams, warnings: list[str]) -> str:
        """Режим TEXT: фрагмент встроенного текста (в основном классическая литература).

        Фрагмент начинается со случайного предложения, поэтому даже один текст
        даёт разные упражнения; предыдущий текст не повторяется.

        Args:
            params: Нормализованные параметры.
            warnings: Список для сообщений.

        Returns:
            Текст, обрезанный до запрошенного количества слов (продолжается
            с начала, если остаток текста короткий).
        """
        found = self._source.get_random_text(params.layout_name, self._last_title)
        if not found:
            warnings.append("Библиотека текстов пуста")
            return ""
        title, text = found
        self._last_title = title
        self._last_source = title
        words = text.split()
        starts = sentence_starts(words)
        start = self._rng.choice(starts)
        ordered = words[start:] + words[:start]
        count = self._target_words(params)
        while len(ordered) < count:
            ordered += words
        return " ".join(ordered[:count])

    def _custom_text(self, params: ExerciseParams, warnings: list[str]) -> str:
        """Режим CUSTOM: собственный текст пользователя.

        Args:
            params: Параметры с ``custom_text``.
            warnings: Список для сообщений.

        Returns:
            Очищенный пользовательский текст.
        """
        text, removed = clean_custom_text(params.custom_text, params.layout_name)
        if removed:
            warnings.append(f"Удалено символов, которых нет на раскладке: {removed}")
        if not text:
            warnings.append("Свой текст пуст")
        return text

    def _weak_keys_text(self, params: ExerciseParams, warnings: list[str]) -> str:
        """Режим WEAK_KEYS: адаптивное упражнение на проблемных клавишах.

        Каждый символ получает вес ``w_i = w_0 + k * e_i`` (ТЗ, п. 4.3.1).
        Слова выбираются через ``random.choices`` по сумме весов их букв; если
        слабых символов в тексте всё ещё меньше 50 %, подмешиваются слова,
        состоящие только из слабых символов.

        Args:
            params: Параметры с ``weak_key_rates`` (символ -> доля ошибок в %).
            warnings: Список для сообщений.

        Returns:
            Адаптивный текст.
        """
        rates = {c: r for c, r in params.weak_key_rates.items() if r > 0 and c.strip()}
        dictionary = self._source.get_words(params.layout_name)
        if not rates or not dictionary:
            warnings.append("Недостаточно статистики, выбраны случайные слова")
            return self._words_text(params, warnings)

        def weight(word: str) -> float:
            return sum(
                WEAK_BASE_WEIGHT + WEAK_ERROR_FACTOR * rates.get(c, 0.0) for c in word
            ) / len(word)

        count = self._target_words(params)
        words = self._rng.choices(dictionary, [weight(w) for w in dictionary], k=count)
        weak_chars = list(rates)
        weak_weights = [
            WEAK_BASE_WEIGHT + WEAK_ERROR_FACTOR * rates[c] for c in weak_chars
        ]
        index = 0
        while weak_share(words, rates, params.layout_name) < WEAK_MIN_SHARE:
            length = self._rng.randint(3, 5)
            words[index % count] = "".join(
                self._rng.choices(weak_chars, weak_weights, k=length)
            )
            index += 1
        self._rng.shuffle(words)
        return " ".join(words)


def weak_share(
    words: Sequence[str], rates: dict[str, float], layout_name: str
) -> float:
    """Доля символов, приходящихся на слабые клавиши (пробелы не учитываются).

    Args:
        words: Слова упражнения.
        rates: Слабые клавиши (базовые символы).
        layout_name: Раскладка упражнения.

    Returns:
        Значение от 0 до 1.
    """
    chars = [c for word in words for c in word]
    if not chars:
        return 0.0
    weak = sum(base_key_char(c, layout_name) in rates for c in chars)
    return weak / len(chars)


class RepositoryWordSource:
    """:class:`WordSource` на основе базы данных (слова кэшируются в памяти)."""

    def __init__(self, layouts, words, texts) -> None:
        """Сохранить репозитории.

        Args:
            layouts: ``LayoutRepository``.
            words: ``WordRepository``.
            texts: ``TextRepository``.
        """
        self._layouts = layouts
        self._words = words
        self._texts = texts
        self._cache: dict[str, list[str]] = {}

    def _layout_id(self, layout_name: str) -> int | None:
        """Найти идентификатор раскладки.

        Args:
            layout_name: Имя раскладки.

        Returns:
            Идентификатор или ``None``.
        """
        layout = self._layouts.get_by_name(layout_name)
        return layout.id if layout else None

    def get_words(self, layout_name: str) -> list[str]:
        """Вернуть слова словаря раскладки (читаются один раз, затем кэшируются).

        Args:
            layout_name: Имя раскладки.

        Returns:
            Слова.
        """
        if layout_name not in self._cache:
            layout_id = self._layout_id(layout_name)
            self._cache[layout_name] = (
                self._words.get_words(layout_id) if layout_id else []
            )
        return self._cache[layout_name]

    def get_random_text(
        self, layout_name: str, exclude_title: str | None = None
    ) -> tuple[str, str] | None:
        """Вернуть случайный встроенный текст раскладки.

        Args:
            layout_name: Имя раскладки.
            exclude_title: Заголовок предыдущего текста (не повторяется).

        Returns:
            ``(заголовок, содержимое)`` или ``None``.
        """
        layout_id = self._layout_id(layout_name)
        text = self._texts.get_random(layout_id, exclude_title) if layout_id else None
        return (text.title, text.content) if text else None


def main() -> None:
    """Вывести сгенерированное упражнение в консоль для ручной проверки."""
    from keytrainer.config import DB_PATH
    from keytrainer.data.database import Database
    from keytrainer.data.repositories import (
        LayoutRepository,
        TextRepository,
        WordRepository,
    )

    parser = argparse.ArgumentParser(description="Генерация упражнения")
    parser.add_argument(
        "--mode", default="WORDS", choices=[m.value for m in ExerciseMode]
    )
    parser.add_argument("--layout", default=LAYOUT_RU)
    parser.add_argument("--words", type=int, default=DEFAULT_WORDS)
    parser.add_argument("--level", type=int, default=1)
    parser.add_argument("--capitals", action="store_true")
    parser.add_argument("--digits", action="store_true")
    parser.add_argument("--punctuation", action="store_true")
    args = parser.parse_args()

    database = Database(DB_PATH)
    database.initialize()
    source = RepositoryWordSource(
        LayoutRepository(database), WordRepository(database), TextRepository(database)
    )
    params = ExerciseParams(
        mode=ExerciseMode(args.mode),
        layout_name=args.layout,
        word_count=args.words,
        level=args.level,
        capitals=args.capitals,
        digits=args.digits,
        punctuation=args.punctuation,
    )
    print(ExerciseGenerator(source).generate(params).text)


if __name__ == "__main__":
    main()
