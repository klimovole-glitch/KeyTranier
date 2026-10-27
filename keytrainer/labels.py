"""Russian captions shown in the interface and in CSV files (ТЗ, п. 4.3.3)."""

from keytrainer.data.keyboard_layouts import LAYOUT_EN, LAYOUT_RU
from keytrainer.data.models import ExerciseMode

MODE_TITLES = {
    ExerciseMode.KEYS: "изучение клавиш",
    ExerciseMode.WORDS: "случайные слова",
    ExerciseMode.TEXT: "связный текст",
    ExerciseMode.WEAK_KEYS: "работа над ошибками",
    ExerciseMode.CUSTOM: "свой текст",
}

LAYOUT_TITLES = {LAYOUT_RU: "RU ЙЦУКЕН", LAYOUT_EN: "EN QWERTY"}
LAYOUT_SHORT = {LAYOUT_RU: "ЙЦУКЕН", LAYOUT_EN: "QWERTY"}

KEY_LEVEL_TITLES = {
    1: "домашний ряд",
    2: "+ верхний ряд",
    3: "+ нижний ряд",
    4: "+ цифры",
    5: "+ знаки",
}


def plural(number: int, one: str, few: str, many: str) -> str:
    """Choose the Russian plural form for a number.

    Args:
        number: The number.
        one: Form for 1 ("ошибка").
        few: Form for 2-4 ("ошибки").
        many: Form for 5-20 ("ошибок").

    Returns:
        Number with the right word, e.g. "3 ошибки".
    """
    tail = number % 100
    if 11 <= tail <= 14:
        word = many
    elif number % 10 == 1:
        word = one
    elif 2 <= number % 10 <= 4:
        word = few
    else:
        word = many
    return f"{number} {word}"


def format_duration(seconds: float) -> str:
    """Format seconds as ``MM:SS``.

    Args:
        seconds: Duration.

    Returns:
        Text such as ``01:05``.
    """
    total = int(round(seconds))
    return f"{total // 60:02d}:{total % 60:02d}"


def format_number(value: float, digits: int = 1) -> str:
    """Format a number with a decimal comma, as in the mockups ("6,1").

    Args:
        value: Number.
        digits: Digits after the comma.

    Returns:
        Formatted number without a trailing ",0".
    """
    text = f"{value:.{digits}f}".replace(".", ",")
    return text[:-2] if digits == 1 and text.endswith(",0") else text
