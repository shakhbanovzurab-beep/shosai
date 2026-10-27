"""Meetings' tasks: a person's rooms closed with their account (A4c), a finished call's
handover and the sweep of each home every 300 s (A5).

Identity's events start the first, a call's finish the second and the scheduler the third.
Each is safe to repeat: a closed room, an ended call or a closed idle room is left as is.
"""

from datetime import timedelta
from typing import Final

from shosai.core.schedule.jobs import PeriodicJob
from shosai.core.tasks.declaration import (
    MAX_DELIVERIES,
    NO_RETRY,
    TRANSIENT_FAILURES,
    RetryPolicy,
    TaskDeclaration,
    TaskHandler,
    TaskKind,
)
from shosai.core.tasks.payloads import HomeTaskPayload
from shosai.core.tasks.queues import TaskQueue
from shosai.features.meetings.application.account_rooms import AccountRooms
from shosai.features.meetings.application.calls import Calls
from shosai.features.meetings.application.handover import HAND_OVER_CALL, CallTask
from shosai.features.meetings.application.sweep import Sweep
from shosai.features.meetings.domain.idle import SWEEP_EVERY

CLOSE_ACCOUNT_ROOMS: Final = TaskDeclaration(
    name="meetings.close_account_rooms",
    queue=TaskQueue.DEFAULT,
    payload=HomeTaskPayload,
    deadline=timedelta(minutes=2),
    retry=RetryPolicy(MAX_DELIVERIES, TRANSIENT_FAILURES),
)


SWEEP_ROOMS: Final = TaskDeclaration(
    name="meetings.sweep_rooms",
    queue=TaskQueue.DEFAULT,
    payload=HomeTaskPayload,
    deadline=timedelta(minutes=4),
    retry=NO_RETRY,
    kind=TaskKind.TICK,
)
PERIODIC_JOBS: Final = (PeriodicJob(SWEEP_ROOMS, every=SWEEP_EVERY),)


def task_handlers(
    rooms: AccountRooms, calls: Calls, sweep: Sweep
) -> tuple[TaskHandler[HomeTaskPayload], TaskHandler[CallTask], TaskHandler[HomeTaskPayload]]:
    """The slice's task handlers in this process."""

    async def close_account_rooms(payload: HomeTaskPayload) -> None:
        if payload.user_id is not None:
            await rooms.close_all(payload.home, payload.user_id)

    async def sweep_rooms(payload: HomeTaskPayload) -> None:
        await sweep.run(payload.home)

    return (
        TaskHandler(CLOSE_ACCOUNT_ROOMS, close_account_rooms),
        TaskHandler(HAND_OVER_CALL, calls.ended),
        TaskHandler(SWEEP_ROOMS, sweep_rooms),
    )
