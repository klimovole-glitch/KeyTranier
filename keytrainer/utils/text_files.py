"""Reading user TXT files in the encodings used on Windows and Linux."""

from pathlib import Path

ENCODINGS = ("utf-8-sig", "cp1251")


def read_text_file(path: Path) -> str:
    """Read a TXT file in UTF-8 or, if that fails, in Windows-1251.

    Files saved by Windows Notepad in Russian are often in cp1251.

    Args:
        path: File chosen by the user.

    Returns:
        File content.

    Raises:
        UnicodeDecodeError: If neither encoding fits.
    """
    data = Path(path).read_bytes()
    for encoding in ENCODINGS[:-1]:
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode(ENCODINGS[-1])
