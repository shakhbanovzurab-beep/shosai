"""A person's own stickers: listed with their boards and usage, changed, deleted (§3.15).

A sticker is its owner's; another person's or an unknown one is `sticker_not_found`. Its
states are changed as a full list: a kept id keeps its values, a new state comes without
one, a missing one goes with the values that used it — the database's cascade. A change
or a deletion raises the revision of every board the sticker is on.
"""

from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, datetime
from http import HTTPStatus
from uuid import UUID

from sqlalchemy import ColumnElement, and_, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.ids import new_id
from shosai.features.identity.contracts import Principal
from shosai.features.tasks.application.sticker_views import (
    OwnedStickerView,
    StickerView,
    UsageView,
    states_json,
    sticker_of,
)
from shosai.features.tasks.domain.stickers import (
    StateDraft,
    StickerKind,
    StickerRuleError,
    checked_name,
    checked_states,
)
from shosai.features.tasks.infrastructure.board_records import BoardRecord
from shosai.features.tasks.infrastructure.sticker_records import (
    BoardStickerRecord,
    StickerRecord,
    StickerStateRecord,
    TaskStickerValueRecord,
)

STICKERS = StickerRecord
STATES = StickerStateRecord


def sticker_failure(error: StickerRuleError) -> AppError:
    """A broken rule of stickers as the API answers it: a full set or owner is a conflict."""
    conflict = error.code.endswith("_full")
    return AppError(
        error.code, HTTPStatus.CONFLICT if conflict else HTTPStatus.UNPROCESSABLE_CONTENT
    )


def not_found() -> AppError:
    """No such sticker of the person."""
    return AppError("sticker_not_found", HTTPStatus.NOT_FOUND)


def own(viewer: UUID) -> ColumnElement[bool]:
    """The person's own stickers, not a workspace's."""
    return and_(STICKERS.user_id == viewer, STICKERS.org_id.is_(None))


async def owned_sticker(
    session: AsyncSession, viewer: UUID, sticker_id: UUID, *, lock: bool = False
) -> StickerView:
    """The person's sticker with its states; 404 otherwise."""
    statement = select(
        STICKERS.id, STICKERS.kind, STICKERS.name, STICKERS.user_id, STICKERS.org_id,
        states_json(),
    ).where(STICKERS.id == sticker_id, own(viewer))  # fmt: skip
    row = (await session.execute(statement.with_for_update() if lock else statement)).first()
    if row is None:
        raise not_found()
    sticker_id, kind, name, owner, org, states = row
    return sticker_of(
        {"id": sticker_id, "kind": kind, "name": name, "user_id": owner, "org_id": org,
         "states": states}
    )  # fmt: skip


async def write_states(
    session: AsyncSession, sticker: StickerView, states: list[StateDraft]
) -> None:
    """The sticker's states as the full list: kept by id, new without one, missing gone."""
    known = {state.id for state in sticker.states}
    if any(draft.state_id is not None and draft.state_id not in known for draft in states):
        raise AppError("state_not_found", HTTPStatus.NOT_FOUND)
    kept = {draft.state_id for draft in states if draft.state_id is not None}
    gone = [STATES.sticker_id == sticker.id]
    if kept:
        gone.append(STATES.id.not_in(kept))
    await session.execute(delete(STATES).where(*gone))
    for position, draft in enumerate(states):
        if draft.state_id is None:
            session.add(
                STATES(
                    id=new_id(), sticker_id=sticker.id, user_id=sticker.owner_user_id,
                    org_id=sticker.owner_org_id, name=draft.name, color=draft.color.value,
                    position=position,
                )
            )  # fmt: skip
            continue
        await session.execute(
            update(STATES)
            .where(STATES.id == draft.state_id)
            .values(name=draft.name, color=draft.color.value, position=position)
        )
    await session.flush()


async def touch_boards_of(session: AsyncSession, sticker_id: UUID, now: datetime) -> None:
    """Raise the revision of every board the sticker is on."""
    on = select(BoardStickerRecord.board_id).where(BoardStickerRecord.sticker_id == sticker_id)
    await session.execute(
        update(BoardRecord)
        .where(BoardRecord.id.in_(on))
        .values(revision=BoardRecord.revision + 1, updated_at=now)
    )


class Stickers:
    """The person's own stickers."""

    def __init__(
        self,
        transactions: HomeTransactions,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._clock = clock

    async def owned(self, principal: Principal) -> list[OwnedStickerView]:
        """The person's stickers with the boards they are on and their usage."""
        viewer = principal.user_id
        async with self._transactions.begin(principal.scope(), read_only=True) as session:
            rows = await session.execute(
                select(
                    STICKERS.id, STICKERS.kind, STICKERS.name, STICKERS.user_id, STICKERS.org_id,
                    states_json(),
                )
                .where(own(viewer))
                .order_by(STICKERS.created_at, STICKERS.id)
            )  # fmt: skip
            stickers = [
                sticker_of({"id": i, "kind": k, "name": n, "user_id": u, "org_id": o, "states": s})
                for i, k, n, u, o, s in rows
            ]
            boards = await self._boards(session, viewer)
            usage = await self._usage(session, viewer)
        return [
            OwnedStickerView(s, tuple(boards.get(s.id, ())), usage.get(s.id, UsageView(0)))
            for s in stickers
        ]

    async def change(
        self,
        principal: Principal,
        sticker_id: UUID,
        change: tuple[str | None, list[StateDraft] | None],
    ) -> StickerView:
        """The sticker renamed, or with its states as the full list."""
        raw_name, raw_states = change
        try:
            name = None if raw_name is None else checked_name(raw_name)
            states = None if raw_states is None else checked_states(raw_states)
        except StickerRuleError as error:
            raise sticker_failure(error) from error
        viewer = principal.user_id
        async with self._transactions.begin(principal.scope()) as session:
            sticker = await owned_sticker(session, viewer, sticker_id, lock=True)
            if name is not None:
                await session.execute(
                    update(STICKERS).where(STICKERS.id == sticker_id).values(name=name)
                )
            if states is not None and sticker.kind is StickerKind.STATES:
                await write_states(session, sticker, states)
            await touch_boards_of(session, sticker_id, self._clock())
            return await owned_sticker(session, viewer, sticker_id)

    async def delete(self, principal: Principal, sticker_id: UUID) -> None:
        """Delete the sticker: off every board, its values gone from every task."""
        async with self._transactions.begin(principal.scope()) as session:
            await owned_sticker(session, principal.user_id, sticker_id, lock=True)
            await touch_boards_of(session, sticker_id, self._clock())
            await session.execute(delete(STICKERS).where(STICKERS.id == sticker_id))

    async def _boards(
        self, session: AsyncSession, viewer: UUID
    ) -> dict[UUID, list[tuple[UUID, str]]]:
        rows = await session.execute(
            select(BoardStickerRecord.sticker_id, BoardRecord.id, BoardRecord.name)
            .join(BoardRecord, BoardRecord.id == BoardStickerRecord.board_id)
            .where(BoardRecord.user_id == viewer)
            .order_by(BoardRecord.created_at)
        )
        found: defaultdict[UUID, list[tuple[UUID, str]]] = defaultdict(list)
        for sticker_id, board_id, name in rows:
            found[sticker_id].append((board_id, name))
        return found

    async def _usage(self, session: AsyncSession, viewer: UUID) -> dict[UUID, UsageView]:
        values = TaskStickerValueRecord
        rows = await session.execute(
            select(values.sticker_id, values.state_id, func.count())
            .join(STICKERS, STICKERS.id == values.sticker_id)
            .where(own(viewer))
            .group_by(values.sticker_id, values.state_id)
        )
        tasks: defaultdict[UUID, int] = defaultdict(int)
        states: defaultdict[UUID, dict[UUID, int]] = defaultdict(dict)
        for sticker_id, state_id, count in rows:
            tasks[sticker_id] += count
            if state_id is not None:
                states[sticker_id][state_id] = count
        return {sid: UsageView(count, states.get(sid, {})) for sid, count in tasks.items()}
