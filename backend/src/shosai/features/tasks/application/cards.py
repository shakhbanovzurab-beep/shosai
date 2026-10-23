"""A board's cards: a new personal task or a copy where it is put, and a card moved or edited
(tasks plan §3.3, §3.5 flow 3, §3.14).

Writes take the board's lock. A new card is a hand-made personal task in its column's
status; a board shows 1 000 open cards at most, so only a done column takes more. A copy of
a card of the board takes its words, priority, dates, schedule, assignee name, values and
checklist unticked, never its cover, comments or Leo's marks; a workspace's task is not copied. A
moved card takes its new column's kind as its status, with that change's events and rules;
its title and priority change as the task's own patch changes them. A card's transaction is
opened in its task's space, as row-level security writes a workspace's rows only there.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from http import HTTPStatus
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.ids import new_id
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import Principal
from shosai.features.tasks.application.board_access import owned_board
from shosai.features.tasks.application.boards import board_failure
from shosai.features.tasks.application.columns import not_found as column_not_found
from shosai.features.tasks.application.placements import CardSpot, place
from shosai.features.tasks.application.recurring import copy_checklist
from shosai.features.tasks.application.scoping import Scoping, locked_task, rule_failure, scope_in
from shosai.features.tasks.application.task_edits import Edit, TaskEdits
from shosai.features.tasks.application.task_reads import TaskReads
from shosai.features.tasks.application.task_writes import NewTask, TaskWrites
from shosai.features.tasks.application.views import TaskView
from shosai.features.tasks.contracts import TaskNotFoundError
from shosai.features.tasks.domain.boards import BoardRuleError, check_card_room
from shosai.features.tasks.domain.changes import UNSET, TaskChange, Unset
from shosai.features.tasks.domain.placement import status_after_move
from shosai.features.tasks.domain.recurrence import recurrence_of
from shosai.features.tasks.domain.tasks import (
    Assignee,
    Priority,
    TaskRuleError,
    TaskStatus,
    checked_title,
)
from shosai.features.tasks.infrastructure.board_records import (
    BoardColumnRecord,
    TaskPlacementRecord,
)
from shosai.features.tasks.infrastructure.sticker_records import TaskStickerValueRecord
from shosai.features.tasks.infrastructure.task_records import TaskRecord

PLACED = TaskPlacementRecord


@dataclass(frozen=True, slots=True)
class NewCard:
    """A card to put on a board: its title, column and position, maybe a copy of a card."""

    title: str
    column_id: UUID
    position: int
    copy_of: UUID | None = None


@dataclass(frozen=True, slots=True)
class CardChange:
    """What a card's change sets: its title, its priority (`priority_sent`: `null` clears),
    and a move to a column and a position, which go together."""

    title: str | None = None
    priority: Priority | None = None
    priority_sent: bool = False
    move: tuple[UUID, int] | None = None


class Cards:
    """Puts, moves and edits the cards of the person's boards."""

    def __init__(
        self,
        transactions: HomeTransactions,
        ports: PortDirectory,
        writers: tuple[TaskWrites, TaskEdits],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._ports = ports
        self._writes, self._edits = writers
        self._clock = clock
        self._reads = TaskReads(transactions, ports)
        self._scoping = Scoping(transactions, ports)

    async def create(self, principal: Principal, board_id: UUID, new: NewCard) -> TaskView:
        """A new card where it is put."""
        try:
            title = checked_title(new.title)
        except TaskRuleError as error:
            raise rule_failure(error) from error
        viewer, now = principal.user_id, self._clock()
        async with self._transactions.begin(scope_in(principal, None)) as session:
            await owned_board(session, viewer, board_id, lock=True)
            kind = await _column_kind(session, board_id, new.column_id)
            if kind is not TaskStatus.DONE:
                await _room(session, viewer, board_id)
            source = (
                None
                if new.copy_of is None
                else await self._source(session, viewer, board_id, new.copy_of)
            )
            draft = _draft(title, kind, source)
            task_id = await self._writes.make(session, principal, draft)
            if source is not None:
                await copy_checklist(session, source, task_id, now)
                await _copy_values(session, source.id, (task_id, viewer), now)
            await place(
                session, viewer, task_id, CardSpot(board_id, new.column_id, new.position), now
            )
            view = await self._reads.view(session, viewer, task_id)
        return await self._reads.signed(principal, view)

    async def change(
        self, principal: Principal, board_id: UUID, task_id: UUID, change: CardChange
    ) -> TaskView:
        """The card after its move or edit."""
        viewer, now = principal.user_id, self._clock()
        scope = await self._scoping.space_of(principal, task_id)
        async with self._transactions.begin(scope) as session:
            await owned_board(session, viewer, board_id, lock=True)
            placed = await session.get(PLACED, (viewer, task_id))
            if placed is None or placed.board_id != board_id:
                raise TaskNotFoundError
            record = await locked_task(session, self._ports, viewer, task_id)
            status: TaskStatus | Unset = UNSET
            if change.move is not None:
                kind = await _column_kind(session, board_id, change.move[0])
                moved = status_after_move(TaskStatus(record.status), kind)
                status = UNSET if moved.value == record.status else moved
            edit = TaskChange(
                title=UNSET if change.title is None else change.title,
                priority=change.priority if change.priority_sent else UNSET,
                status=status,
            )
            await self._edits.apply(session, viewer, record, Edit(change=edit))
            if change.move is not None:
                spot = CardSpot(board_id, change.move[0], change.move[1])
                await place(session, viewer, task_id, spot, now)
            view = await self._reads.view(session, viewer, task_id)
        return await self._reads.signed(principal, view)

    async def _source(
        self, session: AsyncSession, viewer: UUID, board_id: UUID, task_id: UUID
    ) -> TaskRecord:
        """The card to copy: on this board, and the person's own."""
        placed = await session.get(PLACED, (viewer, task_id))
        if placed is None or placed.board_id != board_id:
            raise TaskNotFoundError
        source = await locked_task(session, self._ports, viewer, task_id, lock=False)
        if source.org_id is not None:
            raise AppError("workspace_task_copy", HTTPStatus.CONFLICT)
        return source


def _draft(title: str, kind: TaskStatus, source: TaskRecord | None) -> NewTask:
    if source is None:
        return NewTask(title=title, status=kind)
    return NewTask(
        title=title, description=source.description, status=kind,
        priority=Priority(source.priority) if source.priority else None,
        starts_on=source.starts_on, due_on=source.due_on,
        recurrence=recurrence_of(source.recurrence) if source.recurrence else None,
        assignee=Assignee(name=source.assignee_name),
    )  # fmt: skip


async def _column_kind(session: AsyncSession, board_id: UUID, column_id: UUID) -> TaskStatus:
    kind = await session.scalar(
        select(BoardColumnRecord.kind).where(
            BoardColumnRecord.id == column_id, BoardColumnRecord.board_id == board_id
        )
    )
    if kind is None:
        raise column_not_found()
    return TaskStatus(kind)


async def _room(session: AsyncSession, viewer: UUID, board_id: UUID) -> None:
    """A board shows 1 000 open cards at most."""
    open_cards = await session.scalar(
        select(func.count())
        .select_from(PLACED)
        .join(TaskRecord, TaskRecord.id == PLACED.task_id)
        .where(
            PLACED.user_id == viewer,
            PLACED.board_id == board_id,
            TaskRecord.status != TaskStatus.DONE.value,
        )
    )
    try:
        check_card_room(open_cards or 0)
    except BoardRuleError as error:
        raise board_failure(error) from error


async def _copy_values(
    session: AsyncSession, source_id: UUID, copy: tuple[UUID, UUID], now: datetime
) -> None:
    """The source card's values on its copy, a personal task of the person."""
    task_id, owner = copy
    values = TaskStickerValueRecord
    rows = await session.execute(
        select(values.sticker_id, values.state_id, values.number, values.text).where(
            values.task_id == source_id
        )
    )
    session.add_all(
        values(
            id=new_id(), task_id=task_id, sticker_id=sticker_id, user_id=owner, state_id=state_id,
            number=number, text=text, updated_at=now,
        )
        for sticker_id, state_id, number, text in rows
    )  # fmt: skip
