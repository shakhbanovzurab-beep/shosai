"""Which meetings a person sees: the access policy inside meetings' own query (inv-14).

A meeting is visible when workspaces' policy admits it for the viewer and it is not hidden
by a deletion (MT-D8). Every list, read, search hit, Leo read and share of meetings starts
here; identity's deletion window joins the rule with plan step 15. A change is written in
the meeting's own scope (`meeting_scope`).
"""

from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.meetings.contracts import MeetingNotFoundError
from shosai.features.meetings.infrastructure.meeting_records import (
    MEETING_RESOURCE,
    MeetingRecord,
)
from shosai.features.workspaces.contracts import AccessPolicy, Viewer


def visible_meetings(policy: AccessPolicy, viewer: Viewer) -> Select[MeetingRecord]:
    """The meetings the viewer may see now."""
    return select(MeetingRecord).where(
        policy.readable(MEETING_RESOURCE, viewer), MeetingRecord.deleted_at.is_(None)
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
