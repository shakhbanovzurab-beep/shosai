"""What a reader of a meeting is shown: its notes' state, its folder, its map node by node.

The notes are `processing` while the meeting's latest run works, `ready` once a write-up
exists, `failed` when the latest run failed with nothing written, and `none` for a meeting
whose run never started (nothing was said). A folder is personal (MT-D7): only the owner
files their own personal meeting, so a reader who is not the owner never sees the
owner's folder, and a company's meeting is in no folder. The map is served as a
collection (§10): its nodes in pre-order, each with its parent and depth.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Final
from uuid import UUID

from shosai.features.meetings.domain.runs import RunState

MAP_NODES_MAX: Final = 2_000


class NotesState(StrEnum):
    """Where a meeting's notes are."""

    NONE = "none"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class FilingRule(StrEnum):
    """Why a meeting cannot go into a folder; the value is the API's error code."""

    NOT_OWNER = "meeting_not_yours"
    COMPANY_MEETING = "company_meeting_has_no_folder"


def notes_state(latest_run: RunState | None, *, written: bool) -> NotesState:
    """The notes' state from the latest run and whether a write-up exists."""
    if latest_run in {RunState.PENDING, RunState.RUNNING}:
        return NotesState.PROCESSING
    if written:
        return NotesState.READY
    if latest_run is RunState.FAILED:
        return NotesState.FAILED
    return NotesState.NONE


def filing_refusal(*, owner: bool, company: bool) -> FilingRule | None:
    """Why the reader may not file this meeting, or None when they may."""
    if not owner:
        return FilingRule.NOT_OWNER
    if company:
        return FilingRule.COMPANY_MEETING
    return None


def shown_folder(folder_id: UUID | None, *, owner: bool) -> UUID | None:
    """The meeting's folder as this reader sees it: the owner's own, nobody else's."""
    return folder_id if owner else None


@dataclass(frozen=True, slots=True)
class MapRow:
    """A node of the map: its place in pre-order, its parent's, its depth and label."""

    index: int
    parent: int | None
    depth: int
    label: str


def map_rows(tree: Mapping[str, Any]) -> list[MapRow]:
    """The stored map's nodes in pre-order, the root first; at most 2 000 of them.

    Walked with a stack, not recursion: a map carried over from the draft may be deep.
    """
    rows: list[MapRow] = []
    stack: list[tuple[Mapping[str, Any], int | None, int]] = [(tree, None, 0)]
    while stack and len(rows) < MAP_NODES_MAX:
        node, parent, depth = stack.pop()
        index = len(rows)
        rows.append(MapRow(index, parent, depth, str(node.get("label", ""))))
        children = node.get("children") or []
        stack.extend((child, index, depth + 1) for child in reversed(children))
    return rows
