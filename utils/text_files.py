"""Чтение текстовых файлов в UTF-8 или Windows-1251."""

from pathlib import Path


def read_text(path: Path | str) -> str:
    """Прочитать текстовый файл, пробуя UTF-8 и переходя на cp1251."""
    path = Path(path)
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="cp1251")