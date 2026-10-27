"""Repositories: the only place in the program that contains SQL queries."""

from keytrainer.data.repositories.key_repository import KeyRepository
from keytrainer.data.repositories.key_stat_repository import (
    KeyAggregate,
    KeyStatRepository,
)
from keytrainer.data.repositories.layout_repository import LayoutRepository
from keytrainer.data.repositories.session_repository import SessionRepository
from keytrainer.data.repositories.text_repository import TextRepository
from keytrainer.data.repositories.user_repository import UserRepository
from keytrainer.data.repositories.word_repository import WordRepository

__all__ = [
    "KeyAggregate",
    "KeyRepository",
    "KeyStatRepository",
    "LayoutRepository",
    "SessionRepository",
    "TextRepository",
    "UserRepository",
    "WordRepository",
]
