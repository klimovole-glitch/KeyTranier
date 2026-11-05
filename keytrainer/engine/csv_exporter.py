from __future__ import annotations
"""Экспорт истории сессий в CSV для Microsoft Excel (ТЗ, п. 4.2.1).

UTF-8 с BOM позволяет Excel распознать русские буквы; точка с запятой —
разделитель списка в русской локали, поэтому столбцы открываются
правильно по двойному щелчку.
"""

import csv
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from keytrainer.data.models import Session
from keytrainer.labels import MODE_TITLES

ENCODING = "utf-8-sig"
DELIMITER = ";"
HEADER = (
    "Дата и время",
    "Режим",
    "WPM",
    "CPM",
    "% ошибок",
    "Ошибок",
    "Длительность, с",
    "Длина, симв.",
    "Завершена",
)


def _decimal(value: float | None) -> str:
    """Записать число с десятичной запятой (русский Excel).

    Args:
        value: Число или ``None``.

    Returns:
        Текст вида ``"46,5"``.
    """
    return "" if value is None else f"{value:.1f}".replace(".", ",")


def session_row(session: Session) -> list[str]:
    """Преобразовать сессию в строку CSV.

    Args:
        session: Сессия.

    Returns:
        Ячейки в порядке :data:`HEADER`.
    """
    started = datetime.fromisoformat(session.started_at)
    return [
        started.strftime("%d.%m.%Y %H:%M"),
        MODE_TITLES[session.exercise_mode],
        _decimal(session.wpm),
        _decimal(session.cpm),
        _decimal(session.error_rate),
        str(session.errors_count),
        _decimal(session.duration_sec),
        str(session.text_length),
        "да" if session.is_completed else "нет",
    ]


def export_sessions(path: Path, sessions: Sequence[Session]) -> int:
    """Записать сессии в файл CSV.

    Args:
        path: Файл, выбранный пользователем.
        sessions: Экспортируемые сессии.

    Returns:
        Количество записанных сессий.
    """
    with Path(path).open("w", newline="", encoding=ENCODING) as file:
        writer = csv.writer(file, delimiter=DELIMITER)
        writer.writerow(HEADER)
        writer.writerows(session_row(s) for s in sessions)
    return len(sessions)
