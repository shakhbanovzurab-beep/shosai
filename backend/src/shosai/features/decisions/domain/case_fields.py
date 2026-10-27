"""Strict reading of a dataset case's fields: a wrong type is an error, never a guess.

A labelled set is the ground the thresholds are fitted on; a case whose fields are missing or
of another type would quietly bend them, so it is refused with the field's name.
"""

from collections.abc import Mapping


def text(raw: Mapping[str, object], name: str) -> str:
    """A string field."""
    value = raw.get(name)
    if not isinstance(value, str):
        message = f"поле {name}: нужна строка"
        raise ValueError(message)
    return value


def whole(raw: Mapping[str, object], name: str) -> int:
    """A non-negative integer field."""
    value = raw.get(name)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        message = f"поле {name}: нужно неотрицательное целое"
        raise ValueError(message)
    return value


def flag(raw: Mapping[str, object], name: str) -> bool:
    """A boolean field."""
    value = raw.get(name)
    if not isinstance(value, bool):
        message = f"поле {name}: нужно true или false"
        raise ValueError(message)
    return value


def records(raw: Mapping[str, object], name: str) -> list[Mapping[str, object]]:
    """A list of objects."""
    value = raw.get(name)
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        message = f"поле {name}: нужен список объектов"
        raise ValueError(message)
    return list(value)
