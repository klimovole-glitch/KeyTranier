"""Классы сущностей, отражающие таблицы ``keytrainer.db``.

Каждый dataclass соответствует одной таблице ER-диаграммы. Репозитории
преобразуют объекты ``sqlite3.Row`` в эти сущности, поэтому верхние слои
никогда не работают с «сырыми» строками SQL.
"""

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum


class ExerciseMode(str, Enum):
    """Режимы упражнений (ТЗ, п. 4.2.1)."""

    KEYS = "KEYS"
    WORDS = "WORDS"
    TEXT = "TEXT"
    WEAK_KEYS = "WEAK_KEYS"
    CUSTOM = "CUSTOM"


class Theme(str, Enum):
    """Цветовые темы интерфейса."""

    LIGHT = "LIGHT"
    DARK = "DARK"


@dataclass(frozen=True)
class Layout:
    """Раскладка клавиатуры (строка ``tbl_layouts``)."""

    id: int
    layout_name: str


@dataclass(frozen=True)
class Key:
    """Клавиша раскладки с пальцем и позицией отрисовки (``tbl_keys``)."""

    id: int
    layout_id: int
    key_char: str
    row_num: int
    finger: str
    pos_x: float
    pos_y: float


@dataclass
class User:
    """Профиль пользователя с личными настройками (``tbl_users``)."""

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
    """Слово словаря (``tbl_words``)."""

    id: int
    layout_id: int
    word: str


@dataclass
class Text:
    """Встроенный или пользовательский текст (``tbl_texts``)."""

    id: int
    layout_id: int
    title: str
    content: str
    is_custom: bool


@dataclass
class Session:
    """Результат одного упражнения (``tbl_sessions``).

    ``id`` равен ``None``, пока сессия не сохранена в базе данных.
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
    """Статистика по клавишам внутри одной сессии (``tbl_key_stats``)."""

    key_id: int
    attempts: int
    errors: int
    avg_latency_ms: float | None
    session_id: int | None = None
    id: int | None = None
