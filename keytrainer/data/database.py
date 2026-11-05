from __future__ import annotations
"""Подключение к SQLite, создание схемы, резервное копирование и восстановление.

Реализует ТЗ, п. 2.5-2.6 и 4.1.7:

* ``PRAGMA foreign_keys = ON`` для каждого соединения;
* каждая единица работы выполняется в одной транзакции (commit или rollback);
* при запуске создаётся копия ``keytrainer.db.bak``;
* повреждённая база сохраняется как ``keytrainer.db.corrupted_<время>``, а
  данные восстанавливаются из резервной копии либо создаётся новая база.
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
    """Результат :meth:`Database.initialize`, показываемый пользователю в интерфейсе."""

    CREATED = "created"
    OPENED = "opened"
    RESTORED_FROM_BACKUP = "restored_from_backup"
    RECREATED = "recreated"


def is_healthy(db_path: Path) -> bool:
    """Проверить, что файл — читаемая неповреждённая база данных SQLite.

    Args:
        db_path: Путь к файлу базы данных.

    Returns:
        ``True``, если ``PRAGMA integrity_check`` возвращает ``ok``.
    """
    try:
        with closing(sqlite3.connect(db_path)) as conn:
            result = conn.execute("PRAGMA integrity_check").fetchone()
            return result is not None and result[0] == "ok"
    except sqlite3.DatabaseError:
        return False


class Database:
    """Шлюз к файлу ``keytrainer.db``.

    Репозитории получают экземпляр этого класса и открывают короткие
    соединения через :meth:`connection`. Новое соединение на каждую операцию
    в SQLite дёшево и позволяет фоновым потокам (тепловая карта, экспорт CSV)
    работать без общего объекта соединения.
    """

    def __init__(self, db_path: Path, resources_dir: Path = RESOURCES_DIR) -> None:
        """Создать шлюз, не обращаясь к диску.

        Args:
            db_path: Расположение файла базы данных.
            resources_dir: Папка со словарями для первого запуска.
        """
        self._path = Path(db_path)
        self._resources_dir = resources_dir

    @property
    def path(self) -> Path:
        """Путь к файлу базы данных."""
        return self._path

    @property
    def backup_path(self) -> Path:
        """Путь к резервной копии ``<db>.bak``."""
        return self._path.with_name(self._path.name + ".bak")

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        """Открыть соединение, которое фиксирует изменения при успехе и откатывает при ошибке.

        Yields:
            Соединение со строками ``sqlite3.Row`` и включёнными внешними ключами.

        Raises:
            sqlite3.Error: Повторно выбрасывается после отката, если блок завершился ошибкой.
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
        """Подготовить базу данных к работе: восстановить, создать схему, заполнить, сделать копию.

        Returns:
            Что произошло с файлом базы данных.
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
        """Скопировать базу данных в ``<db>.bak`` через API резервного копирования SQLite."""
        with (
            closing(sqlite3.connect(self._path)) as source,
            closing(sqlite3.connect(self.backup_path)) as target,
        ):
            source.backup(target)

    def _recover(self) -> InitStatus:
        """Сохранить повреждённый файл и по возможности восстановить данные из копии.

        Returns:
            ``RESTORED_FROM_BACKUP`` или ``RECREATED``.
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
