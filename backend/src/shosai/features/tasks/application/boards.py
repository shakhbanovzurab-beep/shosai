"""A person's boards: made from a template, renamed, laid out, chosen as incoming, deleted
(tasks plan §3.3, TK-D4, TK-D6, §3.14).

A board is made with its template's columns in the request's language; a person holds 50,
counted under their settings row's lock so two tabs cannot pass the limit. A layout only
reorders and renames what the board shows; anything else is `board_changed`. Deleting a
board removes its placements and the hand-made personal tasks on it, with their events and
their attachments given back to files; tasks of meetings and workspaces stay.
"""

from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from http import HTTPStatus
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.events.outbox import EventOutbox
from shosai.core.i18n.locales import normalize_language
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.ids import new_id
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import ACCOUNT_PROFILE_READER, Principal
from shosai.features.tasks.application.attachment_releases import AttachmentReleases
from shosai.features.tasks.application.board_access import incoming_board, owned_board, shown
from shosai.features.tasks.application.board_reads import BoardReads, summary_of
from shosai.features.tasks.application.board_views import BoardSummaryView, BoardsView
from shosai.features.tasks.application.landing import reconcile
from shosai.features.tasks.application.task_events import deleted_of
from shosai.features.tasks.domain.boards import (
    TEMPLATES,
    BoardIcon,
    BoardRuleError,
    BoardTemplate,
    LayoutColumn,
    ShownColumn,
    check_board_room,
    checked_board_name,
    checked_layout,
)
from shosai.features.tasks.domain.ranks import spaced_ranks
from shosai.features.tasks.domain.tasks import TaskSource
from shosai.features.tasks.domain.template_words import column_word
from shosai.features.tasks.infrastructure.board_records import (
    BoardColumnRecord,
    BoardRecord,
    TaskPlacementRecord,
    TaskSettingsRecord,
)
from shosai.features.tasks.infrastructure.task_records import TaskRecord

PLACED = TaskPlacementRecord
FULL_CODES = frozenset({"boards_full", "board_columns_full", "board_full", "last_column_of_kind"})


def board_failure(error: BoardRuleError) -> AppError:
    """A broken rule of boards as the API answers it: a limit or a stale layout is a conflict."""
    conflict = error.code in FULL_CODES or error.code == "board_changed"
    status = HTTPStatus.CONFLICT if conflict else HTTPStatus.UNPROCESSABLE_CONTENT
    return AppError(error.code, status)


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


class BoardWrites:
    """Makes, changes, lays out and deletes the person's boards."""

    def __init__(
        self,
        transactions: HomeTransactions,
        ports: PortDirectory,
        outbox: EventOutbox,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._ports = ports
        self._outbox = outbox
        self._clock = clock
        self._reads = BoardReads(transactions, ports, clock)
        self._releases = AttachmentReleases(transactions, ports)

    async def create(
        self, principal: Principal, made: tuple[str, BoardIcon, BoardTemplate], language: str | None
    ) -> BoardSummaryView:
        """A new board with its template's columns named in the request's language, else the
        profile's, else English."""
        raw_name, icon, template = made
        viewer, now = principal.user_id, self._clock()
        try:
            name = checked_board_name(raw_name)
            async with self._transactions.begin(principal.scope()) as session:
                if language is None:
                    profile = await self._ports.get(ACCOUNT_PROFILE_READER).profile(session, viewer)
                    language = None if profile is None else normalize_language(profile.language)
                await hold_settings(session, viewer)
                held = await session.scalar(
                    select(func.count())
                    .select_from(BoardRecord)
                    .where(BoardRecord.user_id == viewer)
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
                        id=new_id(), board_id=board.id, user_id=viewer,
                        title=column_word(word, language), kind=kind.value, position=position,
                    )
                    for position, (word, kind) in enumerate(TEMPLATES[template])
                )  # fmt: skip
                return summary_of(board, await incoming_board(session, viewer), 0)
        except BoardRuleError as error:
            raise board_failure(error) from error

    async def change(
        self, principal: Principal, board_id: UUID, change: tuple[str | None, BoardIcon | None]
    ) -> BoardSummaryView:
        """The board renamed or with another icon."""
        raw_name, icon = change
        viewer, now = principal.user_id, self._clock()
        try:
            name = None if raw_name is None else checked_board_name(raw_name)
        except BoardRuleError as error:
            raise board_failure(error) from error
        async with self._transactions.begin(principal.scope()) as session:
            board = await owned_board(session, viewer, board_id, lock=True)
            board.name = name or board.name
            board.icon = board.icon if icon is None else icon.value
            board.revision += 1
            board.updated_at = now
            await session.flush()
            listing = await self._reads.listing(session, viewer, now)
        return next(item for item in listing.items if item.id == board_id)

    async def delete(self, principal: Principal, board_id: UUID) -> None:
        """Delete the board and the hand-made personal tasks on it (TK-D6)."""
        viewer = principal.user_id
        async with self._transactions.begin(principal.scope()) as session:
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
                await self._outbox.add(session, deleted_of(task))
                await session.delete(task)
            await session.flush()
            await session.execute(delete(BoardRecord).where(BoardRecord.id == board_id))
        await self._releases.owner(principal.scope())

    async def set_incoming(self, principal: Principal, board_id: UUID | None) -> BoardsView:
        """Choose the board incoming work lands on, or none; what waits lands at once."""
        viewer, now = principal.user_id, self._clock()
        async with self._transactions.begin(principal.scope()) as session:
            if board_id is not None:
                await owned_board(session, viewer, board_id, lock=True)
            await hold_settings(session, viewer)
            await session.execute(
                update(TaskSettingsRecord)
                .where(TaskSettingsRecord.user_id == viewer)
                .values(incoming_board_id=board_id, updated_at=now)
            )
            if board_id is not None:
                readable = self._reads.readable(viewer)
                await reconcile(session, viewer, (board_id, True), (readable, now))
            return await self._reads.listing(session, viewer, now)

    async def lay_out(
        self, principal: Principal, board_id: UUID, layout: Sequence[LayoutColumn]
    ) -> None:
        """Reorder and rename the board's columns and cards, if they are the ones it shows."""
        viewer, now = principal.user_id, self._clock()
        async with self._transactions.begin(principal.scope()) as session:
            board = await owned_board(session, viewer, board_id, lock=True)
            placed = await self._placed(session, viewer, board_id, now)
            try:
                checked = checked_layout(
                    [
                        ShownColumn(column_id, tuple(cards[0]))
                        for column_id, cards in placed.items()
                    ],
                    layout,
                )
            except BoardRuleError as error:
                raise board_failure(error) from error
            await _apply_layout(session, checked, placed)
            board.revision += 1
            board.updated_at = now

    async def _placed(
        self, session: AsyncSession, viewer: UUID, board_id: UUID, now: datetime
    ) -> dict[UUID, tuple[list[UUID], list[UUID]]]:
        """Each column's shown cards and the rest, in their order."""
        columns = await session.scalars(
            select(BoardColumnRecord.id)
            .where(BoardColumnRecord.board_id == board_id)
            .order_by(BoardColumnRecord.position)
        )
        placed: dict[UUID, tuple[list[UUID], list[UUID]]] = {c: ([], []) for c in columns}
        visible = select(TaskRecord.id).where(self._reads.readable(viewer), shown(now))
        rows = await session.execute(
            select(PLACED.column_id, PLACED.task_id, PLACED.task_id.in_(visible))
            .where(PLACED.user_id == viewer, PLACED.board_id == board_id)
            .order_by(PLACED.rank)
        )
        for column_id, task_id, seen in rows:
            placed[column_id][0 if seen else 1].append(task_id)
        return placed


async def _apply_layout(
    session: AsyncSession,
    layout: Sequence[LayoutColumn],
    placed: dict[UUID, tuple[list[UUID], list[UUID]]],
) -> None:
    """Columns in the layout's order and titles, each one's cards spaced in the new order with
    the cards it does not show after them."""
    for position, column in enumerate(layout):
        await session.execute(
            update(BoardColumnRecord)
            .where(BoardColumnRecord.id == column.column_id)
            .values(position=position, title=column.title)
        )
        order = [*column.task_ids, *placed[column.column_id][1]]
        for task_id, rank in zip(order, spaced_ranks(len(order)), strict=True):
            await session.execute(
                update(PLACED)
                .where(PLACED.column_id == column.column_id, PLACED.task_id == task_id)
                .values(rank=rank)
            )
