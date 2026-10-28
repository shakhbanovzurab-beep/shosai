"""Meetings' tasks: a person's rooms closed with their account (A4c), a finished call's
handover and the sweep of each home every 300 s (A5).

Identity's events start the first, a call's finish the second and the scheduler the third.
The handover files the board's last picture in the owner's File Manager (A11b), then ends the
call. Each is safe to repeat: a closed room, a filed picture, an ended call or a closed idle
room is left as is.
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
from shosai.features.meetings.application.board import Boards
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
    rooms: AccountRooms, calls: Calls, sweep: Sweep, boards: Boards
) -> tuple[TaskHandler[HomeTaskPayload], TaskHandler[CallTask], TaskHandler[HomeTaskPayload]]:
    """The slice's task handlers in this process."""

    async def close_account_rooms(payload: HomeTaskPayload) -> None:
        if payload.user_id is not None:
            await rooms.close_all(payload.home, payload.user_id)

    async def hand_over_call(task: CallTask) -> None:
        await boards.file_picture(task)
        await calls.ended(task)

    async def sweep_rooms(payload: HomeTaskPayload) -> None:
        await sweep.run(payload.home)

    return (
        TaskHandler(CLOSE_ACCOUNT_ROOMS, close_account_rooms),
        TaskHandler(HAND_OVER_CALL, hand_over_call),
        TaskHandler(SWEEP_ROOMS, sweep_rooms),
    )
