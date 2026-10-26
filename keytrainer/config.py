"""Application configuration and path settings."""

import sys
from pathlib import Path


def get_base_path() -> Path:
    """Get the base path for data and config files.

    If the application is frozen (compiled with PyInstaller),
    returns the directory of the executable. Otherwise, returns
    the project root directory.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent.parent


BASE_DIR = get_base_path()

DATA_DIR = BASE_DIR / "data"
RESOURCES_DIR = BASE_DIR / "keytrainer" / "resources"

DB_PATH = BASE_DIR / "keytrainer.db"
DB_BAK_PATH = BASE_DIR / "keytrainer.db.bak"
LOG_PATH = BASE_DIR / "keytrainer.log"

LAYOUTS = {
    "RU_JCUKEN": "ЙЦУКЕН",
    "EN_QWERTY": "QWERTY",
}

DEFAULT_LAYOUT = "RU_JCUKEN"
DEFAULT_MODE = "words"
DEFAULT_DURATION = 60

# UI Settings
WINDOW_MIN_WIDTH = 900
WINDOW_MIN_HEIGHT = 600
FONT_FAMILY = "JetBrains Mono"
FONT_SIZE = 16

# Colors
COLOR_BG = "#1e1e1e"
COLOR_TEXT = "#d4d4d4"
COLOR_CORRECT = "#4ec9b0"
COLOR_ERROR = "#f44747"
COLOR_HINT = "#569cd6"