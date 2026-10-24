"""A page of a meeting's transcript for Leo: the lines that fit the tool's budget (step 14).

Lines are counted at four characters a token with each line's frame; a page names where the
next one starts. The owner's voice is the recording owner's speaker, or the live "me" side.
"""

from collections.abc import Sequence
from typing import Final

from shosai.core.ai.spend.estimates import CHARS_PER_TOKEN
from shosai.features.notes.channels.agent_tools import TRANSCRIPT_BUDGET, SpokenLine, TranscriptPage
from shosai.features.notes.domain.transcript import SIDE_SPEAKER, Side
from shosai.features.notes.domain.transcript_archive import TranscriptLine

LINES_READ: Final = 500
# Сколько символов JSON занимает строка расшифровки сверх своего текста.
LINE_FRAME_CHARS: Final = 80


def owner_voice(roles: dict[int, str]) -> int | None:
    """The meeting owner's voice: a recording's owner, or the live "me" side."""
    owned = [idx for idx, role in roles.items() if role == "owner"]
    if owned:
        return owned[0]
    return None if roles else SIDE_SPEAKER[Side.ME]


def page_of(lines: Sequence[TranscriptLine], owner: int | None) -> TranscriptPage:
    """The lines that fit the budget, and where the next page starts."""
    room = TRANSCRIPT_BUDGET * CHARS_PER_TOKEN
    shown: list[SpokenLine] = []
    for line in lines[:LINES_READ]:
        cost = len(line.text) + LINE_FRAME_CHARS
        if shown and cost > room:
            return TranscriptPage(lines=shown, next_from_ms=line.start_ms)
        room -= cost
        shown.append(
            SpokenLine(
                at_ms=line.start_ms,
                speaker=None if line.speaker_idx is None else line.speaker_idx + 1,
                owner_voice=line.speaker_idx is not None and line.speaker_idx == owner,
                text=line.text,
            )
        )
    following = lines[LINES_READ] if len(lines) > LINES_READ else None
    return TranscriptPage(
        lines=shown, next_from_ms=following.start_ms if following is not None else None
    )
