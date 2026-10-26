"""What the native model proxy takes from a shipped client (agent plan §1.1; step 14).

The macOS and Windows apps send a live conversation for a short answer, or screenshots of a
task. The proxy keeps the newest of the conversation within its budget — each message cut to
its own cap, at most 50 messages, and the latest always kept, cut if it alone is over the
budget (the draft could drop the question itself). Screenshots arrive as base64, with or
without a `data:` prefix: the first six that decode strictly and are at most 8 MiB are kept,
each frame's size checked before it is decoded. A temperature is held to the providers'
range, and an answer to the proxy's own bound of output tokens.
"""

import base64
import binascii
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

MESSAGE_CHARS: Final = 128_000
KEPT_MESSAGES: Final = 50
CONVERSATION_CHARS: Final = 192_000
FRAMES: Final = 6
FRAME_BYTES: Final = 8 * 1024 * 1024
# Кадров просматривается не больше: испорченные не заставят перебирать тело без конца.
LOOKED_AT: Final = 4 * FRAMES
ANSWER_TOKENS: Final = 4096
HOTTEST: Final = 2.0
DATA_URL: Final = "data:"
# Сигнатуры картинок, которые принимают модели зрения; иное читается как PNG, как в черновике.
SIGNATURES: Final = (
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
)
WEBP: Final = (b"RIFF", b"WEBP")


@dataclass(frozen=True, slots=True)
class Said:
    """One message of the client's conversation: who said it and what."""

    role: str
    content: str


def kept_conversation(messages: Sequence[Said]) -> list[Said]:
    """The newest of the conversation within its budget, in order; the latest always kept."""
    present = [Said(m.role, m.content[:MESSAGE_CHARS]) for m in messages if m.content.strip()]
    newest = present[-KEPT_MESSAGES:]
    if not newest:
        return []
    *earlier, latest = newest
    latest = Said(latest.role, latest.content[:CONVERSATION_CHARS])
    kept, spent = [latest], len(latest.content)
    for message in reversed(earlier):
        if spent + len(message.content) > CONVERSATION_CHARS:
            break
        kept.append(message)
        spent += len(message.content)
    return kept[::-1]


def frames(images: Sequence[str] | None, single: str) -> list[bytes]:
    """The screenshots that decode, at most six, each at most 8 MiB."""
    candidates = list(images) if images else [single] if single else []
    found: list[bytes] = []
    for raw in candidates[:LOOKED_AT]:
        frame = decoded(raw)
        if frame is not None:
            found.append(frame)
        if len(found) == FRAMES:
            break
    return found


def decoded(raw: str) -> bytes | None:
    """A frame's bytes; None for an empty, oversized or malformed one."""
    text = raw.split(",", 1)[1] if raw.startswith(DATA_URL) and "," in raw else raw
    if not text or len(text) * 3 // 4 > FRAME_BYTES:
        return None
    try:
        return base64.b64decode(text, validate=True)
    except binascii.Error, ValueError:
        return None


def media_type(frame: bytes) -> str:
    """The frame's image type by its first bytes; PNG when none is recognised."""
    if frame[:4] == WEBP[0] and frame[8:12] == WEBP[1]:
        return "image/webp"
    return next((kind for magic, kind in SIGNATURES if frame.startswith(magic)), "image/png")


def answer_temperature(asked: float | None) -> float | None:
    """The temperature asked, held to the providers' range; None leaves the model's own."""
    return None if asked is None else min(max(asked, 0.0), HOTTEST)


def answer_tokens(asked: int | None) -> int:
    """The output bound: what the client asked, never above the proxy's own."""
    return ANSWER_TOKENS if asked is None else min(asked, ANSWER_TOKENS)
