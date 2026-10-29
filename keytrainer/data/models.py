"""Entity classes that mirror the tables of ``keytrainer.db``.

Each dataclass corresponds to one table of the ER diagram. Repositories
convert ``sqlite3.Row`` objects into these entities, so upper layers never
work with raw SQL rows.
"""

from dataclasses import dataclass
from enum import Enum


class ExerciseMode(str, Enum):
    """Exercise modes (ТЗ, п. 4.2.1)."""

    KEYS = "KEYS"
    WORDS = "WORDS"
    TEXT = "TEXT"
    WEAK_KEYS = "WEAK_KEYS"
    CUSTOM = "CUSTOM"


class Theme(str, Enum):
    """Interface color themes."""

    LIGHT = "LIGHT"
    DARK = "DARK"


@dataclass(frozen=True)
class Layout:
    """Keyboard layout (row of ``tbl_layouts``)."""

    id: int
    layout_name: str


@dataclass(frozen=True)
class Key:
    """Key of a layout with its finger and drawing position (``tbl_keys``)."""

    id: int
    layout_id: int
    key_char: str
    row_num: int
    finger: str
    pos_x: float
    pos_y: float


@dataclass
class User:
    """User profile with personal settings (``tbl_users``)."""

    id: int
    user_name: str
    layout_id: int | None
    theme: Theme
    font_size: int
    default_mode: ExerciseMode
    show_finger_hint: bool
    auto_pause: bool
    created_at: str


@dataclass(frozen=True)
class Word:
    """Dictionary word (``tbl_words``)."""

    id: int
    layout_id: int
    word: str


@dataclass
class Text:
    """Built-in or user text (``tbl_texts``)."""

    id: int
    layout_id: int
    title: str
    content: str
    is_custom: bool


@dataclass
class Session:
    """Result of one exercise (``tbl_sessions``).

    ``id`` is ``None`` until the session is saved to the database.
    """

    user_id: int
    layout_id: int
    started_at: str
    exercise_mode: ExerciseMode
    text_length: int
    duration_sec: float
    wpm: float
    cpm: float
    error_rate: float
    errors_count: int
    is_completed: bool = True
    id: int | None = None


@dataclass
class KeyStat:
    """Per-key statistics inside one session (``tbl_key_stats``)."""

    key_id: int
    attempts: int
    errors: int
    avg_latency_ms: float | None
    session_id: int | None = None
    id: int | None = None
