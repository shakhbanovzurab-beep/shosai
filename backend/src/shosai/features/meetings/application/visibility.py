"""Which meetings a person sees: the access policy inside meetings' own query (inv-14).

A meeting is visible when workspaces' policy admits it for the viewer and it is not hidden
by a deletion (MT-D8). Every list, read, search hit, Leo read and share of meetings starts
here; identity's deletion window joins the rule with plan step 15.
"""

from sqlalchemy import Select, select

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
