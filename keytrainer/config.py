"""Application-wide paths, constants and logging setup.

All paths are built with :mod:`pathlib`, so the same code works on Windows
and Linux (ТЗ, п. 4.1.7). When the program is frozen by PyInstaller, the
database and the log are stored next to the executable (Portable mode).
"""

import logging
import sys
from pathlib import Path

APP_NAME = "KeyTrainer Analytics"
DB_FILE_NAME = "keytrainer.db"
LOG_FILE_NAME = "keytrainer.log"


def get_app_dir() -> Path:
    """Return the directory where the database and the log are stored.

    Returns:
        Folder of the executable for a frozen build, otherwise the project root.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def get_resources_dir() -> Path:
    """Return the directory with built-in dictionaries and texts.

    Returns:
        Path to ``keytrainer/resources`` (inside the PyInstaller bundle
        when the program is frozen).
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
    """Configure logging to ``keytrainer.log`` (ТЗ, п. 3.2 раздела API).

    Args:
        log_path: File that receives log records.
        level: Minimal level of records to write.
    """
    logging.basicConfig(
        filename=log_path,
        level=level,
        encoding="utf-8",
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
