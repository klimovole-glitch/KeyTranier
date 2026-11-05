from __future__ import annotations
"""Русские подписи, показываемые в интерфейсе и в файлах CSV (ТЗ, п. 4.3.3)."""

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
    """Выбрать русскую форму множественного числа для числа.

    Args:
        number: Число.
        one: Форма для 1 («ошибка»).
        few: Форма для 2-4 («ошибки»).
        many: Форма для 5-20 («ошибок»).

    Returns:
        Число с правильным словом, например «3 ошибки».
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
    """Отформатировать секунды как ``MM:SS``.

    Args:
        seconds: Длительность.

    Returns:
        Текст вида ``01:05``.
    """
    total = int(round(seconds))
    return f"{total // 60:02d}:{total % 60:02d}"


def format_number(value: float, digits: int = 1) -> str:
    """Отформатировать число с десятичной запятой, как в макетах («6,1»).

    Args:
        value: Число.
        digits: Знаков после запятой.

    Returns:
        Отформатированное число без завершающего «,0».
    """
    text = f"{value:.{digits}f}".replace(".", ",")
    return text[:-2] if digits == 1 and text.endswith(",0") else text
