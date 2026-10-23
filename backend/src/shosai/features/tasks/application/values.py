"""A task's values of stickers: set and cleared by whoever may read the task (§3.15, KG-D4).

A value is set of a sticker the person owns, or of one the task already carries — a
colleague's on a workspace task; anything else is `sticker_not_found`. It must be of the
sticker's kind, a state of that very sticker, within the number's or the text's bounds. The
value goes with the task and is written in its space; it raises the revision of the
reader's board and touches a meeting's set, as any change of the task's card does.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from http import HTTPStatus
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import Insert, insert
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.ids import new_id
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import Principal
from shosai.features.tasks.application.scoping import Scoping, locked_task, task_changed
from shosai.features.tasks.application.stickers import not_found, sticker_failure
from shosai.features.tasks.domain.stickers import (
    StickerKind,
    StickerRuleError,
    StickerValue,
    checked_value,
)
from shosai.features.tasks.domain.tasks import TaskSource
from shosai.features.tasks.infrastructure.sticker_records import (
    StickerRecord,
    StickerStateRecord,
    TaskStickerValueRecord,
)
from shosai.features.tasks.infrastructure.task_records import TaskRecord

VALUES = TaskStickerValueRecord


class Values:
    """Sets and clears the values of tasks."""

    def __init__(
        self,
        transactions: HomeTransactions,
        ports: PortDirectory,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._ports = ports
        self._clock = clock
        self._scoping = Scoping(transactions, ports)

    async def put(
        self, principal: Principal, task_id: UUID, sticker_id: UUID, value: StickerValue
    ) -> StickerValue:
        """The task's value of the sticker, set."""
        viewer, now = principal.user_id, self._clock()
        scope = await self._scoping.space_of(principal, task_id)
        async with self._transactions.begin(scope) as session:
            task = await locked_task(session, self._ports, viewer, task_id)
            if task.source == TaskSource.JIRA.value:
                raise AppError("jira_unsupported", HTTPStatus.CONFLICT)
            kind = await _settable(session, viewer, task_id, sticker_id)
            try:
                clean = checked_value(value, kind)
            except StickerRuleError as error:
                raise sticker_failure(error) from error
            if clean.state_id is not None:
                await _check_state(session, sticker_id, clean.state_id)
            await session.execute(_upsert(task, sticker_id, clean, now))
            await task_changed(session, viewer, task, now)
        return clean

    async def clear(self, principal: Principal, task_id: UUID, sticker_id: UUID) -> None:
        """The task's value of the sticker, cleared."""
        viewer, now = principal.user_id, self._clock()
        scope = await self._scoping.space_of(principal, task_id)
        async with self._transactions.begin(scope) as session:
            task = await locked_task(session, self._ports, viewer, task_id)
            if await session.get(StickerRecord, sticker_id) is None:
                raise not_found()
            await session.execute(
                delete(VALUES).where(VALUES.task_id == task_id, VALUES.sticker_id == sticker_id)
            )
            await task_changed(session, viewer, task, now)


async def _settable(
    session: AsyncSession, viewer: UUID, task_id: UUID, sticker_id: UUID
) -> StickerKind:
    """The kind of a sticker the person may set on the task: theirs, or one it carries."""
    carried = (
        select(VALUES.sticker_id)
        .where(VALUES.task_id == task_id, VALUES.sticker_id == sticker_id)
        .exists()
    )
    mine = (StickerRecord.user_id == viewer) & StickerRecord.org_id.is_(None)
    kind = await session.scalar(
        select(StickerRecord.kind).where(StickerRecord.id == sticker_id, mine | carried)
    )
    if kind is None:
        raise not_found()
    return StickerKind(kind)


async def _check_state(session: AsyncSession, sticker_id: UUID, state_id: UUID) -> None:
    found = await session.scalar(
        select(StickerStateRecord.id).where(
            StickerStateRecord.id == state_id, StickerStateRecord.sticker_id == sticker_id
        )
    )
    if found is None:
        raise AppError("state_not_found", HTTPStatus.NOT_FOUND)


def _upsert(task: TaskRecord, sticker_id: UUID, value: StickerValue, now: datetime) -> Insert:
    fields = {"state_id": value.state_id, "number": value.number, "text": value.text}
    return (
        insert(VALUES)
        .values(
            id=new_id(), task_id=task.id, sticker_id=sticker_id, user_id=task.user_id,
            org_id=task.org_id, updated_at=now, **fields,
        )
        .on_conflict_do_update(
            index_elements=[VALUES.task_id, VALUES.sticker_id], set_={**fields, "updated_at": now}
        )
    )  # fmt: skip
