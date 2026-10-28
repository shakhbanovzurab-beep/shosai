"""Connectors' tasks (plan §3.5): sweeps of due grants, keep-alive, revocation, key rotation.

The sweeps are ticks the scheduler queues per home; each due grant becomes a task in its
owner's scope, which claims the grant before it works it, so a duplicate task does nothing.
A grant task is not retried by the broker: its due time is the retry — the revocation moves
it forward after a refusal, the keep-alive an hour after a failure.
"""

from datetime import timedelta
from typing import Any, Final
from uuid import UUID

from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.schedule.jobs import DueRowSource, PeriodicJob
from shosai.core.tasks.declaration import NO_RETRY, TaskDeclaration, TaskHandler, TaskKind
from shosai.core.tasks.payloads import HomeTaskPayload
from shosai.core.tasks.queues import TaskQueue
from shosai.core.tasks.sender import TaskSender
from shosai.features.connectors.application.grant_tokens import GrantTokens
from shosai.features.connectors.application.key_rotation import KeyRotation
from shosai.features.connectors.application.lifecycle_sweeps import DueGrant, DueGrants
from shosai.features.connectors.application.revocation import GrantRevoker


class GrantTaskPayload(HomeTaskPayload):
    """A task on one grant, in its owner's scope."""

    grant_id: UUID


def _tick(
    name: str, deadline: timedelta, queue: TaskQueue = TaskQueue.DEFAULT
) -> TaskDeclaration[HomeTaskPayload]:
    return TaskDeclaration(
        name=name, queue=queue, payload=HomeTaskPayload, deadline=deadline, retry=NO_RETRY,
        kind=TaskKind.TICK,
    )  # fmt: skip


def _work(name: str, deadline: timedelta) -> TaskDeclaration[GrantTaskPayload]:
    return TaskDeclaration(
        name=name, queue=TaskQueue.DEFAULT, payload=GrantTaskPayload, deadline=deadline,
        retry=NO_RETRY,
    )  # fmt: skip


KEEPALIVE_SWEEP: Final = _tick("connectors.keepalive_due", timedelta(minutes=1))
REVOKE_SWEEP: Final = _tick("connectors.revoke_due", timedelta(minutes=1))
ROTATE_KEYS: Final = _tick("connectors.rotate_keys", timedelta(minutes=30), TaskQueue.BULK)
KEEP_ALIVE: Final = _work("connectors.keep_alive", timedelta(minutes=1))
REVOKE_GRANT: Final = _work("connectors.revoke_grant", timedelta(minutes=2))
DUE_SOURCES: Final = (
    DueRowSource(KEEPALIVE_SWEEP, every=timedelta(minutes=5)),
    DueRowSource(REVOKE_SWEEP, every=timedelta(seconds=30)),
)
PERIODIC_JOBS: Final = (PeriodicJob(ROTATE_KEYS, every=timedelta(days=7)),)


def grant_task(home: Home, due: DueGrant) -> GrantTaskPayload:
    """The task payload of one due grant."""
    return GrantTaskPayload(
        home=home, user_id=due.user_id, org_id=due.org_id, grant_id=due.grant_id
    )


def connectors_task_handlers(
    parts: tuple[DueGrants, GrantTokens, GrantRevoker, KeyRotation], tasks: TaskSender
) -> tuple[TaskHandler[Any], ...]:
    """The lifecycle's tasks bound to the process."""
    due, tokens, revoker, rotation = parts

    async def keepalive_due(payload: HomeTaskPayload) -> None:
        for grant in await due.keepalive(payload.home):
            await tasks.send(KEEP_ALIVE, grant_task(payload.home, grant))

    async def revoke_due(payload: HomeTaskPayload) -> None:
        for grant in await due.revocations(payload.home):
            await tasks.send(REVOKE_GRANT, grant_task(payload.home, grant))

    async def keep_alive(payload: GrantTaskPayload) -> None:
        await tokens.keep_alive(_scope(payload), payload.grant_id)

    async def revoke_grant(payload: GrantTaskPayload) -> None:
        await revoker.revoke_due(_scope(payload), payload.grant_id)

    async def rotate_keys(payload: HomeTaskPayload) -> None:
        await rotation.run(payload.home)

    return (
        TaskHandler(KEEPALIVE_SWEEP, keepalive_due),
        TaskHandler(REVOKE_SWEEP, revoke_due),
        TaskHandler(KEEP_ALIVE, keep_alive),
        TaskHandler(REVOKE_GRANT, revoke_grant),
        TaskHandler(ROTATE_KEYS, rotate_keys),
    )


def _scope(payload: GrantTaskPayload) -> TenancyScope:
    if payload.user_id is None:
        message = "задача гранта без человека"
        raise ValueError(message)
    return TenancyScope(payload.home, payload.user_id, payload.org_id)
