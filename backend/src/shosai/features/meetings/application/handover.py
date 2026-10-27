"""The handover of a finished call: the task that ends it (meetings plan §3.5 flow 4).

The call's chat, the board's picture and the participants' tracks pass to the owner's meeting
in notes from steps B2 and B3 on; the handover ends the call once they are passed. It runs as
the owner in the room's space, and a repeat finds the call ended and changes nothing.
"""

from datetime import timedelta
from typing import Final
from uuid import UUID

from shosai.core.tasks.declaration import (
    MAX_DELIVERIES,
    TRANSIENT_FAILURES,
    RetryPolicy,
    TaskDeclaration,
)
from shosai.core.tasks.payloads import HomeTaskPayload
from shosai.core.tasks.queues import TaskQueue


class CallTask(HomeTaskPayload):
    """A finished call of its owner, in the room's space."""

    call_id: UUID


HAND_OVER_CALL: Final = TaskDeclaration(
    name="meetings.hand_over_call",
    queue=TaskQueue.DEFAULT,
    payload=CallTask,
    deadline=timedelta(minutes=2),
    retry=RetryPolicy(MAX_DELIVERIES, TRANSIENT_FAILURES),
)
