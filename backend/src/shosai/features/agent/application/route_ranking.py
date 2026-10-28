"""A turn's toolsets ranked by a bound router beside the rule (decisions' `turn.route`, DL-D3).

The router is asked only when the rule cannot offer every toolset it fills the room with even
for reading — while every toolset's reads fit, its writes are one `load_toolset` away and
nothing is asked (DL-D3); since meetings' toolset the catalog no longer fits so. The person's
question, the start of the last answer and how many turns the thread had are read in one
statement of the run's transaction; the router then runs while the context is read, and the
first model request waits for it at most `ROUTE_WAIT`. A late, empty or absent answer leaves
the rule's order.
The toolsets the router brought in stay for the thread's next three turns, so the tools do
not flip from turn to turn; at the run's end the router hears which toolsets it called.
"""

import asyncio
from collections.abc import Sequence
from datetime import timedelta
from typing import Final, Protocol

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.ports.directory import PortDirectory
from shosai.features.agent.application.turn_task import TurnPayload
from shosai.features.agent.contracts import TURN_ROUTER, RouteRequest, TurnRouter
from shosai.features.agent.domain.operator import is_operator
from shosai.features.agent.domain.routing import CORE
from shosai.features.agent.domain.threads import MessageRole
from shosai.features.agent.infrastructure.run_records import AgentRunRecord
from shosai.features.agent.infrastructure.thread_records import AgentMessageRecord

# Дольше политики (350 мс) не ждём ни при каком роутере: ход важнее порядка инструментов.
ROUTE_WAIT: Final = timedelta(milliseconds=400)
ONE_MS: Final = timedelta(milliseconds=1)
# Начало прошлого ответа: роутеру хватает первых фраз.
PREVIOUS_CHARS: Final = 300
MESSAGE = AgentMessageRecord
log = structlog.stdlib.get_logger(__name__)

type Asked = asyncio.Task[tuple[str, ...] | None]


class Rankable(Protocol):
    """What ranking reads of a turn's offer and gives back to it."""

    def to_rank(self) -> tuple[str, ...]:
        """The toolsets that fill the room, when the rule left one of them out; else none."""
        ...

    def summary(self, name: str) -> str:
        """A toolset's tools and the first sentence of each one's description."""
        ...

    def kept(self) -> tuple[int, int]:
        """How many toolsets the rule keeps whole, and the tokens of segment 2 left."""
        ...

    def rank(self, ranked: Sequence[str]) -> None:
        """Fill the room with the ranked toolsets first."""
        ...


class RouteRanking:
    """Asks the bound router, waits for it within the turn's budget, tells it the run's end."""

    def __init__(self, ports: PortDirectory | None) -> None:
        self._ports = ports

    async def ask(
        self, session: AsyncSession, payload: TurnPayload, offer: Rankable, section: str
    ) -> Asked | None:
        """Start the router on the offer's candidates; None when there is nothing to rank."""
        routers = self._routers()
        names = offer.to_rank()
        if not routers or not names or is_operator(payload.user_id):
            return None
        question, previous, turn = await turn_texts(session, payload)
        forced, room = offer.kept()
        request = RouteRequest(
            candidates=tuple((name, offer.summary(name)) for name in names),
            forced=forced, room=room, question=question, previous=previous[:PREVIOUS_CHARS],
            section=section, turn=turn, language=payload.language, scope=payload.scope(),
            cross_border_consent=payload.cross_border_consent, run_id=payload.run_id,
        )  # fmt: skip
        return asyncio.create_task(routers[0].route(request))

    async def settle(self, offer: Rankable, asked: Asked | None) -> bool:
        """The router's ranking applied to the offer, waited for at most `ROUTE_WAIT`;
        whether the router was asked."""
        if asked is None:
            return False
        try:
            async with asyncio.timeout(ROUTE_WAIT.total_seconds()):
                ranked = await asked
        except TimeoutError:
            log.warning("Роутер наборов не успел: порядок правила", wait_ms=ROUTE_WAIT // ONE_MS)
            return True
        if ranked:
            offer.rank(ranked)
        return True

    def ended(self, payload: TurnPayload, called: Sequence[str]) -> None:
        """Tell the router which toolsets a run it ranked called."""
        for router in self._routers():
            router.ended(payload.home, payload.run_id, frozenset(called) - {CORE})

    def _routers(self) -> Sequence[TurnRouter]:
        return () if self._ports is None else self._ports.all(TURN_ROUTER)


async def turn_texts(session: AsyncSession, payload: TurnPayload) -> tuple[str, str, int]:
    """The person's question, the thread's last answer and its earlier turns, in one read."""
    question = (
        select(MESSAGE.text)
        .where(MESSAGE.id == payload.question_id, MESSAGE.thread_id == payload.thread_id)
        .scalar_subquery()
    )
    previous = (
        select(MESSAGE.text)
        .where(
            MESSAGE.thread_id == payload.thread_id,
            MESSAGE.role == MessageRole.ASSISTANT.value,
            MESSAGE.id != payload.reply_id,
        )
        .order_by(MESSAGE.created_at.desc())
        .limit(1)
        .scalar_subquery()
    )
    turns = (
        select(func.count())
        .select_from(AgentRunRecord)
        .where(
            AgentRunRecord.thread_id == payload.thread_id,
            AgentRunRecord.started_at < payload.started_at,
        )
        .scalar_subquery()
    )
    row = (await session.execute(select(question, previous, turns))).one()
    return row[0] or "", row[1] or "", int(row[2] or 0)
