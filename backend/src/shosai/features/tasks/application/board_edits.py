"""A person's board changes inside the caller's transaction (tasks plan §3.3, TK-D4, TK-D6).

The cabinet's routes open a transaction for each; Leo's board tools run the same changes in
the transaction that also marks the action's item done, so a change is applied once. Every
change takes the person's settings or the board's lock first, as the cabinet's do.
"""

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import ColumnElement, delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.events.outbox import EventOutbox
from shosai.core.kernel.ids import new_id
from shosai.features.tasks.application.board_access import owned_board
from shosai.features.tasks.application.landing import reconcile
from shosai.features.tasks.application.task_events import deleted_of
from shosai.features.tasks.domain.boards import (
    TEMPLATES,
    BoardIcon,
    BoardTemplate,
    check_board_room,
    checked_board_columns,
    checked_board_name,
)
from shosai.features.tasks.domain.tasks import TaskSource, TaskStatus
from shosai.features.tasks.domain.template_words import column_word
from shosai.features.tasks.infrastructure.board_records import (
    BoardColumnRecord,
    BoardRecord,
    TaskPlacementRecord,
    TaskSettingsRecord,
)
from shosai.features.tasks.infrastructure.task_records import TaskRecord

PLACED = TaskPlacementRecord


async def hold_settings(session: AsyncSession, viewer: UUID) -> None:
    """The person's settings row, made if missing and locked: their board writes go in turn."""
    await session.execute(
        insert(TaskSettingsRecord).values(user_id=viewer).on_conflict_do_nothing()
    )
    await session.execute(
        select(TaskSettingsRecord.user_id)
        .where(TaskSettingsRecord.user_id == viewer)
        .with_for_update()
    )


async def board_made(
    session: AsyncSession,
    viewer: UUID,
    made: tuple[str, BoardIcon, BoardTemplate | Sequence[tuple[str, TaskStatus]]],
    at: tuple[str | None, datetime],
) -> BoardRecord:
    """A new board of the person with its template's columns in the language, or with its own
    columns; `BoardRuleError` for a name, a column or a count past the rules."""
    raw_name, icon, columns = made
    language, now = at
    name = checked_board_name(raw_name)
    chosen = (
        tuple((column_word(word, language), kind) for word, kind in TEMPLATES[columns])
        if isinstance(columns, BoardTemplate)
        else checked_board_columns(columns)
    )
    await hold_settings(session, viewer)
    held = await session.scalar(
        select(func.count()).select_from(BoardRecord).where(BoardRecord.user_id == viewer)
    )
    check_board_room(held or 0)
    board = BoardRecord(
        id=new_id(), user_id=viewer, name=name, icon=icon.value, revision=1,
        created_at=now, updated_at=now,
    )  # fmt: skip
    session.add(board)
    await session.flush()
    session.add_all(
        BoardColumnRecord(
            id=new_id(), board_id=board.id, user_id=viewer, title=title, kind=kind.value,
            position=position,
        )
        for position, (title, kind) in enumerate(chosen)
    )  # fmt: skip
    await session.flush()
    return board


async def board_changed(
    session: AsyncSession,
    viewer: UUID,
    board_id: UUID,
    change: tuple[str | None, BoardIcon | None, datetime],
) -> BoardRecord:
    """The board renamed or with another icon; `BoardRuleError` for a name past the rules."""
    raw_name, icon, now = change
    name = None if raw_name is None else checked_board_name(raw_name)
    board = await owned_board(session, viewer, board_id, lock=True)
    board.name = name or board.name
    board.icon = board.icon if icon is None else icon.value
    board.revision += 1
    board.updated_at = now
    await session.flush()
    return board


async def board_deleted(
    session: AsyncSession, outbox: EventOutbox, viewer: UUID, board_id: UUID
) -> None:
    """Delete the board with the hand-made personal tasks on it (TK-D6); the caller gives
    their attachments back to files after the commit."""
    await owned_board(session, viewer, board_id, lock=True)
    made_here = await session.scalars(
        select(TaskRecord)
        .join(PLACED, PLACED.task_id == TaskRecord.id)
        .where(
            PLACED.user_id == viewer, PLACED.board_id == board_id,
            TaskRecord.user_id == viewer, TaskRecord.org_id.is_(None),
            TaskRecord.source == TaskSource.MANUAL.value,
        )
        .with_for_update(of=TaskRecord)
    )  # fmt: skip
    for task in made_here.all():
        await outbox.add(session, deleted_of(task))
        await session.delete(task)
    await session.flush()
    await session.execute(delete(BoardRecord).where(BoardRecord.id == board_id))


async def incoming_chosen(
    session: AsyncSession,
    viewer: UUID,
    board_id: UUID | None,
    reading: tuple[ColumnElement[bool], datetime],
) -> None:
    """Choose the board incoming work lands on, or none; what waits lands at once."""
    readable, now = reading
    if board_id is not None:
        await owned_board(session, viewer, board_id, lock=True)
    await hold_settings(session, viewer)
    await session.execute(
        update(TaskSettingsRecord)
        .where(TaskSettingsRecord.user_id == viewer)
        .values(incoming_board_id=board_id, updated_at=now)
    )
    if board_id is not None:
        await reconcile(session, viewer, (board_id, True), (readable, now))
