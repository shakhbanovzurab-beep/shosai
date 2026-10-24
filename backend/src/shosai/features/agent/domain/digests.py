"""A tool result cut to fit its budget, and still valid JSON (Leo §7.3; agent step 6).

A result longer than its tool's budget enters the context as a digest: the same JSON with
its longest lists cut to their first items and, if that is not enough, its longest texts cut
short, until it fits. Each cut list is named with how many items it held, so the model knows
what it did not see; the whole result is kept and paged with `core.read_result`. The cut
counts bytes, never words, so it does not depend on the result's language.
"""

import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Final

from pydantic import JsonValue

from shosai.features.agent.domain.budgets import estimate_tokens

# Строка короче этого не режется: обрывок короче фразы модели бесполезен.
SHORTEST_CUT: Final = 80
ELLIPSIS: Final = "…"
# Предел шагов урезания: каждый вдвое сокращает самый длинный список или текст.
MAX_CUTS: Final = 200

type Path = tuple[str | int, ...]


@dataclass(frozen=True, slots=True)
class Digest:
    """The cut result and, by the path of each cut list, how many items it held."""

    value: JsonValue
    omitted: dict[str, int] = field(default_factory=dict)


def compact(value: JsonValue) -> str:
    """JSON as the model reads it: no spaces, letters as they are."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def fits(value: JsonValue, budget: int) -> bool:
    """Whether the JSON stays within the budget's tokens."""
    return estimate_tokens(compact(value)) <= budget


def digest(value: JsonValue, budget: int) -> Digest | None:
    """The result cut to the budget; None when even its skeleton does not fit."""
    cut = json.loads(compact(value))
    omitted: dict[str, int] = {}
    for _ in range(MAX_CUTS):
        if fits(cut, budget):
            return Digest(cut, omitted)
        if not _halve_longest_list(cut, omitted) and not _halve_longest_text(cut):
            return None
    return None


def _halve_longest_list(value: JsonValue, omitted: dict[str, int]) -> bool:
    lists = [(path, node) for path, node in _nodes(value) if isinstance(node, list)]
    longest = max(lists, key=lambda entry: len(entry[1]), default=None)
    if longest is None or len(longest[1]) < 2:
        return False
    path, items = longest
    name = _name(path)
    omitted.setdefault(name, len(items))
    del items[(len(items) + 1) // 2 :]
    return True


def _halve_longest_text(value: JsonValue) -> bool:
    texts = [
        (slot, child)
        for slot, child in _slots(value)
        if isinstance(child, str) and len(child) > SHORTEST_CUT
    ]
    longest = max(texts, key=lambda entry: len(entry[1]), default=None)
    if longest is None:
        return False
    slot, text = longest
    slot.put(text[: max(SHORTEST_CUT, len(text) // 2)] + ELLIPSIS)
    return True


def _nodes(value: JsonValue, path: Path = ()) -> Iterator[tuple[Path, JsonValue]]:
    yield path, value
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _nodes(child, (*path, key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _nodes(child, (*path, index))


@dataclass(frozen=True, slots=True)
class _Slot:
    """A place inside a container: a dict's key or a list's index."""

    container: dict[str, JsonValue] | list[JsonValue]
    key: str | int

    def put(self, new: JsonValue) -> None:
        if isinstance(self.container, dict):
            self.container[str(self.key)] = new
        else:
            self.container[int(self.key)] = new


def _slots(value: JsonValue) -> Iterator[tuple[_Slot, JsonValue]]:
    """Every value inside a container, with its place."""
    for _, node in _nodes(value):
        if isinstance(node, dict):
            for key, child in node.items():
                yield _Slot(node, key), child
        elif isinstance(node, list):
            for index, child in enumerate(node):
                yield _Slot(node, index), child


def _name(path: Path) -> str:
    """`meetings[0].segments` for a path of keys and indices; `$` for the result itself."""
    name = ""
    for step in path:
        name += f"[{step}]" if isinstance(step, int) else (f".{step}" if name else step)
    return name or "$"
