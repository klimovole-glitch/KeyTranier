"""Tests of schema creation, reference data, backup and recovery."""

from keytrainer.data.database import Database, InitStatus
from keytrainer.data.keyboard_layouts import LAYOUT_EN, LAYOUT_RU, base_key_char
from keytrainer.data.repositories import (
    KeyRepository,
    LayoutRepository,
    TextRepository,
    WordRepository,
)

EXPECTED_TABLES = {
    "tbl_layouts",
    "tbl_keys",
    "tbl_users",
    "tbl_words",
    "tbl_texts",
    "tbl_sessions",
    "tbl_key_stats",
}


def test_all_tables_created(database):
    """All seven tables of the ER diagram exist."""
    with database.connection() as conn:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row["name"] for row in rows}
    assert EXPECTED_TABLES <= tables


def test_foreign_keys_enabled(database):
    """Every connection has foreign keys turned on."""
    with database.connection() as conn:
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_reference_data_seeded(database):
    """Both layouts have keys, at least 1000 words and built-in texts."""
    layouts = LayoutRepository(database)
    for name in (LAYOUT_RU, LAYOUT_EN):
        layout = layouts.get_by_name(name)
        assert layout is not None
        assert len(KeyRepository(database).get_by_layout(layout.id)) == 47
        assert WordRepository(database).count_by_layout(layout.id) >= 1000
        assert TextRepository(database).get_by_layout(layout.id, custom=False)


def test_home_row_fingers(database):
    """Home row keys have the fingers of the touch typing method."""
    keys = KeyRepository(database)
    assert keys.get_by_char(1, "ф").finger == "L_PINKY"
    assert keys.get_by_char(1, "а").finger == "L_INDEX"
    assert keys.get_by_char(2, "j").finger == "R_INDEX"
    assert keys.get_by_char(2, " ").finger == "THUMB"


def test_base_key_char_maps_shift_symbols():
    """Capital letters and Shift symbols map to their base key."""
    assert base_key_char("Ф", LAYOUT_RU) == "ф"
    assert base_key_char(",", LAYOUT_RU) == "."
    assert base_key_char("?", LAYOUT_EN) == "/"


def test_second_initialize_does_not_duplicate(database):
    """Repeated start keeps one copy of the reference data."""
    words_before = WordRepository(database).count()
    assert database.initialize() == InitStatus.OPENED
    assert WordRepository(database).count() == words_before


def test_backup_created(database):
    """A backup copy appears next to the database on start."""
    assert database.backup_path.exists()


def test_restore_from_backup(tmp_path):
    """A damaged file is kept and the data is restored from the backup."""
    db = Database(tmp_path / "kt.db")
    db.initialize()
    db.path.write_bytes(b"this is not a database" * 100)

    assert db.initialize() == InitStatus.RESTORED_FROM_BACKUP
    assert list(tmp_path.glob("kt.db.corrupted_*"))
    assert WordRepository(db).count() > 0


def test_recreate_without_backup(tmp_path):
    """Without a backup a new database with reference data is created."""
    db = Database(tmp_path / "kt.db")
    db.path.write_bytes(b"garbage" * 100)

    assert db.initialize() == InitStatus.RECREATED
    assert LayoutRepository(db).count() == 2
