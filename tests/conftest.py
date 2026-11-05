"""Общие фикстуры pytest."""

import pytest

from keytrainer.data.database import Database


@pytest.fixture
def database(tmp_path):
    """Создать инициализированную базу данных во временной папке.

    Args:
        tmp_path: Временный каталог, предоставляемый pytest.

    Returns:
        Готовая к использованию :class:`Database`.
    """
    db = Database(tmp_path / "test.db")
    db.initialize()
    return db
