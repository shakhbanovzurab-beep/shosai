"""One item of an action, from its plan to its outcome (Leo §8.4, ADR 0025).

An item keeps what its slice froze when the write was proposed — the targets and the data its
`execute` reads back — the preview the card showed, the arguments' names with hashes of their
values for the audit trail, and its outcome. An item of a call that sends data out (Leo §7.4)
keeps the call's arguments as its plan and, once the call ran, the id of its kept result. An
item is marked `executing` in its own commit before its slice is called (write-ahead): an
executor lost after that point leaves the item `outcome_unknown`, never retried; one lost
before it leaves the item `failed` (`not_started`), since nothing was attempted.
"""

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Final

from pydantic import JsonValue

from shosai.core.agent_tools.results import PreviewParam
from shosai.features.agent.domain.actions import ItemOutcome

HASH_CHARS: Final = 16
WRITE_EFFECT: Final = "write"


class ItemState(StrEnum):
    """Where an item stands; `executing` only between its write-ahead commit and its outcome."""

    PENDING = "pending"
    EXECUTING = "executing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    OUTCOME_UNKNOWN = "outcome_unknown"


class ItemCode(StrEnum):
    """Codes an item ends with besides its tool's own error codes."""

    NOT_STARTED = "not_started"
    LOST = "executor_lost"


@dataclass(frozen=True, slots=True)
class ActionItem:
    """One write of an action: its plan, its preview and its state."""

    tool: str
    targets: tuple[str, ...]
    plan: Mapping[str, JsonValue]
    fields: tuple[tuple[str, str], ...]
    preview_key: str
    preview_params: Mapping[str, PreviewParam] = field(default_factory=dict)
    # Как отменить запись (spec.reversibility): от этого зависят каналы одобрения и карточка.
    reversibility: str = "reversible"
    state: ItemState = ItemState.PENDING
    code: str | None = None
    # Эффект инструмента: запись, или вызов наружу, который ждал карточки (Leo §7.4).
    effect: str = WRITE_EFFECT
    # Хранимый результат вызова наружу после одобрения: его читает эпилог.
    result: str | None = None

    def stored(self) -> dict[str, JsonValue]:
        """The item as the action row keeps it."""
        return {
            "tool": self.tool,
            "targets": list(self.targets),
            "plan": dict(self.plan),
            "fields": [{"name": name, "hash": digest} for name, digest in self.fields],
            "preview": {"key": self.preview_key, "params": dict(self.preview_params)},
            "reversibility": self.reversibility,
            "state": self.state.value,
            "code": self.code,
            "effect": self.effect,
            "result": self.result,
        }

    def with_state(self, state: ItemState, code: str | None = None) -> ActionItem:
        """The item in another state."""
        return replace(self, state=state, code=code)

    def with_result(self, result: str) -> ActionItem:
        """The item succeeded, its call's result kept under the id."""
        return replace(self, state=ItemState.SUCCEEDED, code=None, result=result)

    @property
    def outcome(self) -> ItemOutcome:
        """The item's outcome as the action's end reads it."""
        match self.state:
            case ItemState.PENDING:
                return ItemOutcome.PENDING
            case ItemState.EXECUTING | ItemState.OUTCOME_UNKNOWN:
                return ItemOutcome.OUTCOME_UNKNOWN
            case ItemState.SUCCEEDED:
                return ItemOutcome.SUCCEEDED
            case ItemState.FAILED:
                return ItemOutcome.FAILED


def item_of(raw: Mapping[str, JsonValue]) -> ActionItem:
    """An item back from the action row."""
    preview = mapping(raw.get("preview"))
    code, result = raw.get("code"), raw.get("result")
    return ActionItem(
        tool=str(raw["tool"]),
        targets=tuple(str(target) for target in sequence(raw.get("targets"))),
        plan=mapping(raw.get("plan")),
        fields=tuple(
            (str(each.get("name")), str(each.get("hash")))
            for each in map(mapping, sequence(raw.get("fields")))
        ),
        preview_key=str(preview.get("key") or ""),
        preview_params=params_of(mapping(preview.get("params"))),
        reversibility=str(raw.get("reversibility") or "reversible"),
        state=ItemState(str(raw.get("state") or ItemState.PENDING.value)),
        code=None if code is None else str(code),
        effect=str(raw.get("effect") or WRITE_EFFECT),
        result=None if result is None else str(result),
    )


def mapping(value: JsonValue) -> dict[str, JsonValue]:
    """A JSON object, or an empty one."""
    return dict(value) if isinstance(value, dict) else {}


def sequence(value: JsonValue) -> list[JsonValue]:
    """A JSON array, or an empty one."""
    return list(value) if isinstance(value, list) else []


def params_of(raw: Mapping[str, JsonValue]) -> dict[str, PreviewParam]:
    """A preview's parameters: scalars only."""
    return {
        name: value
        for name, value in raw.items()
        if value is None or isinstance(value, str | int | float)
    }


def redacted(arguments: Mapping[str, JsonValue]) -> tuple[tuple[str, str], ...]:
    """Each argument's name with a short hash of its value: what the audit may keep of it."""
    return tuple(
        (name, hashlib.sha256(canonical(value).encode()).hexdigest()[:HASH_CHARS])
        for name, value in sorted(arguments.items())
    )


def canonical(value: JsonValue) -> str:
    """A value's JSON with sorted keys, so equal values hash alike."""
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def lost(items: Sequence[ActionItem]) -> tuple[ActionItem, ...]:
    """The items after their executor was lost: a started one's outcome is unknown, an item
    never started failed without being attempted, a finished one keeps its outcome."""
    return tuple(
        item.with_state(ItemState.OUTCOME_UNKNOWN, ItemCode.LOST.value)
        if item.state is ItemState.EXECUTING
        else item.with_state(ItemState.FAILED, ItemCode.NOT_STARTED.value)
        if item.state is ItemState.PENDING
        else item
        for item in items
    )
