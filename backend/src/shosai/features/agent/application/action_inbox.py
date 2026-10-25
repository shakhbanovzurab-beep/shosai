"""The person's cards outside a conversation: the inbox and one card (agent step 9b; Leo §13.2).

The inbox lists the person's actions newest first, by cursor, optionally of one public state;
"Needs you" reads the cards still waiting — `proposed` and within their hour, so a card the
sweep has not expired yet is not offered. A card is read by its id. Both read as the person,
so row-level security and the person's id keep everyone else's cards out, and every card is
rendered in the person's language.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Final
from uuid import UUID

from pydantic import BaseModel, JsonValue
from sqlalchemy import Select, select

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.errors import AppError
from shosai.core.pagination.cursor import CursorCodec
from shosai.core.pagination.keyset import Keyset
from shosai.core.pagination.page import Page, PageRequest, page_of
from shosai.features.agent.application.action_cards import ActionCards
from shosai.features.agent.domain.actions import PublicStatus, internal_statuses
from shosai.features.agent.infrastructure.run_records import AgentActionRecord
from shosai.features.identity.contracts import Principal

ACTION = AgentActionRecord
NEWEST: Final = Keyset((ACTION.created_at.expression, ACTION.id.expression), descending=True)


class ActionPosition(BaseModel):
    """Where a page of cards ended."""

    created_at: datetime
    id: UUID


CODEC: Final = CursorCodec("agent.actions", ActionPosition)


def not_found() -> AppError:
    """No card of the person by that id."""
    return AppError("action_not_found", HTTPStatus.NOT_FOUND)


class ActionInbox:
    """Reads the person's cards."""

    def __init__(
        self,
        transactions: HomeTransactions,
        cards: ActionCards,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._cards = cards
        self._clock = clock

    async def page(
        self, principal: Principal, status: PublicStatus | None, request: PageRequest
    ) -> Page[dict[str, JsonValue]]:
        """A page of the person's cards, newest first, of one state or of all."""
        position = None if request.cursor is None else CODEC.decode(request.cursor)
        after = None if position is None else (position.created_at, position.id)
        statement = self._of(principal, status)
        async with self._transactions.begin(principal.scope(), read_only=True) as session:
            rows = list(await session.scalars(NEWEST.page(statement, after, request.limit)))
            cards = await self._cards.cards(session, rows[: request.limit])
        page = page_of(rows, request, CODEC, lambda row: row.id, position_of)
        return Page(items=cards, next_cursor=page.next_cursor)

    async def card(self, principal: Principal, action_id: UUID) -> dict[str, JsonValue]:
        """One of the person's cards."""
        async with self._transactions.begin(principal.scope(), read_only=True) as session:
            record = await session.scalar(
                select(ACTION).where(ACTION.id == action_id, ACTION.user_id == principal.user_id)
            )
            if record is None:
                raise not_found()
            (card,) = await self._cards.cards(session, [record])
        return card

    async def decided(
        self, principal: Principal, record: AgentActionRecord
    ) -> dict[str, JsonValue]:
        """The card of an action the person just decided, as it stands."""
        async with self._transactions.begin(principal.scope(), read_only=True) as session:
            (card,) = await self._cards.cards(session, [record])
        return card

    def _of(self, principal: Principal, status: PublicStatus | None) -> Select[ACTION]:
        statement = select(ACTION).where(ACTION.user_id == principal.user_id)
        if status is None:
            return statement
        statement = statement.where(ACTION.status.in_(internal_statuses(status)))
        if status is PublicStatus.PROPOSED:
            statement = statement.where(ACTION.expires_at > self._clock())
        return statement


def position_of(record: AgentActionRecord) -> ActionPosition:
    """The cursor's position after a card."""
    return ActionPosition(created_at=record.created_at, id=record.id)
