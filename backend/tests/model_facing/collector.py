"""Walking model-facing text and checking that instructions are written in Latin script.

The rule is core's `non_latin_letters`, the one studio applies to the operator's platform text.
"""

from collections.abc import Iterable, Iterator, Mapping, Set
from dataclasses import dataclass
from enum import Enum

from pydantic import BaseModel

from shosai.core.kernel.latin_script import non_latin_letters
from tests.model_facing.registry import ModelFacingSource

EXCERPT_LENGTH = 80


@dataclass(frozen=True, slots=True)
class ModelText:
    """A string for a model and its path inside the source object."""

    path: str
    text: str


def iter_texts(value: object, path: str = "$") -> Iterator[ModelText]:
    """Every string of an object, including mapping keys and enum values."""
    yield from _walk(value, path, frozenset())


def find_violations(sources: Iterable[ModelFacingSource]) -> list[str]:
    """Source strings with letters outside the Latin script, except declared literals."""
    violations: list[str] = []
    for source in sources:
        for value in source.collect():
            for item in iter_texts(value):
                letters = non_latin_letters(item.text)
                if letters and item.text not in source.allowed_literals:
                    excerpt = item.text[:EXCERPT_LENGTH]
                    violations.append(
                        f"{source.owner} / {source.name} {item.path}: "
                        f"{''.join(letters)} in {excerpt!r}"
                    )
    return violations


def _walk(value: object, path: str, ancestors: frozenset[int]) -> Iterator[ModelText]:
    # Член StrEnum — тоже строка; enum разбирается первым, чтобы путь называл член.
    if isinstance(value, Enum):
        yield from _walk(value.value, f"{path}<{type(value).__name__}.{value.name}>", ancestors)
        return
    if isinstance(value, str):
        yield ModelText(path, value)
        return
    if isinstance(value, int | float) or value is None:
        return
    if id(value) in ancestors:
        return
    nested = ancestors | {id(value)}
    yield from _walk_container(value, path, nested)


def _walk_container(value: object, path: str, ancestors: frozenset[int]) -> Iterator[ModelText]:
    if isinstance(value, type) and issubclass(value, Enum):
        for member in value:
            yield from _walk(member, f"{path}<{value.__name__}>", ancestors)
    elif isinstance(value, type) and issubclass(value, BaseModel):
        yield from _walk(value.model_json_schema(), f"{path}<{value.__name__} schema>", ancestors)
    elif isinstance(value, BaseModel):
        yield from _walk(
            value.model_dump(mode="json"), f"{path}<{type(value).__name__}>", ancestors
        )
    elif isinstance(value, Mapping):
        for key, item in value.items():
            yield from _walk(key, f"{path}.<key>", ancestors)
            yield from _walk(item, f"{path}[{key!r}]", ancestors)
    elif isinstance(value, list | tuple | Set):
        for index, item in enumerate(value):
            yield from _walk(item, f"{path}[{index}]", ancestors)
    else:
        message = (
            f"{path}: {type(value).__name__} не поддерживается; "
            "источник возвращает строки, словари, списки, enum или модели Pydantic"
        )
        raise TypeError(message)
