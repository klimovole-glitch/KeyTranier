"""Initial filling of reference tables (layouts, keys, words, texts).

The data is loaded from text files in ``keytrainer/resources`` when the
database is created for the first time (ТЗ, раздел 7).
"""

import logging
import sqlite3
from datetime import datetime
from pathlib import Path

from keytrainer.config import RESOURCES_DIR
from keytrainer.data.keyboard_layouts import (
    LAYOUT_EN,
    LAYOUT_IDS,
    LAYOUT_RU,
    build_key_specs,
)

logger = logging.getLogger(__name__)

DEFAULT_USER_NAME = "Гость"
_LANG_SUFFIX = {LAYOUT_RU: "ru", LAYOUT_EN: "en"}
_TITLE_MARK = "## "


def load_words(path: Path) -> list[str]:
    """Read a dictionary file with one word per line.

    Args:
        path: UTF-8 text file.

    Returns:
        Non-empty, stripped, lowercase words without duplicates.
    """
    words = (line.strip().lower() for line in path.read_text("utf-8").splitlines())
    return list(dict.fromkeys(word for word in words if word))


def parse_texts(path: Path) -> list[tuple[str, str]]:
    """Read a text library where every text starts with a ``## Title`` line.

    Args:
        path: UTF-8 text file.

    Returns:
        Pairs ``(title, content)``.
    """
    texts: list[tuple[str, str]] = []
    title, lines = None, []
    for line in path.read_text("utf-8").splitlines() + [_TITLE_MARK]:
        if line.startswith(_TITLE_MARK):
            if title and lines:
                texts.append((title, " ".join(lines)))
            title, lines = line[len(_TITLE_MARK) :].strip(), []
        elif line.strip():
            lines.append(line.strip())
    return texts


def _seed_layout(conn: sqlite3.Connection, name: str, resources_dir: Path) -> None:
    """Insert one layout with its keys, words and texts.

    Args:
        conn: Open connection inside a transaction.
        name: Layout name.
        resources_dir: Folder with dictionary and text files.
    """
    layout_id = LAYOUT_IDS[name]
    suffix = _LANG_SUFFIX[name]
    conn.execute(
        "INSERT INTO tbl_layouts (id, layout_name) VALUES (?, ?)", (layout_id, name)
    )
    conn.executemany(
        "INSERT INTO tbl_keys (layout_id, key_char, row_num, finger, pos_x, pos_y) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [
            (layout_id, k.key_char, k.row_num, k.finger, k.pos_x, k.pos_y)
            for k in build_key_specs(name)
        ],
    )
    words = load_words(resources_dir / f"words_{suffix}.txt")
    conn.executemany(
        "INSERT OR IGNORE INTO tbl_words (layout_id, word) VALUES (?, ?)",
        [(layout_id, word) for word in words],
    )
    texts = parse_texts(resources_dir / f"texts_{suffix}.txt")
    conn.executemany(
        "INSERT INTO tbl_texts (layout_id, title, content, is_custom) "
        "VALUES (?, ?, ?, 0)",
        [(layout_id, title, content) for title, content in texts],
    )
    logger.info("Seeded %s: %d words, %d texts", name, len(words), len(texts))


def seed_reference_data(
    conn: sqlite3.Connection, resources_dir: Path = RESOURCES_DIR
) -> bool:
    """Fill reference tables if the database is empty.

    Args:
        conn: Open connection; the caller commits the transaction.
        resources_dir: Folder with dictionary and text files.

    Returns:
        ``True`` if data was inserted, ``False`` if it already existed.
    """
    if conn.execute("SELECT COUNT(*) FROM tbl_layouts").fetchone()[0]:
        return False
    for name in (LAYOUT_RU, LAYOUT_EN):
        _seed_layout(conn, name, resources_dir)
    conn.execute(
        "INSERT INTO tbl_users (user_name, layout_id, created_at) VALUES (?, ?, ?)",
        (
            DEFAULT_USER_NAME,
            LAYOUT_IDS[LAYOUT_RU],
            datetime.now().isoformat(timespec="seconds"),
        ),
    )
    return True
