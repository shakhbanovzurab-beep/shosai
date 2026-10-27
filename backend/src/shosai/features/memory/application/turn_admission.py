"""A turn's admission: what the person said becomes facts or candidates (memory step 5, MM-D1).

After `agent.turn.completed`, off the turn's path, the person's own words of the turn — never
tool rounds, attachments or what Leo said — are read with the switch and the consent. The
extraction model finds at most three statements, their vectors are taken in one call, and the
rules decide and write under the person's lock. Nothing happens for memory off, a Russian-home
person without cross-border consent, the operator, or a run whose text tried to instruct Leo.
A redelivered task writes nothing twice: the write is keyed by the run.
"""

from datetime import timedelta
from typing import Final
from uuid import UUID

from pydantic import BaseModel
from redis.asyncio import Redis

from shosai.core.agent_tools.context import Taint
from shosai.core.db.transactions import HomeTransactions
from shosai.core.idempotency.ledger import EffectKey, EffectLedger, EffectScope
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.features.agent.contracts.memory import PERSON_WORDS, TurnWords
from shosai.features.identity.contracts import CONSENT_READER
from shosai.features.memory.application.admission_writer import (
    AdmissionWriter,
    Found,
    turn_origin,
)
from shosai.features.memory.application.switch import memory_on
from shosai.features.memory.domain.admission import Admission
from shosai.features.memory.infrastructure.embeddings import Embedder, Payer
from shosai.features.memory.infrastructure.extractor import Extractor
from shosai.features.memory.infrastructure.metrics import MemoryMetrics
from shosai.features.memory.infrastructure.presence import TTL_SECONDS, has_memories_key

ADMISSIONS: Final = EffectScope("memory.turn_admissions", keep=timedelta(days=7))
SOURCE: Final = "turn"


class Admitted(BaseModel):
    """What a turn's statements became."""

    outcomes: list[Admission]


class TurnAdmission:
    """Admits the statements of one turn."""

    def __init__(
        self,
        transactions: HomeTransactions,
        models: tuple[Extractor, Embedder],
        collaborators: tuple[PortDirectory, EffectLedger, Redis, MemoryMetrics],
    ) -> None:
        self._transactions = transactions
        self._extractor, self._embedder = models
        self._ports, self._effects, self._valkey, self._metrics = collaborators
        self._writer = AdmissionWriter(self._embedder.model)

    async def admit(self, home: Home, user_id: UUID, run_id: UUID) -> list[Admission]:
        """What the turn's statements became; nothing when the person's memory takes none."""
        scope = TenancyScope(home, user_id)
        words, consent = await self._read(scope, run_id)
        if words is None:
            return []
        payer = Payer(scope, consent)
        statements = await self._extractor.turn(payer, words, str(run_id))
        if not statements:
            self._metrics.admitted(SOURCE, [])
            return []
        vectors = await self._embedder.statements(
            payer, [statement.text for statement in statements], f"admit:{run_id}"
        )
        effect = EffectKey(ADMISSIONS, str(run_id))
        async with self._transactions.begin(scope) as session:

            async def write() -> Admitted:
                found = [
                    Found(statement, vector)
                    for statement, vector in zip(statements, vectors, strict=True)
                ]
                outcomes = await self._writer.write(session, user_id, turn_origin(words), found)
                return Admitted(outcomes=outcomes)

            done = await self._effects.once(session, effect, Admitted, write)
        outcomes = done.outcome.outcomes
        if not done.replayed:
            self._metrics.admitted(SOURCE, outcomes)
        if Admission.ACTIVE in outcomes:
            await self._valkey.set(has_memories_key(user_id), "1", ex=TTL_SECONDS)
        return outcomes

    async def _read(self, scope: TenancyScope, run_id: UUID) -> tuple[TurnWords | None, bool]:
        """The turn's words when the person's memory may take them, and their consent."""
        user_id = scope.user_id
        if user_id is None:
            return None, False
        async with self._transactions.begin(scope, read_only=True) as session:
            if not await memory_on(session, user_id):
                return None, False
            consent = scope.home is not Home.RU or await self._ports.get(
                CONSENT_READER
            ).cross_border(session, user_id)
            words = await self._ports.get(PERSON_WORDS).of_turn(session, user_id, run_id)
        if not consent or words is None or words.taint >= Taint.SUSPICIOUS:
            return None, consent
        return words, consent
