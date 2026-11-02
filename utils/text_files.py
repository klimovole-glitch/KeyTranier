"""Reading text files in UTF-8 or Windows-1251."""

from pathlib import Path


def read_text(path: Path | str) -> str:
    """Read a text file, trying UTF-8 and falling back to cp1251."""
    path = Path(path)
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="cp1251")