"""What a meeting tool's result rests on: the meeting, in its space (ADR 0068 AG-D1).

Every read of a meeting names it as the source of Leo's answer, with the workspace it belongs
to — none for the person's own; for a colleague's meeting shared into a workspace, that
workspace — so the answer cites it and the panel shows where it is from; a transcript page
names the moment it starts at and its first words.
"""

from collections.abc import Sequence
from typing import Final
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.agent_tools.sources import QUOTE_MAX, TITLE_MAX, SourceKind, SourceRef
from shosai.features.notes.infrastructure.meeting_records import MEETING_RESOURCE, MeetingRecord
from shosai.features.workspaces.contracts import AccessPolicy, Viewer

# Отрывок строки расшифровки в источнике: начало страницы, а не вся она.
LINE_QUOTE: Final = 300


def meeting_source(
    meeting: tuple[UUID, str, UUID | None], *, locator: str | None = None, quote: str = ""
) -> SourceRef:
    """A meeting as a source: its id, title and workspace, a moment and a quote if given."""
    meeting_id, title, org_id = meeting
    return SourceRef(
        kind=SourceKind.MEETING, id=str(meeting_id), title=title[:TITLE_MAX], org_id=org_id,
        locator=locator, quote=quote[:QUOTE_MAX],
    )  # fmt: skip


def moment(ms: int) -> str:
    """A moment of a recording as the person reads it: `m:ss`, or `h:mm:ss` past an hour."""
    seconds = max(ms, 0) // 1000
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


async def meeting_spaces(
    session: AsyncSession, policy: AccessPolicy, viewer: UUID, meetings: Sequence[MeetingRecord]
) -> dict[UUID, UUID | None]:
    """Each meeting's space for Leo: its workspace, or the one a colleague's personal meeting
    is shared to the person through; None for the person's own."""
    spaces: dict[UUID, UUID | None] = {meeting.id: meeting.org_id for meeting in meetings}
    shared = [m.id for m in meetings if m.org_id is None and m.user_id != viewer]
    if shared:
        spaces |= await policy.shared_into(session, MEETING_RESOURCE, shared, Viewer(viewer))
    return spaces
