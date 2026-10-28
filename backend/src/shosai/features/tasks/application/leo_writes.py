"""What Leo's write tools do to tasks, once the person approved them (tasks step 8).

A batch of new tasks is checked whole when it is proposed — the space the person may write
in, each task's rules, members and projects, the board's room — and made whole when it is
executed, again checked, in one transaction of the space: Leo writes them (`created_by =
leo`) on the person's behalf, on top of the board's first column when one is named. A task
made from a team chat carries its chat only when the server planned it from the chat (TK-D13).
A change, a tick and a move act on one task the person may read, through the same rules as
the cabinet's: field presence, Leo's marks, the next recurring task, the stopwatch's
automations and the boards' revisions. A Jira card is left to Jira's writes (step 13).
"""

from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from http import HTTPStatus
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.kernel.errors import AppError
from shosai.features.identity.contracts import Principal
from shosai.features.tasks.application import clock_rules
from shosai.features.tasks.application.board_access import incoming_board, owned_board
from shosai.features.tasks.application.placements import (
    CardSpot,
    board_columns,
    column_kind,
    first_column_of,
    place,
)
from shosai.features.tasks.application.scoping import raise_revisions, rule_failure
from shosai.features.tasks.application.task_edits import Edit, TaskEdits
from shosai.features.tasks.application.task_writes import NewTask, TaskWrites, checked_draft
from shosai.features.tasks.domain.boards import BOARD_OPEN_CARDS_MAX
from shosai.features.tasks.domain.changes import UNSET, TaskChange
from shosai.features.tasks.domain.chat_source import ChatOrigin
from shosai.features.tasks.domain.placement import spot_for, status_after_move
from shosai.features.tasks.domain.tasks import (
    CreatedBy,
    TaskRule,
    TaskRuleError,
    TaskSource,
    TaskStatus,
)
from shosai.features.tasks.infrastructure.board_records import TaskPlacementRecord
from shosai.features.tasks.infrastructure.task_records import TaskRecord


@dataclass(frozen=True, slots=True)
class LeoBatch:
    """Tasks Leo makes in one go: all in one space, maybe on one board, maybe from a chat."""

    drafts: tuple[NewTask, ...]
    workspace_id: UUID | None = None
    board_id: UUID | None = None
    chat: ChatOrigin | None = None


def jira_refused(record: TaskRecord) -> None:
    """A Jira card waits for Jira's writes (step 13)."""
    if record.source == TaskSource.JIRA.value:
        raise AppError("jira_unsupported", HTTPStatus.CONFLICT)


async def checked_batch(
    session: AsyncSession, writes: TaskWrites, principal: Principal, batch: LeoBatch
) -> LeoBatch:
    """The batch with every task checked as the cabinet checks one, or the first refusal."""
    drafts: list[NewTask] = []
    for draft in batch.drafts:
        try:
            clean = checked_draft(replace(draft, workspace_id=batch.workspace_id))
            # Начало позже срока — ошибка, как в кабинете; без срока начало отпадает при записи.
            if clean.starts_on and clean.due_on and clean.starts_on > clean.due_on:
                raise TaskRuleError(TaskRule.RANGE_INVALID)
        except TaskRuleError as error:
            raise rule_failure(error) from error
        await writes.admit(session, principal, clean)
        drafts.append(clean)
    board_id = batch.board_id
    if board_id is not None:
        await owned_board(session, principal.user_id, board_id)
        await _room(session, principal.user_id, board_id, len(drafts))
    elif batch.workspace_id is None:
        board_id = await _incoming_with_room(session, principal.user_id, len(drafts))
    return replace(batch, drafts=tuple(drafts), board_id=board_id)


async def make_batch(
    session: AsyncSession,
    writes: TaskWrites,
    principal: Principal,
    batch: LeoBatch,
    now: datetime,
) -> tuple[UUID, ...]:
    """The batch made, checked again, in the caller's transaction of its space."""
    checked = await checked_batch(session, writes, principal, batch)
    made: list[UUID] = []
    for draft in checked.drafts:
        leo = replace(draft, created_by=CreatedBy.LEO, chat=checked.chat)
        made.append(await writes.make(session, principal, leo))
    if checked.board_id is not None:
        await _put_on_board(session, principal.user_id, checked.board_id, made, now)
    return tuple(made)


async def _put_on_board(
    session: AsyncSession, viewer: UUID, board_id: UUID, task_ids: Sequence[UUID], now: datetime
) -> None:
    """The new tasks on top of the board's first to-do column, the first of them topmost; the
    board's revision goes up."""
    column_id = await first_column_of(session, board_id, TaskStatus.TODO)
    if column_id is None:
        message = "у доски нет колонки «к выполнению»"
        raise ValueError(message)
    for position, task_id in enumerate(task_ids):
        await place(session, viewer, task_id, CardSpot(board_id, column_id, position), now)
        record = await session.get(TaskRecord, task_id)
        if record is not None:
            await clock_rules.arrived(session, record, (board_id, column_id), now)
    # Новые карточки — изменение доски: открытая доска примет её версию только с выросшей ревизией.
    await raise_revisions(session, viewer, task_ids, now)


async def _incoming_with_room(session: AsyncSession, viewer: UUID, adding: int) -> UUID | None:
    """Where personal tasks go when Leo names no board: the incoming board while it has room
    (no task stays off every board, the owner's rule of 2026-10-28); a full one leaves them
    waiting for it."""
    board_id = await incoming_board(session, viewer)
    if board_id is None or await _held(session, viewer, board_id) + adding > BOARD_OPEN_CARDS_MAX:
        return None
    return board_id


async def _room(session: AsyncSession, viewer: UUID, board_id: UUID, adding: int) -> None:
    """A board shows 1 000 open cards at most."""
    if await _held(session, viewer, board_id) + adding > BOARD_OPEN_CARDS_MAX:
        raise AppError("board_full", HTTPStatus.CONFLICT)


async def _held(session: AsyncSession, viewer: UUID, board_id: UUID) -> int:
    """The board's open cards."""
    held = await session.scalar(
        select(func.count())
        .select_from(TaskPlacementRecord)
        .join(TaskRecord, TaskRecord.id == TaskPlacementRecord.task_id)
        .where(
            TaskPlacementRecord.user_id == viewer,
            TaskPlacementRecord.board_id == board_id,
            TaskRecord.status != TaskStatus.DONE.value,
        )
    )
    return held or 0


async def move_card(
    session: AsyncSession,
    principal: Principal,
    record: TaskRecord,
    move: tuple[CardSpot, TaskEdits],
    now: datetime,
) -> TaskStatus:
    """The person's card of the task put at the spot of one of their boards, from wherever it
    sat; the column's kind is the status, and the stopwatch follows as on a card's move."""
    spot, edits = move
    viewer = principal.user_id
    await owned_board(session, viewer, spot.board_id, lock=True)
    kind = await column_kind(session, spot.board_id, spot.column_id)
    before = TaskStatus(record.status)
    status = status_after_move(before, kind)
    placed = await session.get(TaskPlacementRecord, (viewer, record.id))
    source = None
    if placed is not None:
        columns = await board_columns(session, placed.board_id)
        source = spot_for(before, columns, placed.column_id).column_id
    change = TaskChange(status=UNSET if status is before else status)
    await edits.apply(session, viewer, record, Edit(change=change, moving=True))
    await place(session, viewer, record.id, spot, now)
    if source is None:
        await clock_rules.arrived(session, record, (spot.board_id, spot.column_id), now)
    else:
        await clock_rules.moved(session, record, (spot.board_id, source, spot.column_id), now)
    return status
