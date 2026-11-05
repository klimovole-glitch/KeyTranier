from __future__ import annotations
"""Первоначальное заполнение справочных таблиц (раскладки, клавиши, слова, тексты).

Данные загружаются из текстовых файлов в ``keytrainer/resources`` при
первом создании базы данных (ТЗ, раздел 7).
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
    """Прочитать файл словаря, где одно слово на строку.

    Args:
        path: Текстовый файл в UTF-8.

    Returns:
        Непустые, очищенные от пробелов слова в нижнем регистре без дубликатов.
    """
    words = (line.strip().lower() for line in path.read_text("utf-8").splitlines())
    return list(dict.fromkeys(word for word in words if word))


def parse_texts(path: Path) -> list[tuple[str, str]]:
    """Прочитать библиотеку текстов, где каждый текст начинается со строки ``## Заголовок``.

    Args:
        path: Текстовый файл в UTF-8.

    Returns:
        Пары ``(заголовок, содержимое)``.
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
    """Вставить одну раскладку вместе с её клавишами, словами и текстами.

    Args:
        conn: Открытое соединение внутри транзакции.
        name: Имя раскладки.
        resources_dir: Папка с файлами словарей и текстов.
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
    """Заполнить справочные таблицы, если база данных пуста.

    Args:
        conn: Открытое соединение; транзакцию фиксирует вызывающий код.
        resources_dir: Папка с файлами словарей и текстов.

    Returns:
        ``True``, если данные вставлены, ``False``, если они уже были.
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


def sync_builtin_library(
    conn: sqlite3.Connection, resources_dir: Path = RESOURCES_DIR
) -> int:
    """Привести встроенные слова и тексты существующей базы данных к актуальному виду.

    Библиотека растёт от версии к версии: добавляются новые слова словаря;
    тексты сопоставляются по заголовку, новые добавляются, удалённые
    убираются. Пользовательские тексты (``is_custom = 1``) не затрагиваются.

    Args:
        conn: Открытое соединение; транзакцию фиксирует вызывающий код.
        resources_dir: Папка с файлами текстов.

    Returns:
        Количество добавленных текстов.
    """
    added = 0
    for name in (LAYOUT_RU, LAYOUT_EN):
        layout_id = LAYOUT_IDS[name]
        suffix = _LANG_SUFFIX[name]
        conn.executemany(
            "INSERT OR IGNORE INTO tbl_words (layout_id, word) VALUES (?, ?)",
            [
                (layout_id, word)
                for word in load_words(resources_dir / f"words_{suffix}.txt")
            ],
        )
        texts = dict(parse_texts(resources_dir / f"texts_{suffix}.txt"))
        stored = {
            row[0]
            for row in conn.execute(
                "SELECT title FROM tbl_texts WHERE layout_id = ? AND is_custom = 0",
                (layout_id,),
            )
        }
        new = [(layout_id, t, texts[t]) for t in texts if t not in stored]
        conn.executemany(
            "INSERT INTO tbl_texts (layout_id, title, content, is_custom) "
            "VALUES (?, ?, ?, 0)",
            new,
        )
        for title in stored - texts.keys():
            conn.execute(
                "DELETE FROM tbl_texts WHERE layout_id = ? AND is_custom = 0 "
                "AND title = ?",
                (layout_id, title),
            )
        added += len(new)
    if added:
        logger.info("Built-in library updated: %d texts added", added)
    return added
