"""Where a task came from, as the reader may see it: its meeting and the moment that proves it.

Notes decides who may read a meeting (inv-14): a meeting the reader cannot read, or one that
is gone, leaves the task's source without it (TK-D3: "its source shown as gone").
"""

from dataclasses import replace

from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.ports.directory import PortDirectory
from shosai.features.notes.contracts import (
    MEETING_FINDINGS,
    MEETING_READER,
    MeetingNotFoundError,
)
from shosai.features.tasks.application.views import FindingRef, MeetingRef, TaskView
from shosai.features.workspaces.contracts import Viewer


async def with_source(
    session: AsyncSession, ports: PortDirectory, viewer: Viewer, view: TaskView
) -> TaskView:
    """The task with its meeting and the finding's quote, when the reader may read them."""
    if view.meeting_id is None:
        return view
    facts = await ports.get(MEETING_READER).facts(session, viewer, [view.meeting_id])
    meeting = facts.get(view.meeting_id)
    if meeting is None:
        return view
    found = MeetingRef(meeting.meeting_id, meeting.title, meeting.started_at)
    quote = None
    if view.finding_id is not None:
        try:
            findings = await ports.get(MEETING_FINDINGS).of(session, viewer, view.meeting_id)
        except MeetingNotFoundError:
            findings = ()
        quote = next(
            (FindingRef(f.quote, f.start_ms) for f in findings if f.finding_id == view.finding_id),
            None,
        )
    return replace(view, meeting=found, finding=quote)
