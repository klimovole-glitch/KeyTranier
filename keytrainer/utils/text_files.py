from __future__ import annotations
"""Чтение пользовательских TXT-файлов в кодировках, используемых в Windows и Linux."""

from pathlib import Path

ENCODINGS = ("utf-8-sig", "cp1251")


def read_text_file(path: Path) -> str:
    """Прочитать TXT-файл в UTF-8 или, если не получилось, в Windows-1251.

    Файлы, сохранённые Блокнотом Windows на русском, часто в cp1251.

    Args:
        path: Файл, выбранный пользователем.

    Returns:
        Содержимое файла.

    Raises:
        UnicodeDecodeError: Если не подходит ни одна кодировка.
    """
    data = Path(path).read_bytes()
    for encoding in ENCODINGS[:-1]:
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode(ENCODINGS[-1])
