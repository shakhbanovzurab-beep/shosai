"""Stickers on a board: placed, shown or hidden, removed (tasks plan §3.15).

A board places its owner's stickers — an existing one, or a new one made with it — after
the others, 20 at most, its owner holding 100; a sticker already there stays as it is. A
system sticker is shown or hidden on the board's row, the stopwatch also keeps its
automations; a custom one on its place. A removed sticker's values stay with the tasks and
come back when it is placed again. Every write takes the board's lock and raises its
revision.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from http import HTTPStatus
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.ids import new_id
from shosai.features.identity.contracts import Principal
from shosai.features.tasks.application.board_access import owned_board
from shosai.features.tasks.application.scoping import invalid
from shosai.features.tasks.application.sticker_views import BoardStickerView, system_stickers
from shosai.features.tasks.application.stickers import (
    own,
    owned_sticker,
    sticker_failure,
    write_states,
)
from shosai.features.tasks.domain.board_fields import StopwatchAutomations, SystemSticker
from shosai.features.tasks.domain.stickers import (
    BOARD_STICKERS_MAX,
    STICKERS_MAX,
    StateDraft,
    StickerKind,
    StickerRule,
    StickerRuleError,
    checked_name,
    checked_states,
)
from shosai.features.tasks.infrastructure.board_records import BoardRecord
from shosai.features.tasks.infrastructure.sticker_records import BoardStickerRecord, StickerRecord

PLACED = BoardStickerRecord


@dataclass(frozen=True, slots=True)
class NewSticker:
    """A sticker made as it is placed."""

    kind: StickerKind
    name: str
    states: tuple[StateDraft, ...] = ()


def not_on_board() -> AppError:
    """The sticker is not on this board."""
    return AppError("sticker_not_on_board", HTTPStatus.NOT_FOUND)


class BoardStickers:
    """Places, shows and removes the stickers of a person's boards."""

    def __init__(
        self,
        transactions: HomeTransactions,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._clock = clock

    async def place(
        self, principal: Principal, board_id: UUID, placed: UUID | NewSticker
    ) -> BoardStickerView:
        """The sticker on the board, shown, after the others."""
        viewer = principal.user_id
        try:
            async with self._transactions.begin(principal.scope()) as session:
                board = await owned_board(session, viewer, board_id, lock=True)
                if isinstance(placed, NewSticker):
                    sticker_id = await _made(session, viewer, placed)
                else:
                    sticker_id = (await owned_sticker(session, viewer, placed)).id
                spot = await _spot(session, board_id, sticker_id)
                if spot is None:
                    held = await session.scalar(
                        select(func.count()).select_from(PLACED).where(PLACED.board_id == board_id)
                    )
                    if (held or 0) >= BOARD_STICKERS_MAX:
                        raise StickerRuleError(StickerRule.BOARD_STICKERS_FULL)
                    spot = PLACED(
                        id=new_id(),
                        board_id=board_id, sticker_id=sticker_id, user_id=viewer, visible=True,
                        position=held or 0,
                    )  # fmt: skip
                    session.add(spot)
                _touched(board, self._clock())
                sticker = await owned_sticker(session, viewer, sticker_id)
                return BoardStickerView(sticker, spot.visible)
        except StickerRuleError as error:
            raise sticker_failure(error) from error

    async def change(
        self,
        principal: Principal,
        board_id: UUID,
        sticker: tuple[str, bool | None, StopwatchAutomations | None],
    ) -> BoardStickerView:
        """The sticker shown or hidden on the board's cards; the stopwatch's automations."""
        raw_id, visible, automations = sticker
        system = SystemSticker(raw_id) if raw_id in set(SystemSticker) else None
        if automations is not None and system is not SystemSticker.STOPWATCH:
            raise invalid()
        viewer = principal.user_id
        async with self._transactions.begin(principal.scope()) as session:
            board = await owned_board(session, viewer, board_id, lock=True)
            if system is not None:
                if visible is not None:
                    board.system_stickers = {**board.system_stickers, system.value: visible}
                if automations is not None:
                    board.stopwatch_automations = {
                        "start_on_arrival": automations.start_on_arrival,
                        "restart_on_move": automations.restart_on_move,
                        "stop_on_done": automations.stop_on_done,
                    }
                _touched(board, self._clock())
                shown = system_stickers(board.system_stickers, board.stopwatch_automations)
                return next(view for view in shown if view.sticker is system)
            spot = await _spot(session, board_id, _uuid(raw_id))
            if spot is None:
                raise not_on_board()
            if visible is not None:
                spot.visible = visible
            _touched(board, self._clock())
            return BoardStickerView(
                await owned_sticker(session, viewer, spot.sticker_id), spot.visible
            )

    async def remove(self, principal: Principal, board_id: UUID, raw_id: str) -> None:
        """Take the sticker off the board; its values stay with the tasks."""
        if raw_id in set(SystemSticker):
            raise AppError("system_sticker", HTTPStatus.CONFLICT)
        async with self._transactions.begin(principal.scope()) as session:
            board = await owned_board(session, principal.user_id, board_id, lock=True)
            gone = await session.scalar(
                delete(PLACED)
                .where(PLACED.board_id == board_id, PLACED.sticker_id == _uuid(raw_id))
                .returning(PLACED.position)
            )
            if gone is None:
                raise not_on_board()
            await session.execute(
                update(PLACED)
                .where(PLACED.board_id == board_id, PLACED.position > gone)
                .values(position=PLACED.position - 1)
            )
            _touched(board, self._clock())


async def _made(session: AsyncSession, viewer: UUID, new: NewSticker) -> UUID:
    """A new sticker of the person, within their 100."""
    name = checked_name(new.name)
    states = checked_states(list(new.states)) if new.kind is StickerKind.STATES else []
    held = await session.scalar(select(func.count()).select_from(StickerRecord).where(own(viewer)))
    if (held or 0) >= STICKERS_MAX:
        raise StickerRuleError(StickerRule.STICKERS_FULL)
    sticker = StickerRecord(id=new_id(), user_id=viewer, kind=new.kind.value, name=name)
    session.add(sticker)
    await session.flush()
    if states:
        made = await owned_sticker(session, viewer, sticker.id)
        await write_states(session, made, states)
    return sticker.id


async def _spot(
    session: AsyncSession, board_id: UUID, sticker_id: UUID
) -> BoardStickerRecord | None:
    """Where the sticker sits on the board, if it does."""
    found: BoardStickerRecord | None = await session.scalar(
        select(PLACED).where(PLACED.board_id == board_id, PLACED.sticker_id == sticker_id)
    )
    return found


def _uuid(raw: str) -> UUID:
    """A sticker's id from the path; anything else is no sticker of the board."""
    try:
        return UUID(raw)
    except ValueError as error:
        raise not_on_board() from error


def _touched(board: BoardRecord, now: datetime) -> None:
    board.revision += 1
    board.updated_at = now
