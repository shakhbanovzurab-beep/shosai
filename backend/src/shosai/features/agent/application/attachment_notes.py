"""A question's attachment notes as the model reads them, wrapped as the person's own file
(agent step 12b; Leo §7.4)."""

from collections.abc import Mapping
from typing import Any

from shosai.features.agent.domain.attachments import OWN_FILE, noted
from shosai.features.agent.domain.wrapper import wrap
from shosai.features.agent.infrastructure.prompts import (
    ATTACHED_IMAGE,
    ATTACHED_MORE,
    ATTACHED_TEXT,
    ATTACHED_UNREADABLE,
)


def note_text(note: Mapping[str, Any]) -> str:
    """One attachment's note as the model reads it."""
    name = str(note.get("name", ""))
    kind = note.get("kind")
    if kind == "image":
        return ATTACHED_IMAGE.format(name=name)
    if kind == "document":
        text = ATTACHED_TEXT.format(name=name, text=str(note.get("text", "")))
        ref = note.get("ref")
        return f"{text}\n{ATTACHED_MORE.format(ref=ref)}" if ref else text
    return ATTACHED_UNREADABLE.format(name=name, code=str(note.get("code", "failed")))


def attachments_block(digest: Mapping[str, Any] | None, token: str) -> str | None:
    """The question's attachments as one block wrapped as the person's own file, or None."""
    notes = noted(digest)
    if not notes:
        return None
    return wrap("\n\n".join(note_text(note) for note in notes), OWN_FILE, token)
