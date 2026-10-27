"""Typing metrics (ТЗ, п. 4.3.1).

All functions are pure: they take numbers and return numbers, so they are
easy to check against reference values (ТЗ, п. 6.1 — расхождение ≤ 0.1).
"""

from collections.abc import Sequence

CHARS_PER_WORD = 5


def wpm(correct_chars: int, minutes: float) -> float:
    """Calculate typing speed in words per minute.

    ``WPM = (N_correct / 5) / T``, where one word is 5 characters.

    Args:
        correct_chars: Number of correctly typed characters.
        minutes: Typing time in minutes.

    Returns:
        Words per minute, ``0.0`` if the time is zero.
    """
    return (correct_chars / CHARS_PER_WORD) / minutes if minutes > 0 else 0.0


def cpm(correct_chars: int, minutes: float) -> float:
    """Calculate typing speed in characters per minute (``N_correct / T``).

    Args:
        correct_chars: Number of correctly typed characters.
        minutes: Typing time in minutes.

    Returns:
        Characters per minute, ``0.0`` if the time is zero.
    """
    return correct_chars / minutes if minutes > 0 else 0.0


def error_rate(errors: int, keystrokes: int) -> float:
    """Calculate the error rate ``E = N_errors / N_keystrokes * 100``.

    Args:
        errors: Number of wrong key presses.
        keystrokes: Number of all key presses.

    Returns:
        Error rate in percent, ``0.0`` if nothing was pressed.
    """
    return errors / keystrokes * 100 if keystrokes else 0.0


def accuracy(error_rate_percent: float) -> float:
    """Calculate accuracy ``A = 100 - E``.

    Args:
        error_rate_percent: Error rate in percent.

    Returns:
        Accuracy in percent.
    """
    return 100.0 - error_rate_percent


def moving_average(values: Sequence[float], window: int) -> list[float]:
    """Smooth a series with a trailing moving average.

    The first points use all values available so far, so the result has
    the same length as the input (needed for the history chart).

    Args:
        values: Series of numbers in chronological order.
        window: Number of last values to average (N).

    Returns:
        Smoothed series.

    Raises:
        ValueError: If ``window`` is less than 1.
    """
    if window < 1:
        raise ValueError("window must be >= 1")
    result = []
    for index in range(len(values)):
        chunk = values[max(0, index - window + 1) : index + 1]
        result.append(sum(chunk) / len(chunk))
    return result
