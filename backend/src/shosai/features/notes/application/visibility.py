"""Which meetings a person sees: the access policy inside meetings' own query (inv-14).

A meeting is visible when workspaces' policy admits it for the viewer, it is not hidden by
a deletion (MT-D8) and its owner's account is not in identity's deletion window (ADR 0045
point 6). Every list, read, search hit, Leo read, other slices' read and share of meetings
starts here. A change is written in the meeting's own scope (`meeting_scope`).
"""

from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.notes.contracts import MeetingNotFoundError
from shosai.features.notes.infrastructure.meeting_records import (
    MEETING_RESOURCE,
    MeetingRecord,
)
from shosai.features.workspaces.contracts import AccessPolicy, Viewer


def visible_meetings(policy: AccessPolicy, viewer: Viewer) -> Select[MeetingRecord]:
    """The meetings the viewer may see now."""
    return select(MeetingRecord).where(
        policy.readable(MEETING_RESOURCE, viewer),
        MeetingRecord.deleted_at.is_(None),
        MeetingRecord.account_hidden.is_(False),
    )


async def meeting_scope(
    session: AsyncSession, policy: AccessPolicy, reader: TenancyScope, meeting_id: UUID
) -> TenancyScope:
    """The scope a change of the meeting is written in: its company's, else the reader's own.

    Row-level security writes a company's row only in that company's scope, so a change
    first finds the meeting the reader may see, in their own scope; `MeetingNotFoundError`
    when they may not.
    """
    if reader.user_id is None:
        message = "встречу меняет человек: в скоупе нужен user_id"
        raise ValueError(message)
    found = await session.execute(
        visible_meetings(policy, Viewer(reader.user_id))
        .with_only_columns(MeetingRecord.org_id)
        .where(MeetingRecord.id == meeting_id)
    )
    row = found.first()
    if row is None:
        raise MeetingNotFoundError
    return TenancyScope(reader.home, reader.user_id, row.org_id)


async def meeting_for(
    session: AsyncSession,
    policy: AccessPolicy,
    reader: UUID,
    meeting_id: UUID,
    *,
    lock: bool = False,
) -> tuple[MeetingRecord, bool]:
    """The meeting the reader may see and whether they may manage it; locked for a change.

    `MeetingNotFoundError` for a meeting they may not read, however it exists.
    """
    viewer = Viewer(reader)
    statement = (
        visible_meetings(policy, viewer)
        .add_columns(policy.manageable(MEETING_RESOURCE, viewer).label("manageable"))
        .where(MeetingRecord.id == meeting_id)
    )
    if lock:
        statement = statement.with_for_update(of=MeetingRecord)
    found = (await session.execute(statement)).first()
    if found is None:
        raise MeetingNotFoundError
    return found[0], bool(found[1])
