"""Export of the session history to CSV for Microsoft Excel (ТЗ, п. 4.2.1).

UTF-8 with BOM lets Excel recognize Russian letters; the semicolon is the
list separator of the Russian locale, so columns open correctly by a
double click.
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
    """Write a number with a decimal comma (Russian Excel).

    Args:
        value: Number or ``None``.

    Returns:
        Text such as ``"46,5"``.
    """
    return "" if value is None else f"{value:.1f}".replace(".", ",")


def session_row(session: Session) -> list[str]:
    """Convert a session to a CSV row.

    Args:
        session: Session.

    Returns:
        Cells in the order of :data:`HEADER`.
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
    """Write sessions to a CSV file.

    Args:
        path: File chosen by the user.
        sessions: Sessions to export.

    Returns:
        Number of written sessions.
    """
    with Path(path).open("w", newline="", encoding=ENCODING) as file:
        writer = csv.writer(file, delimiter=DELIMITER)
        writer.writerow(HEADER)
        writer.writerows(session_row(s) for s in sessions)
    return len(sessions)
