from __future__ import annotations
"""Исключения, выбрасываемые слоем доступа к данным."""


class DataAccessError(Exception):
    """Базовый класс всех ошибок доступа к данным."""


class ValidationError(DataAccessError):
    """Выбрасывается, когда значение не удовлетворяет бизнес-ограничениям."""


class DuplicateNameError(DataAccessError):
    """Выбрасывается, когда UNIQUE-имя (профиль, слово) уже существует."""


class NotFoundError(DataAccessError):
    """Выбрасывается, когда запись с запрошенным идентификатором не существует."""
