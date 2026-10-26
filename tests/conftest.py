"""Shared pytest fixtures."""

import pytest

from keytrainer.data.database import Database


@pytest.fixture
def database(tmp_path):
    """Create an initialized database in a temporary folder.

    Args:
        tmp_path: Temporary directory provided by pytest.

    Returns:
        Ready-to-use :class:`Database`.
    """
    db = Database(tmp_path / "test.db")
    db.initialize()
    return db
