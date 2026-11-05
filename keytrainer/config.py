from __future__ import annotations
"""Пути приложения, константы и настройка журналирования.

Все пути строятся через :mod:`pathlib`, поэтому один и тот же код работает в
Windows и Linux (ТЗ, п. 4.1.7). Если программа упакована PyInstaller,
база данных и журнал хранятся рядом с исполняемым файлом (портативный режим).
"""

import logging
import sys
from pathlib import Path

APP_NAME = "KeyTrainer Analytics"
DB_FILE_NAME = "keytrainer.db"
LOG_FILE_NAME = "keytrainer.log"


def get_app_dir() -> Path:
    """Вернуть каталог, где хранятся база данных и журнал.

    Returns:
        Папка исполняемого файла для упакованной сборки, иначе корень проекта.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def get_resources_dir() -> Path:
    """Вернуть каталог со встроенными словарями и текстами.

    Returns:
        Путь к ``keytrainer/resources`` (внутри пакета PyInstaller,
        если программа упакована).
    """
    bundle_dir = getattr(sys, "_MEIPASS", None)
    if bundle_dir:
        return Path(bundle_dir) / "keytrainer" / "resources"
    return Path(__file__).resolve().parent / "resources"


APP_DIR = get_app_dir()
RESOURCES_DIR = get_resources_dir()
DB_PATH = APP_DIR / DB_FILE_NAME
LOG_PATH = APP_DIR / LOG_FILE_NAME
SETTINGS_PATH = APP_DIR / "settings.json"


def setup_logging(log_path: Path = LOG_PATH, level: int = logging.INFO) -> None:
    """Настроить журналирование в ``keytrainer.log`` (ТЗ, п. 3.2 раздела API).

    Args:
        log_path: Файл, в который пишутся записи журнала.
        level: Минимальный уровень записываемых сообщений.
    """
    logging.basicConfig(
        filename=log_path,
        level=level,
        encoding="utf-8",
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
