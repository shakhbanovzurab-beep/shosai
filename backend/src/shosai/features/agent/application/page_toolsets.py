"""The toolsets a turn's page brings: its cabinet section and the subject it shows (ADR 0068
AG-D7). They come to the turn whole, whatever the room."""

from collections.abc import Mapping
from typing import Final

from shosai.features.agent.application.surface_digest import SubjectKind
from shosai.features.agent.application.turn_task import TurnPayload
from shosai.features.agent.domain.context import clean_path

# Раздел кабинета (`/app/<раздел>`) и наборы, которые он приносит.
SURFACE_TOOLSETS: Final[Mapping[str, str]] = {
    "meetings": "notes", "notes": "notes", "kanban": "tasks", "tasks": "tasks",
    "projects": "tasks", "file-manager": "files", "folders": "files", "billing": "account",
    "plans": "account", "upgrade": "account", "profile": "account",
}  # fmt: skip
SUBJECT_TOOLSETS: Final[Mapping[SubjectKind, str]] = {
    SubjectKind.MEETING: "notes",
    SubjectKind.TASK: "tasks",
    SubjectKind.BOARD: "tasks",
    SubjectKind.FILE: "files",
}


def page_section(payload: TurnPayload) -> str:
    """The cabinet section the turn was asked on (`/app/<section>`); empty for none."""
    path = clean_path(payload.path)
    parts = path.strip("/").split("/") if path is not None else []
    return parts[1] if len(parts) > 1 and parts[0] == "app" else ""


def surface_toolsets(payload: TurnPayload) -> frozenset[str]:
    """The toolsets the page brings: its section and the subject it shows."""
    names: set[str] = set()
    section = page_section(payload)
    if section in SURFACE_TOOLSETS:
        names.add(SURFACE_TOOLSETS[section])
    if payload.subject_kind is not None:
        names.add(SUBJECT_TOOLSETS[payload.subject_kind])
    return frozenset(names)
