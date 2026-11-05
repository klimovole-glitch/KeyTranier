from __future__ import annotations
"""Метрики набора текста (ТЗ, п. 4.3.1).

Все функции чистые: принимают числа и возвращают числа, поэтому их легко
сверить с эталонными значениями (ТЗ, п. 6.1 — расхождение ≤ 0.1).
"""

from collections.abc import Sequence

CHARS_PER_WORD = 5


def wpm(correct_chars: int, minutes: float) -> float:
    """Вычислить скорость набора в словах в минуту.

    ``WPM = (N_correct / 5) / T``, где одно слово — 5 символов.

    Args:
        correct_chars: Количество правильно набранных символов.
        minutes: Время набора в минутах.

    Returns:
        Слов в минуту, ``0.0`` при нулевом времени.
    """
    return (correct_chars / CHARS_PER_WORD) / minutes if minutes > 0 else 0.0


def cpm(correct_chars: int, minutes: float) -> float:
    """Вычислить скорость набора в символах в минуту (``N_correct / T``).

    Args:
        correct_chars: Количество правильно набранных символов.
        minutes: Время набора в минутах.

    Returns:
        Символов в минуту, ``0.0`` при нулевом времени.
    """
    return correct_chars / minutes if minutes > 0 else 0.0


def error_rate(errors: int, keystrokes: int) -> float:
    """Вычислить долю ошибок ``E = N_errors / N_keystrokes * 100``.

    Args:
        errors: Количество неверных нажатий клавиш.
        keystrokes: Количество всех нажатий клавиш.

    Returns:
        Доля ошибок в процентах, ``0.0``, если ничего не нажато.
    """
    return errors / keystrokes * 100 if keystrokes else 0.0


def accuracy(error_rate_percent: float) -> float:
    """Вычислить точность ``A = 100 - E``.

    Args:
        error_rate_percent: Доля ошибок в процентах.

    Returns:
        Точность в процентах.
    """
    return 100.0 - error_rate_percent


def moving_average(values: Sequence[float], window: int) -> list[float]:
    """Сгладить ряд скользящим средним по предыдущим значениям.

    Первые точки используют все доступные на данный момент значения, поэтому
    результат имеет ту же длину, что и вход (нужно для графика истории).

    Args:
        values: Ряд чисел в хронологическом порядке.
        window: Количество последних значений для усреднения (N).

    Returns:
        Сглаженный ряд.

    Raises:
        ValueError: Если ``window`` меньше 1.
    """
    if window < 1:
        raise ValueError("window must be >= 1")
    result = []
    for index in range(len(values)):
        chunk = values[max(0, index - window + 1) : index + 1]
        result.append(sum(chunk) / len(chunk))
    return result
