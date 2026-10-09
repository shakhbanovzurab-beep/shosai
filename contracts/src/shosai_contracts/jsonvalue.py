"""Typed access to parsed JSON.

`json.load` returns `Any`; here it is narrowed once to the recursive type `Json`,
and from then on code reads values only through these functions. A malformed
document is an input error (`ContractInputError`), not a silent skip.
"""

import json
from pathlib import Path

type Json = dict[str, Json] | list[Json] | str | int | float | bool | None
type JsonObject = dict[str, Json]


class ContractInputError(ValueError):
    """An input document (the baseline or a v2 candidate) does not have the expected shape."""


def load_json(path: Path) -> Json:
    """Read a JSON file; a missing or corrupt file is an explicit input error."""
    try:
        with path.open(encoding="utf-8") as source:
            loaded: Json = json.load(source)
    except FileNotFoundError as error:
        raise ContractInputError(f"file not found: {path}") from error
    except json.JSONDecodeError as error:
        raise ContractInputError(f"invalid JSON in {path}: {error}") from error
    return loaded


def as_object(value: Json, where: str) -> JsonObject:
    """The value must be an object."""
    if not isinstance(value, dict):
        raise ContractInputError(f"{where}: expected an object")
    return value


def as_list(value: Json, where: str) -> list[Json]:
    """The value must be an array."""
    if not isinstance(value, list):
        raise ContractInputError(f"{where}: expected an array")
    return value


def as_str(value: Json, where: str) -> str:
    """The value must be a string."""
    if not isinstance(value, str):
        raise ContractInputError(f"{where}: expected a string")
    return value


def optional_object(value: Json) -> JsonObject:
    """The object, or an empty one if the value is missing or not an object (OpenAPI schemas)."""
    return value if isinstance(value, dict) else {}


def optional_list(value: Json) -> list[Json]:
    """The array, or an empty one if the value is missing or not an array."""
    return value if isinstance(value, list) else []


def optional_str(value: Json) -> str:
    """The string, or an empty string."""
    return value if isinstance(value, str) else ""


def str_list(value: Json, where: str) -> list[str]:
    """An array of strings; a missing value gives an empty array."""
    if value is None:
        return []
    return [as_str(item, f"{where}[{index}]") for index, item in enumerate(as_list(value, where))]
