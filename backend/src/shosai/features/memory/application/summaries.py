"""The summary of what Leo remembers: read, rewritten when stale, refreshed (memory step 7).

Reading never calls a model: the last good summary comes back with whether it is stale — the
facts changed since it was written, or the person's language did — and a stale one older than
an hour is queued for a rewrite, once per ten minutes, while the open goes on. The writer reads
the facts in the person's transaction, calls the model outside it, and keeps the summary only
when its shape holds; an empty memory writes an empty summary with no call. Memory off or a
Russian-home person without cross-border consent writes nothing.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Final
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.ai.calls import CallOrigin
from shosai.core.ai.errors import AiCallError
from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import ACCOUNT_PROFILE_READER, CONSENT_READER
from shosai.features.memory.application.summary_facts import (
    NO_FACTS_DIGEST,
    HeldFacts,
    SummaryFacts,
)
from shosai.features.memory.application.switch import memory_on
from shosai.features.memory.domain.summary import (
    EMPTY_SUMMARY,
    Section,
    Summary,
    SummaryRefusedError,
    checked,
)
from shosai.features.memory.infrastructure.embeddings import Payer
from shosai.features.memory.infrastructure.metrics import MemoryMetrics, SummaryTrigger
from shosai.features.memory.infrastructure.records import MemorySummaryRecord
from shosai.features.memory.infrastructure.summary_model import FALLBACK_LANGUAGE, SummaryModel

REWRITE_AFTER: Final = timedelta(hours=1)
QUEUED_FOR: Final = timedelta(minutes=10)
QUEUED_PREFIX: Final = "memory:summary_queued:"

type SummaryQueue = Callable[[TenancyScope, SummaryTrigger], Awaitable[None]]


class Written(StrEnum):
    """How a write ended; the metric's outcome."""

    WRITTEN = "written"
    EMPTY = "empty"
    REFUSED = "refused"
    FAILED = "failed"
    OFF = "off"
    NO_CONSENT = "no_consent"


@dataclass(frozen=True, slots=True)
class SummaryView:
    """The summary as the person reads it."""

    summary: Summary
    updated_at: datetime | None
    stale: bool


def summary_of(row: MemorySummaryRecord | None) -> Summary:
    """The kept summary, empty when there is none."""
    if row is None:
        return EMPTY_SUMMARY
    sections = tuple(Section(item["title"], item["body"]) for item in row.sections)
    return Summary(sections, tuple(row.suggestions))


class Summaries:
    """Reads and writes the person's summary."""

    def __init__(
        self,
        transactions: HomeTransactions,
        collaborators: tuple[SummaryFacts, SummaryModel, PortDirectory, MemoryMetrics],
        later: tuple[SummaryQueue, Redis],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._facts, self._model, self._ports, self._metrics = collaborators
        self._queue, self._valkey = later
        self._clock = clock

    async def view(self, scope: TenancyScope, *, rewrite: bool = True) -> SummaryView:
        """The kept summary and whether it is stale; a stale one is queued when it is due."""
        user_id = _person(scope)
        async with self._transactions.begin(scope, read_only=True) as session:
            row = await session.get(MemorySummaryRecord, user_id)
            digest = await self._facts.digest(session, user_id)
            language = await self._language(session, user_id)
        stale = _stale(row, digest, language)
        written = row.written_at if row is not None else None
        if rewrite and stale and (written is None or self._clock() - written > REWRITE_AFTER):
            await self.queue(scope, SummaryTrigger.OPEN)
        return SummaryView(summary_of(row) if digest else EMPTY_SUMMARY, written, stale)

    async def queue(self, scope: TenancyScope, trigger: SummaryTrigger) -> None:
        """Queue a rewrite unless one was queued in the last ten minutes."""
        key = f"{QUEUED_PREFIX}{_person(scope)}"
        if await self._valkey.set(key, "1", nx=True, ex=int(QUEUED_FOR.total_seconds())):
            await self._queue(scope, trigger)

    async def write(self, scope: TenancyScope, trigger: SummaryTrigger) -> Written:
        """Write the summary from the current facts; how it went, counted."""
        written = await self._write(scope, trigger)
        self._metrics.summary_written(trigger, written.value)
        return written

    async def _write(self, scope: TenancyScope, trigger: SummaryTrigger) -> Written:
        user_id = _person(scope)
        async with self._transactions.begin(scope, read_only=True) as session:
            if not await memory_on(session, user_id):
                return Written.OFF
            consent = scope.home is not Home.RU or await self._ports.get(
                CONSENT_READER
            ).cross_border(session, user_id)
            language = await self._language(session, user_id)
            held = await self._facts.held(session, user_id)
        if not held.facts:
            await self._keep(scope, (EMPTY_SUMMARY, language, NO_FACTS_DIGEST))
            return Written.EMPTY
        if not consent:
            return Written.NO_CONSENT
        origin = (
            CallOrigin.INTERACTIVE if trigger is SummaryTrigger.REFRESH else CallOrigin.BACKGROUND
        )
        summary = await self._written(Payer(scope, consent), held, language, origin)
        if isinstance(summary, Written):
            return summary
        await self._keep(scope, (summary, language, held.digest))
        return Written.WRITTEN

    async def _written(
        self, payer: Payer, held: HeldFacts, language: str, origin: CallOrigin
    ) -> Summary | Written:
        """The model's summary when its shape holds, or why there is none."""
        key = f"{payer.scope.user_id}:{held.digest}"
        try:
            answer = await self._model.summary(payer, held.text, language, (origin, key))
        except AiCallError:
            return Written.FAILED
        if answer is None:
            return Written.FAILED
        try:
            return checked(
                [(section.title, section.body) for section in answer.sections], answer.suggestions
            )
        except SummaryRefusedError:
            return Written.REFUSED

    async def _keep(self, scope: TenancyScope, kept: tuple[Summary, str, str]) -> None:
        summary, language, digest = kept
        values = {
            "sections": [{"title": s.title, "body": s.body} for s in summary.sections],
            "suggestions": list(summary.suggestions), "language": language,
            "facts_digest": digest, "written_at": self._clock(), "stale": False,
        }  # fmt: skip
        async with self._transactions.begin(scope) as session:
            await session.execute(
                insert(MemorySummaryRecord)
                .values(user_id=_person(scope), **values)
                .on_conflict_do_update(index_elements=[MemorySummaryRecord.user_id], set_=values)
            )

    async def _language(self, session: AsyncSession, user_id: UUID) -> str:
        profile = await self._ports.get(ACCOUNT_PROFILE_READER).profile(session, user_id)
        return profile.language if profile is not None else FALLBACK_LANGUAGE


def _person(scope: TenancyScope) -> UUID:
    if scope.user_id is None:
        message = "сводка памяти читается только от имени человека"
        raise ValueError(message)
    return scope.user_id


def _stale(row: MemorySummaryRecord | None, digest: str, language: str) -> bool:
    """Whether the facts or the language changed since the summary was written."""
    if row is None:
        return digest != NO_FACTS_DIGEST
    return row.stale or row.facts_digest != digest or row.language != language
