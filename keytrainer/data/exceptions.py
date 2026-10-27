"""Exceptions raised by the Data Access layer."""


class DataAccessError(Exception):
    """Base class for all data access errors."""


class ValidationError(DataAccessError):
    """Raised when a value does not satisfy business constraints."""


class DuplicateNameError(DataAccessError):
    """Raised when a UNIQUE name (profile, word) already exists."""


class NotFoundError(DataAccessError):
    """Raised when a record with the requested id does not exist."""
