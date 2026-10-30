"""Connection to SQLite, schema creation, backup and recovery.

Implements ТЗ, п. 2.5-2.6 and 4.1.7:

* ``PRAGMA foreign_keys = ON`` for every connection;
* every unit of work runs in one transaction (commit or rollback);
* on start a copy ``keytrainer.db.bak`` is made;
* a damaged database is kept as ``keytrainer.db.corrupted_<time>`` and the
  data is restored from the backup, or a new database is created.
"""

import logging
import shutil
import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from datetime import datetime
from enum import Enum
from pathlib import Path

from keytrainer.config import RESOURCES_DIR
from keytrainer.data.seed import seed_reference_data, sync_builtin_library

logger = logging.getLogger(__name__)

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


class InitStatus(str, Enum):
    """Result of :meth:`Database.initialize`, shown to the user by the UI."""

    CREATED = "created"
    OPENED = "opened"
    RESTORED_FROM_BACKUP = "restored_from_backup"
    RECREATED = "recreated"


def is_healthy(db_path: Path) -> bool:
    """Check that a file is a readable, non-corrupted SQLite database.

    Args:
        db_path: Path to the database file.

    Returns:
        ``True`` if ``PRAGMA integrity_check`` returns ``ok``.
    """
    try:
        with closing(sqlite3.connect(db_path)) as conn:
            result = conn.execute("PRAGMA integrity_check").fetchone()
            return result is not None and result[0] == "ok"
    except sqlite3.DatabaseError:
        return False


class Database:
    """Gateway to the ``keytrainer.db`` file.

    Repositories receive an instance of this class and open short
    connections through :meth:`connection`. A new connection per operation
    is cheap in SQLite and lets background threads (heatmap, CSV export)
    work without sharing one connection object.
    """

    def __init__(self, db_path: Path, resources_dir: Path = RESOURCES_DIR) -> None:
        """Create the gateway without touching the disk.

        Args:
            db_path: Location of the database file.
            resources_dir: Folder with dictionaries for the first start.
        """
        self._path = Path(db_path)
        self._resources_dir = resources_dir

    @property
    def path(self) -> Path:
        """Path to the database file."""
        return self._path

    @property
    def backup_path(self) -> Path:
        """Path to the backup copy ``<db>.bak``."""
        return self._path.with_name(self._path.name + ".bak")

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        """Open a connection that commits on success and rolls back on error.

        Yields:
            Connection with ``sqlite3.Row`` rows and foreign keys enabled.

        Raises:
            sqlite3.Error: Re-raised after rollback if the block fails.
        """
        conn = sqlite3.connect(self._path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize(self) -> InitStatus:
        """Prepare the database for work: recover, create schema, seed, back up.

        Returns:
            What happened with the database file.
        """
        existed = self._path.exists()
        status = InitStatus.OPENED if existed else InitStatus.CREATED
        if existed and not is_healthy(self._path):
            status = self._recover()

        with self.connection() as conn:
            conn.executescript(SCHEMA_PATH.read_text("utf-8"))
            if not seed_reference_data(conn, self._resources_dir):
                sync_builtin_library(conn, self._resources_dir)

        self.make_backup()
        logger.info("Database initialized: %s", status.value)
        return status

    def make_backup(self) -> None:
        """Copy the database to ``<db>.bak`` using the SQLite backup API."""
        with (
            closing(sqlite3.connect(self._path)) as source,
            closing(sqlite3.connect(self.backup_path)) as target,
        ):
            source.backup(target)

    def _recover(self) -> InitStatus:
        """Keep the damaged file and restore data from the backup if possible.

        Returns:
            ``RESTORED_FROM_BACKUP`` or ``RECREATED``.
        """
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        corrupted = self._path.with_name(f"{self._path.name}.corrupted_{stamp}")
        shutil.move(self._path, corrupted)
        logger.error("Database is damaged, saved as %s", corrupted.name)

        if self.backup_path.exists() and is_healthy(self.backup_path):
            shutil.copy2(self.backup_path, self._path)
            logger.warning("Database restored from %s", self.backup_path.name)
            return InitStatus.RESTORED_FROM_BACKUP

        logger.warning("No valid backup, a new database will be created")
        return InitStatus.RECREATED
