"""Exercise generator: five modes of ТЗ, п. 4.2.1 and adaptive weights 4.3.1.

The generator does not know about SQLite: words and texts come through the
:class:`WordSource` protocol. In the program it is backed by repositories
(:class:`RepositoryWordSource`), in tests — by a plain list.
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
# Words generated for a timed exercise: enough for 150 WPM.
WORDS_PER_MINUTE_RESERVE = 150
WEAK_BASE_WEIGHT = 1.0  # w_0
WEAK_ERROR_FACTOR = 0.5  # k
WEAK_MIN_SHARE = 0.5  # ТЗ, п. 6.1: at least 50% of characters on weak keys
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
    """Where the generator takes dictionary words and texts from."""

    def get_words(self, layout_name: str) -> list[str]:
        """Return dictionary words of a layout."""

    def get_random_text(
        self, layout_name: str, exclude_title: str | None = None
    ) -> tuple[str, str] | None:
        """Return ``(title, content)`` of a random built-in text or ``None``."""


@dataclass(frozen=True)
class ExerciseParams:
    """Parameters chosen on the training tab."""

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
    """Generated exercise."""

    text: str
    params: ExerciseParams
    warnings: tuple[str, ...] = ()
    source: str = ""  # author and title of a connected text


def normalize_params(params: ExerciseParams) -> tuple[ExerciseParams, list[str]]:
    """Replace invalid parameters by defaults (ТЗ, п. 4.1.4).

    Args:
        params: Parameters from the interface.

    Returns:
        Corrected parameters and messages about what was corrected.
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
    """Prepare a user text for typing.

    Typographic quotes and dashes become plain ones, line breaks become
    spaces, characters that cannot be typed on the layout are removed.

    Args:
        text: Raw user text.
        layout_name: Layout of the exercise.

    Returns:
        Clean text and the number of removed characters.
    """
    text = " ".join(text.translate(_TYPOGRAPHY).split())
    kept = [char for char in text if is_typeable(char, layout_name)]
    cleaned = re.sub(" +", " ", "".join(kept)).strip()
    return cleaned, len(text) - len(kept)


def sentence_starts(words: list[str]) -> list[int]:
    """Indexes of words that begin a sentence.

    A sentence begins with the first word and after a word that ends with
    ".", "!" or "?" (closing quotes and brackets are allowed after them).

    Args:
        words: Words of a text.

    Returns:
        Indexes of first words of sentences (at least ``[0]``).
    """
    starts = [0]
    for index, word in enumerate(words[:-1]):
        if word.rstrip("\"')").endswith((".", "!", "?")):
            starts.append(index + 1)
    return starts


class ExerciseGenerator:
    """Builds exercise texts for all five modes."""

    def __init__(self, source: WordSource, rng: random.Random | None = None) -> None:
        """Create a generator.

        Args:
            source: Provider of words and texts.
            rng: Random generator (a seeded one in tests).
        """
        self._source = source
        self._rng = rng or random.Random()
        self._last_title: str | None = None  # do not give one text twice in a row
        self._last_source = ""

    def generate(self, params: ExerciseParams) -> Exercise:
        """Generate an exercise.

        Args:
            params: Exercise parameters.

        Returns:
            Exercise text with warnings about corrected parameters.
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

    # ---------------------------------------------------------- helpers
    def _target_words(self, params: ExerciseParams) -> int:
        """Number of words to generate (more for a timed exercise).

        Args:
            params: Normalized parameters.

        Returns:
            Word count.
        """
        if params.time_limit_sec:
            minutes = params.time_limit_sec / 60
            return math.ceil(WORDS_PER_MINUTE_RESERVE * minutes)
        return params.word_count

    def _decorate(self, words: list[str], params: ExerciseParams) -> str:
        """Add capitals, digits and punctuation if they are switched on.

        Args:
            words: Lowercase words.
            params: Parameters with the flags.

        Returns:
            Final text.
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

    # ------------------------------------------------------------ modes
    def _keys_text(self, params: ExerciseParams, warnings: list[str]) -> str:
        """Mode KEYS: learning the layout row by row.

        Level 1 — home row, 2 — plus top, 3 — plus bottom, 4 — plus digits,
        5 — plus punctuation. Letters of the newest row appear twice as often.

        Args:
            params: Normalized parameters.
            warnings: List for messages.

        Returns:
            Text of pseudo-words made of the level's characters.
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
        """Mode WORDS: random words from the dictionary.

        Args:
            params: Normalized parameters.
            warnings: List for messages.

        Returns:
            Text of random words.
        """
        dictionary = self._source.get_words(params.layout_name)
        if not dictionary:
            warnings.append("Словарь пуст")
            return ""
        count = self._target_words(params)
        words = [self._rng.choice(dictionary) for _ in range(count)]
        return self._decorate(words, params)

    def _connected_text(self, params: ExerciseParams, warnings: list[str]) -> str:
        """Mode TEXT: a fragment of a built-in text (mostly classic literature).

        The fragment starts at a random sentence, so even one text gives
        different exercises; the previous text is not repeated.

        Args:
            params: Normalized parameters.
            warnings: List for messages.

        Returns:
            Text cut to the requested number of words (continued from the
            beginning if the rest of the text is short).
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
        """Mode CUSTOM: the user's own text.

        Args:
            params: Parameters with ``custom_text``.
            warnings: List for messages.

        Returns:
            Cleaned user text.
        """
        text, removed = clean_custom_text(params.custom_text, params.layout_name)
        if removed:
            warnings.append(f"Удалено символов, которых нет на раскладке: {removed}")
        if not text:
            warnings.append("Свой текст пуст")
        return text

    def _weak_keys_text(self, params: ExerciseParams, warnings: list[str]) -> str:
        """Mode WEAK_KEYS: adaptive exercise on problem keys.

        Every character gets the weight ``w_i = w_0 + k * e_i`` (ТЗ, п. 4.3.1).
        Words are chosen with ``random.choices`` by the sum of weights of their
        letters; if weak characters are still less than 50% of the text,
        words built only from weak characters are mixed in.

        Args:
            params: Parameters with ``weak_key_rates`` (char -> error %).
            warnings: List for messages.

        Returns:
            Adaptive text.
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
    """Share of characters that fall on weak keys (spaces excluded).

    Args:
        words: Words of the exercise.
        rates: Weak keys (base characters).
        layout_name: Layout of the exercise.

    Returns:
        Value from 0 to 1.
    """
    chars = [c for word in words for c in word]
    if not chars:
        return 0.0
    weak = sum(base_key_char(c, layout_name) in rates for c in chars)
    return weak / len(chars)


class RepositoryWordSource:
    """:class:`WordSource` backed by the database (words cached in memory)."""

    def __init__(self, layouts, words, texts) -> None:
        """Store repositories.

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
        """Find the id of a layout.

        Args:
            layout_name: Layout name.

        Returns:
            Id or ``None``.
        """
        layout = self._layouts.get_by_name(layout_name)
        return layout.id if layout else None

    def get_words(self, layout_name: str) -> list[str]:
        """Return dictionary words of a layout (read once, then cached).

        Args:
            layout_name: Layout name.

        Returns:
            Words.
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
        """Return a random built-in text of a layout.

        Args:
            layout_name: Layout name.
            exclude_title: Title of the previous text (not repeated).

        Returns:
            ``(title, content)`` or ``None``.
        """
        layout_id = self._layout_id(layout_name)
        text = self._texts.get_random(layout_id, exclude_title) if layout_id else None
        return (text.title, text.content) if text else None


def main() -> None:
    """Print a generated exercise to the console for a manual check."""
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
