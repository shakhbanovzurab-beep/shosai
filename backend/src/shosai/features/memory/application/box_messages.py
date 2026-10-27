"""A message in the summary's "Ask or update" box (memory step 7, ADR 0071 MM-D3).

Memory's own call, not a Leo turn: the model reads the message with the person's facts under
short references and answers a question from them, or names what to remember, correct and
forget; only the references it was given count. The changes are applied once per
`Idempotency-Key` — a retry answers the first result — and each comes back with its fact, so
the dialog shows it and can undo it. The summary is rewritten afterwards in the background.
Refusals: memory off is 409 `memory_off`, a Russian-home person without cross-border consent
403 `consent_required`, more than 30 messages an hour 429, the model unreachable 503.
"""

from collections.abc import Callable, Collection
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from typing import Final
from uuid import UUID

from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.ai.errors import AiCallError
from shosai.core.db.transactions import HomeTransactions
from shosai.core.idempotency.ledger import (
    EffectKey,
    EffectLedger,
    EffectScope,
    account_key,
    fingerprint_of,
)
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.homes import Home
from shosai.core.kv.rate_limits import RateLimit, RateLimiter
from shosai.core.ports.directory import PortDirectory
from shosai.core.web.rate_limit import RateLimitedError
from shosai.features.identity.contracts import CONSENT_READER, Principal
from shosai.features.memory.application.box_changes import BoxChanges, Change, ChangeKind
from shosai.features.memory.application.fact_list import FactLists, FactView, view_of
from shosai.features.memory.application.fact_rows import FACT
from shosai.features.memory.application.summaries import Summaries, SummaryView
from shosai.features.memory.application.summary_facts import HeldFacts, SummaryFacts
from shosai.features.memory.application.switch import memory_on
from shosai.features.memory.domain.box import BoxReply, NewStatement, plan
from shosai.features.memory.domain.facts import FactKind
from shosai.features.memory.infrastructure.embeddings import Payer
from shosai.features.memory.infrastructure.metrics import SummaryTrigger
from shosai.features.memory.infrastructure.presence import TTL_SECONDS, has_memories_key
from shosai.features.memory.infrastructure.summary_model import SummaryModel
from shosai.features.memory.infrastructure.summary_prompts import BoxAnswer

# Ключ клиента живёт сутки: повтор сообщения позже — уже новое сообщение.
MESSAGES: Final = EffectScope("memory.box_messages", keep=timedelta(days=1))
BOX_LIMIT: Final = RateLimit("memory.box", 30, timedelta(hours=1), 30)


class BoxPrint(BaseModel):
    """What a message asked, to tell a retry from a reused key."""

    message: str


class BoxDone(BaseModel):
    """What a message did: its answer and the changes, by fact id."""

    answer: str | None
    changes: list[tuple[ChangeKind, UUID, UUID | None]]


@dataclass(frozen=True, slots=True)
class BoxResult:
    """The answer, each change with the fact as it is now, and the summary."""

    answer: str | None
    changes: tuple[tuple[ChangeKind, FactView, UUID | None], ...]
    summary: SummaryView


def reply_of(answer: BoxAnswer) -> BoxReply:
    """The model's answer as the box's rules read it."""
    return BoxReply(
        answer=answer.answer,
        remember=[NewStatement(item.statement, FactKind(item.kind)) for item in answer.remember],
        update=[(item.fact, item.statement) for item in answer.update],
        forget=list(answer.forget),
    )


class BoxMessages:
    """Answers and applies the person's messages about their memory."""

    def __init__(
        self,
        transactions: HomeTransactions,
        reading: tuple[FactLists, SummaryFacts, SummaryModel, Summaries],
        guards: tuple[EffectLedger, RateLimiter, Redis, PortDirectory],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._lists, self._facts, self._model, self._summaries = reading
        self._effects, self._limiter, self._valkey, self._ports = guards
        self._changes = BoxChanges(self._lists, clock)

    async def handle(self, principal: Principal, message: str, client_key: str) -> BoxResult:
        """The message's answer and changes, once per key."""
        user_id, scope = principal.user_id, principal.scope()
        effect = EffectKey(
            MESSAGES, account_key(user_id, client_key), fingerprint_of(BoxPrint(message=message))
        )
        found = await self._first_read(principal, effect)
        if isinstance(found, BoxDone):
            return await self._result(principal, found)
        held, consent = found
        decision = await self._limiter.check(BOX_LIMIT, str(user_id))
        if not decision.allowed:
            raise RateLimitedError(decision.retry_after)
        try:
            answer = await self._model.box(
                Payer(scope, consent), held.text, message, f"{user_id}:{client_key}"
            )
        except AiCallError:
            answer = None
        if answer is None:
            raise AppError("memory_unavailable", HTTPStatus.SERVICE_UNAVAILABLE)
        planned = plan(reply_of(answer), held.refs)
        async with self._transactions.begin(scope) as session:

            async def apply() -> BoxDone:
                made = await self._changes.apply(session, user_id, planned)
                return BoxDone(answer=planned.answer, changes=[_row(change) for change in made])

            done = (await self._effects.once(session, effect, BoxDone, apply)).outcome
        await self._after(principal, done)
        return await self._result(principal, done)

    async def _first_read(
        self, principal: Principal, effect: EffectKey
    ) -> BoxDone | tuple[HeldFacts, bool]:
        """What an earlier attempt with the key did, or what this one reads."""
        async with self._transactions.begin(principal.scope(), read_only=True) as session:
            earlier = await self._effects.recorded(session, effect, BoxDone)
            if earlier is not None:
                return earlier
            return await self._read(session, principal)

    async def _read(self, session: AsyncSession, principal: Principal) -> tuple[HeldFacts, bool]:
        """The facts the model reads and the person's consent; refused when it may not."""
        user_id = principal.user_id
        if not await memory_on(session, user_id):
            raise AppError("memory_off", HTTPStatus.CONFLICT)
        consent = principal.home is not Home.RU or await self._ports.get(
            CONSENT_READER
        ).cross_border(session, user_id)
        if not consent:
            raise AppError("consent_required", HTTPStatus.FORBIDDEN)
        return await self._facts.held(session, user_id), consent

    async def _after(self, principal: Principal, done: BoxDone) -> None:
        """A remembered fact sets the "has memories" bit; any change queues the summary."""
        kinds = {kind for kind, _, _ in done.changes}
        if ChangeKind.REMEMBERED in kinds:
            await self._valkey.set(has_memories_key(principal.user_id), "1", ex=TTL_SECONDS)
        if kinds:
            await self._summaries.queue(principal.scope(), SummaryTrigger.BOX)

    async def _result(self, principal: Principal, done: BoxDone) -> BoxResult:
        views = await self._views(principal, [fact_id for _, fact_id, _ in done.changes])
        changes = tuple(
            (kind, views[fact_id], replaced)
            for kind, fact_id, replaced in done.changes
            if fact_id in views
        )
        summary = await self._summaries.view(principal.scope(), rewrite=False)
        return BoxResult(done.answer, changes, summary)

    async def _views(
        self, principal: Principal, fact_ids: Collection[UUID]
    ) -> dict[UUID, FactView]:
        if not fact_ids:
            return {}
        user_id = principal.user_id
        async with self._transactions.begin(principal.scope(), read_only=True) as session:
            rows = list(
                await session.scalars(
                    select(FACT).where(FACT.id.in_(tuple(fact_ids)), FACT.user_id == user_id)
                )
            )
            titles = await self._lists.titles(session, user_id, rows)
        return {row.id: view_of(row, titles.get) for row in rows}


def _row(change: Change) -> tuple[ChangeKind, UUID, UUID | None]:
    return change.change, change.fact_id, change.replaced_id
