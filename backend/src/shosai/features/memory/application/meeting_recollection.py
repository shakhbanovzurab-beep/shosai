"""A meeting's recollection: what its notes tell about the owner (memory step 9, MM-D5).

After a meeting's first notes, off the meeting's path: the owner's switch and consent are read,
then the meeting as the owner may read it — its summary, key points and participants — and the
recollections model finds at most five statements; their vectors are taken in one call and the
rules decide and write under the owner's lock, every one a candidate labelled as the meeting's
speech, in the meeting's space, citing the finding or the summary it rests on. Nothing happens
for memory off, a Russian-home owner without cross-border consent, or a meeting the owner can
no longer read. A redelivered task neither writes nor pays twice: the write is keyed by the
meeting, and a key already written answers before the model is asked.
"""

from datetime import timedelta
from typing import Final
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.agent_tools.context import Taint
from shosai.core.ai.errors import AiCallError
from shosai.core.db.transactions import HomeTransactions
from shosai.core.idempotency.ledger import EffectKey, EffectLedger, EffectScope
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import ACCOUNT_PROFILE_READER, CONSENT_READER
from shosai.features.memory.application.admission_writer import AdmissionWriter, Found, Origin
from shosai.features.memory.application.switch import memory_on
from shosai.features.memory.domain.admission import Admission
from shosai.features.memory.domain.facts import MemorySource
from shosai.features.memory.infrastructure.embeddings import Embedder, Payer
from shosai.features.memory.infrastructure.metrics import MemoryMetrics
from shosai.features.memory.infrastructure.recollector import KeyPoint, MeetingRead, Recollector
from shosai.features.notes.contracts import (
    MEETING_FINDINGS,
    MEETING_READER,
    FindingKind,
    MeetingFacts,
    MeetingNotFoundError,
)
from shosai.features.workspaces.contracts import Viewer

RECOLLECTIONS: Final = EffectScope("memory.meeting_recollections", keep=timedelta(days=30))


class Recollected(BaseModel):
    """What a meeting's statements became."""

    outcomes: list[Admission]


class MeetingRecollection:
    """Recollects one meeting for its owner."""

    def __init__(
        self,
        transactions: HomeTransactions,
        models: tuple[Recollector, Embedder],
        collaborators: tuple[PortDirectory, EffectLedger, MemoryMetrics],
    ) -> None:
        self._transactions = transactions
        self._recollector, self._embedder = models
        self._ports, self._effects, self._metrics = collaborators
        self._writer = AdmissionWriter(self._embedder.model)

    async def recollect(self, home: Home, owner: UUID, meeting_id: UUID) -> list[Admission]:
        """What the meeting's statements became; nothing when the owner's memory takes none."""
        scope, effect = TenancyScope(home, owner), EffectKey(RECOLLECTIONS, str(meeting_id))
        read = await self._read(scope, meeting_id, effect)
        if isinstance(read, Recollected):
            return read.outcomes
        if read is None:
            return []
        meeting, seen, consent = read
        payer = Payer(scope, consent)
        try:
            found = await self._recollector.meeting(payer, seen, str(meeting_id))
            vectors = (
                await self._embedder.statements(
                    payer, [item.statement.text for item in found], f"recollect:{meeting_id}"
                )
                if found
                else []
            )
        except AiCallError:
            self._metrics.extracted(MemorySource.MEETING.value, ok=False)
            raise
        self._metrics.extracted(MemorySource.MEETING.value, ok=True)
        if not found:
            self._metrics.admitted(MemorySource.MEETING.value, [])
            return []
        origin = Origin(
            source=MemorySource.MEETING,
            org_id=meeting.org_id,
            refs={"meeting_id": str(meeting_id)},
            taint=Taint.EXTERNAL,
            said_at=meeting.ended_at or meeting.started_at,
        )
        items = [
            Found(item.statement, vector, item.refs)
            for item, vector in zip(found, vectors, strict=True)
        ]
        async with self._transactions.begin(scope) as session:

            async def write() -> Recollected:
                outcomes = await self._writer.write(session, owner, origin, items)
                return Recollected(outcomes=outcomes)

            done = await self._effects.once(session, effect, Recollected, write)
        if not done.replayed:
            self._metrics.admitted(MemorySource.MEETING.value, done.outcome.outcomes)
        return done.outcome.outcomes

    async def _read(
        self, scope: TenancyScope, meeting_id: UUID, effect: EffectKey
    ) -> tuple[MeetingFacts, MeetingRead, bool] | Recollected | None:
        """What a delivery before this one wrote, or the meeting as its owner reads it and
        their consent, when their memory may take it; the model is never paid twice."""
        owner = scope.user_id
        if owner is None:
            return None
        async with self._transactions.begin(scope, read_only=True) as session:
            earlier = await self._effects.recorded(session, effect, Recollected)
            if earlier is not None:
                return earlier
            if not await memory_on(session, owner):
                return None
            consent = scope.home is not Home.RU or await self._ports.get(
                CONSENT_READER
            ).cross_border(session, owner)
            if not consent:
                return None
            found = await self._ports.get(MEETING_READER).facts(
                session, Viewer(owner), [meeting_id]
            )
            meeting = found.get(meeting_id)
            if meeting is None or meeting.user_id != owner:
                return None
            seen = await self._seen(session, owner, meeting)
        return (meeting, seen, consent) if seen is not None else None

    async def _seen(
        self, session: AsyncSession, owner: UUID, meeting: MeetingFacts
    ) -> MeetingRead | None:
        """The summary, key points and participants' names; None without a summary or points."""
        try:
            findings = await self._ports.get(MEETING_FINDINGS).of(
                session, Viewer(owner), meeting.meeting_id
            )
        except MeetingNotFoundError:
            return None
        points = [
            KeyPoint(item.finding_id, item.text, item.quote)
            for item in findings
            if item.kind is FindingKind.KEY_POINT
        ]
        if not meeting.summary and not points:
            return None
        profile = await self._ports.get(ACCOUNT_PROFILE_READER).profile(session, owner)
        names = [person.name for person in meeting.participants if person.name]
        return MeetingRead(
            owner_name=profile.display_name if profile is not None else "",
            summary=meeting.summary or "",
            key_points=points,
            participants=names,
        )
