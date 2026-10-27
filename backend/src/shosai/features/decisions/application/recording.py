"""What the engine keeps of each decision, and the answers that serve a shadow (ADR 0069 DL-D7).

A consulted decision is one record: the rule's outcome when a fallback settled it, Jev's
judged outcome when it answered in time, or — when it answered after the caller moved on —
the rule's outcome it returned with Jev's late probabilities beside it (`late`). A shadow
version's record is its own: it reuses the active answer when it asks the same questions,
and never changes what the caller got. What followed a subject (`observe`) is buffered the
same way.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

import structlog

from shosai.core.ai.decisions import DecisionRequest
from shosai.core.kernel.homes import Home
from shosai.core.kernel.ids import new_id
from shosai.features.decisions.application.asking import Answered
from shosai.features.decisions.application.in_force import InForce
from shosai.features.decisions.application.judging import (
    Asked,
    Settled,
    decision_row,
    judge,
    record_of,
)
from shosai.features.decisions.contracts import (
    CardResolution,
    DecisionCall,
    Outcome,
    ToolsetsCalled,
)
from shosai.features.decisions.domain.outcomes import DecisionReason, DecisionSource, Subject
from shosai.features.decisions.domain.records import state_hash
from shosai.features.decisions.domain.state import state_json
from shosai.features.decisions.infrastructure.metrics import DecisionMetrics

log = structlog.stdlib.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class Prepared:
    """A decision's request to Jev and the keyed hash of its state."""

    request: DecisionRequest
    hash: bytes | None


def prepare(
    in_force: InForce, call: DecisionCall[Any, Any], key: bytes | None
) -> Prepared | DecisionReason:
    """The request a version asks, or `contract` when its facts cannot make one."""
    policy = in_force.policy
    try:
        state = policy.state(call.facts)
        request = DecisionRequest(state=state, questions=policy.questions(call.facts))
    except ValueError:
        log.warning("Запрос решения не собран", point=policy.point, version=policy.version)
        return DecisionReason.CONTRACT
    return Prepared(request, state_hash(state_json(state), key) if key else None)


class Terms(Protocol):
    """Whether Jev may read text now."""

    async def zero_retention(self) -> bool:
        """Every endpoint of the pinned model keeps nothing, as last checked."""
        ...


class Records(Protocol):
    """Where records and outcomes go, in batches."""

    def add_decision(self, home: Home, row: dict[str, Any]) -> None:
        """Buffer a decision's record."""
        ...

    def add_outcome(self, home: Home, row: dict[str, Any]) -> None:
        """Buffer what followed a decided subject."""
        ...


class Recorder:
    """Turns answers into outcomes and records, and buffers what followed a subject."""

    def __init__(
        self,
        records: Records,
        terms: Terms,
        metrics: DecisionMetrics,
        now: Callable[[], datetime],
        hash_key: bytes | None,
    ) -> None:
        self._records = records
        self.terms = terms
        self._metrics = metrics
        self._now = now
        self.hash_key = hash_key

    def fallback(
        self, in_force: InForce, asked: Asked, reason: DecisionReason, *, shadow: bool
    ) -> None:
        """A decision the rule settled because Jev could not be asked."""
        settled = Settled(asked.rule, reason, DecisionSource.FALLBACK, 0, {})
        self._write(in_force, asked, settled, shadow=shadow)

    def answered(
        self, active: InForce, shadow: InForce | None, asked: Asked, answered: Answered
    ) -> Outcome[Any]:
        """The outcome of an answer in time, recorded with its shadow's."""
        if answered.decision is None:
            reason = answered.failure or DecisionReason.PROVIDER_ERROR
            settled = Settled(asked.rule, reason, DecisionSource.FALLBACK, answered.latency_ms, {})
            self._write(active, asked, settled, shadow=False)
            return Outcome(
                asked.rule, reason, DecisionSource.FALLBACK, active.policy.key, asked.decision_id
            )
        judgement = judge(active, asked.facts, asked.rule, answered.decision)
        if judgement.unsafe:
            self._metrics.unsafe(active.policy.point)
            log.error("Политика смягчила исход правила", point=active.policy.point)
        elif active.policy.reads_consent and judgement.value != asked.rule:
            self._metrics.consented(active.policy.point)
        settled = Settled(
            judgement.value, DecisionReason.JUDGED, DecisionSource.JEV, answered.latency_ms,
            judgement.probabilities, answered.decision,
        )  # fmt: skip
        self._write(active, asked, settled, shadow=False)
        self._shadow_beside(shadow, asked, answered)
        return Outcome(
            judgement.value, DecisionReason.JUDGED, DecisionSource.JEV, active.policy.key,
            asked.decision_id,
        )  # fmt: skip

    def landed_late(
        self, active: InForce, shadow: InForce | None, asked: Asked, answered: Answered
    ) -> None:
        """An answer after the deadline: the rule's outcome stands, Jev's probabilities kept."""
        self._metrics.late(active.policy.point)
        chances: Mapping[str, float] = {}
        source = DecisionSource.FALLBACK
        if answered.decision is not None:
            chances = judge(active, asked.facts, asked.rule, answered.decision).probabilities
            source = DecisionSource.LATE
        settled = Settled(
            asked.rule, DecisionReason.DEADLINE, source, answered.latency_ms, chances,
            answered.decision,
        )  # fmt: skip
        self._write(active, asked, settled, shadow=False)
        self._shadow_beside(shadow, asked, answered)

    def shadowed(self, shadow: InForce, asked: Asked, answered: Answered) -> None:
        """A shadow's own answer: what it would have returned, acting on nothing."""
        if answered.decision is None:
            reason = answered.failure or DecisionReason.PROVIDER_ERROR
            settled = Settled(asked.rule, reason, DecisionSource.FALLBACK, answered.latency_ms, {})
        else:
            judgement = judge(shadow, asked.facts, asked.rule, answered.decision)
            settled = Settled(
                judgement.value, DecisionReason.JUDGED, DecisionSource.JEV, answered.latency_ms,
                judgement.probabilities, answered.decision,
            )  # fmt: skip
        self._write(shadow, asked, settled, shadow=True)

    def observed(self, point: str, home: Home, subject: Subject, seen: object) -> None:
        """Buffer what followed a decided subject; nothing to keep for an empty observation."""
        observation = observation_json(seen)
        if observation is None:
            return
        self._records.add_outcome(
            home,
            {"id": new_id(), "created_at": self._now(), "point": point,
             "subject_kind": subject.kind.value, "subject_id": subject.id, "part": subject.part,
             "observation": observation},
        )  # fmt: skip

    def _shadow_beside(self, shadow: InForce | None, asked: Asked, answered: Answered) -> None:
        """A shadow with the active version's questions, judged on the same answer."""
        if shadow is None:
            return
        twin = Asked(
            new_id(),
            asked.subject,
            asked.home,
            asked.language,
            asked.facts,
            asked.rule,
            asked.state_hash,
        )
        self.shadowed(shadow, twin, answered)

    def _write(self, in_force: InForce, asked: Asked, settled: Settled, *, shadow: bool) -> None:
        record = record_of(in_force, asked, settled, shadow=shadow, at=self._now())
        self._records.add_decision(asked.home, decision_row(record))


def observation_json(seen: object) -> dict[str, object] | None:
    """An observation in its point's closed form."""
    if isinstance(seen, ToolsetsCalled):
        return {"called": sorted(seen.names)}
    if isinstance(seen, CardResolution):
        return {"resolution": seen.value}
    return None
