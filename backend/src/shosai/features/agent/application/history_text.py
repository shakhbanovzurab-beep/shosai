"""An earlier message as the model reads it again in a turn's history (Leo §7.3, step 5b).

A server note in its registered words, a question with its attachments' notes, an answer with
what its numbers stood for — kinds and ids, so a follow-up can name the same things, never
their titles' foreign text.
"""

from typing import Any, Final

from shosai.features.agent.application.attachment_notes import attachments_block
from shosai.features.agent.domain.threads import MessageRole
from shosai.features.agent.infrastructure.prompts import SOURCES_NOTE

# Сколько источников прошлого ответа называется в контексте: остальные — за пределами окна.
NOTED_SOURCES: Final = 10


def said(
    role: str,
    text: str,
    digest: dict[str, Any] | None,
    sources: list[dict[str, Any]],
    token: str,
) -> str:
    """A message as the model reads it again: a server note in its registered words, a question
    with its attachments' notes, an answer with what its numbers stood for."""
    if role == MessageRole.SERVER.value:
        note = (digest or {}).get("text")
        return note if isinstance(note, str) else ""
    if role == MessageRole.USER.value:
        attached = attachments_block(digest, token)
        return text if attached is None else f"{text}\n\n{attached}"
    return with_sources(text, sources)


def with_sources(text: str, sources: list[dict[str, Any]]) -> str:
    """An earlier answer with what its numbers stood for: kinds and ids, so a follow-up can
    name the same things, never their titles' foreign text."""
    if not sources:
        return text
    listed = "; ".join(
        f"[{n}] {source.get('kind')} {source.get('id')}"
        for n, source in enumerate(sources[:NOTED_SOURCES], start=1)
    )
    return f"{text}\n\n{SOURCES_NOTE.format(sources=listed)}"
