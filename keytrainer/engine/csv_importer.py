"""Import of the session history from CSV (reverse of :mod:`csv_exporter`).

Reads the file written by "экспорт в csv": UTF-8 with or without BOM, the
semicolon (or comma) as separator and the decimal comma of Russian Excel.
"""

import csv
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from keytrainer.data.exceptions import ValidationError
from keytrainer.data.models import Session
from keytrainer.engine.csv_exporter import ENCODING, HEADER
from keytrainer.labels import MODE_TITLES

MODES_BY_TITLE = {title: mode for mode, title in MODE_TITLES.items()}
DATE_FORMAT = "%d.%m.%Y %H:%M"
YES, NO = "да", "нет"


@dataclass(frozen=True)
class ImportResult:
    """Outcome of reading a CSV file."""

    sessions: tuple[Session, ...]
    invalid: int  # rows that could not be read


def _number(text: str) -> float:
    """Read a number written with a decimal comma or a point.

    Args:
        text: Cell text, e.g. ``"46,5"``.

    Returns:
        Non-negative number.

    Raises:
        ValueError: The text is not a non-negative number.
    """
    value = float(text.strip().replace(",", "."))
    if value < 0:
        raise ValueError("negative number")
    return value


def parse_row(row: Sequence[str], user_id: int, layout_id: int | None) -> Session:
    """Convert a CSV row to a session.

    Args:
        row: Cells in the order of :data:`csv_exporter.HEADER`.
        user_id: Profile that receives the session.
        layout_id: Layout of the profile.

    Returns:
        Session without an id.

    Raises:
        ValueError: A cell has a wrong format.
        KeyError: Unknown exercise mode.
    """
    if len(row) != len(HEADER):
        raise ValueError("wrong number of cells")
    started, mode, wpm, cpm, rate, errors, duration, length, done = (
        cell.strip() for cell in row
    )
    completed = done.lower()
    if completed not in (YES, NO):
        raise ValueError("completed must be да/нет")
    return Session(
        user_id=user_id,
        layout_id=layout_id,
        started_at=datetime.strptime(started, DATE_FORMAT).isoformat(
            timespec="seconds"
        ),
        exercise_mode=MODES_BY_TITLE[mode],
        text_length=int(length),
        duration_sec=_number(duration),
        wpm=_number(wpm),
        cpm=_number(cpm),
        error_rate=_number(rate),
        errors_count=int(errors),
        is_completed=completed == YES,
    )


def read_sessions(path: Path, user_id: int, layout_id: int | None) -> ImportResult:
    """Read sessions from a CSV file.

    Args:
        path: File chosen by the user.
        user_id: Profile that receives the sessions.
        layout_id: Layout of the profile.

    Returns:
        Read sessions and the number of unreadable rows.

    Raises:
        ValidationError: The file is not a KeyTrainer history.
    """
    try:
        with Path(path).open(encoding=ENCODING, newline="") as file:
            first = file.readline()
            file.seek(0)
            delimiter = ";" if first.count(";") >= first.count(",") else ","
            rows = list(csv.reader(file, delimiter=delimiter))
    except UnicodeDecodeError as error:
        raise ValidationError("файл не в кодировке UTF-8") from error
    if not rows or tuple(cell.strip() for cell in rows[0]) != HEADER:
        raise ValidationError("это не файл истории KeyTrainer: другие заголовки")
    sessions: list[Session] = []
    invalid = 0
    for row in rows[1:]:
        if not any(cell.strip() for cell in row):
            continue  # empty line
        try:
            sessions.append(parse_row(row, user_id, layout_id))
        except (ValueError, KeyError):
            invalid += 1
    return ImportResult(tuple(sessions), invalid)
