from __future__ import annotations
"""Импорт истории сессий из CSV (обратная операция к :mod:`csv_exporter`).

Читает файл, записанный кнопкой «экспорт в csv»: UTF-8 с BOM или без него,
точка с запятой (или запятая) как разделитель и десятичная запятая русского Excel.
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
    """Итог чтения файла CSV."""

    sessions: tuple[Session, ...]
    invalid: int  # строки, которые не удалось прочитать


def _number(text: str) -> float:
    """Прочитать число, записанное с десятичной запятой или точкой.

    Args:
        text: Текст ячейки, например ``"46,5"``.

    Returns:
        Неотрицательное число.

    Raises:
        ValueError: Текст не является неотрицательным числом.
    """
    value = float(text.strip().replace(",", "."))
    if value < 0:
        raise ValueError("negative number")
    return value


def parse_row(row: Sequence[str], user_id: int, layout_id: int | None) -> Session:
    """Преобразовать строку CSV в сессию.

    Args:
        row: Ячейки в порядке :data:`csv_exporter.HEADER`.
        user_id: Профиль, получающий сессию.
        layout_id: Раскладка профиля.

    Returns:
        Сессия без id.

    Raises:
        ValueError: Ячейка имеет неверный формат.
        KeyError: Неизвестный режим упражнения.
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
    """Прочитать сессии из файла CSV.

    Args:
        path: Файл, выбранный пользователем.
        user_id: Профиль, получающий сессии.
        layout_id: Раскладка профиля.

    Returns:
        Прочитанные сессии и количество нечитаемых строк.

    Raises:
        ValidationError: Файл не является историей KeyTrainer.
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
            continue  # пустая строка
        try:
            sessions.append(parse_row(row, user_id, layout_id))
        except (ValueError, KeyError):
            invalid += 1
    return ImportResult(tuple(sessions), invalid)
