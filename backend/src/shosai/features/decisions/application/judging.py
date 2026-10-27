"""From Jev's answer to an outcome and a record (Leo §6.2 steps 5 to 7, ADR 0069).

The answer is read through the version's cuts into verdicts, the policy turns them into its
outcome, and the final outcome is the more careful of the policy's and the rule's. Should a
policy ever return one less careful than the rule, the rule's stands and the breach is
reported: monotonic safety is checked, not assumed. The one bounded exception is a policy
that reads a person's consent (`reads_consent`, voice.approval): its consent is the outcome,
and the engine returns it only from an active version's answer in time.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from shosai.core.ai.decisions import Decision
from shosai.core.kernel.homes import Home
from shosai.features.decisions.application.in_force import InForce
from shosai.features.decisions.domain.outcomes import DecisionReason, DecisionSource, Subject
from shosai.features.decisions.domain.records import DecisionRecord
from shosai.features.decisions.domain.verdicts import read


@dataclass(frozen=True, slots=True)
class Judgement:
    """The final outcome, the probabilities it rests on, and whether the policy broke the rule."""

    value: Any
    probabilities: Mapping[str, float]
    unsafe: bool


def judge(in_force: InForce, facts: object, rule: object, decision: Decision) -> Judgement:
    """The outcome of an answer under a version in force; never less careful than `rule`."""
    policy = in_force.policy
    verdicts, chances = read(decision.answers, policy.signals(facts), in_force.cuts)
    judged = policy.outcome(facts, verdicts, chances)
    final = policy.careful(rule, judged)
    if policy.less_careful(final, rule) and not policy.reads_consent:
        return Judgement(rule, chances, unsafe=True)
    return Judgement(final, chances, unsafe=False)


@dataclass(frozen=True, slots=True)
class Asked:
    """What a decision was about and asked as: its id, subject, home, language, the facts,
    the rule's outcome and the state's hash."""

    decision_id: UUID
    subject: Subject
    home: Home
    language: str
    facts: object
    rule: object
    state_hash: bytes | None


@dataclass(frozen=True, slots=True)
class Settled:
    """How a decision ended: the outcome returned, why, from where, after how long."""

    value: object
    reason: DecisionReason
    source: DecisionSource
    latency_ms: int
    probabilities: Mapping[str, float]
    decision: Decision | None = None


def record_of(
    in_force: InForce, asked: Asked, settled: Settled, *, shadow: bool, at: datetime
) -> DecisionRecord:
    """The record of a decision: ids, numbers and codes."""
    policy = in_force.policy
    answer = settled.decision
    return DecisionRecord(
        id=asked.decision_id,
        created_at=at,
        point=policy.point,
        version=policy.version,
        revision=in_force.revision,
        shadow=shadow,
        subject=asked.subject,
        language=asked.language,
        facts=policy.facts(asked.facts),
        rule_outcome=policy.code(asked.rule),
        outcome=policy.code(settled.value),
        reason=settled.reason,
        source=settled.source,
        latency_ms=settled.latency_ms,
        state_hash=asked.state_hash,
        probabilities=dict(settled.probabilities),
        jev_snapshot=answer.snapshot if answer else None,
        jev_request_id=answer.decision_id if answer else None,
    )


def decision_row(record: DecisionRecord) -> dict[str, object]:
    """A record as the table's columns."""
    return {
        "id": record.id, "created_at": record.created_at, "point": record.point,
        "version": record.version, "revision": record.revision, "shadow": record.shadow,
        "subject_kind": record.subject.kind.value, "subject_id": record.subject.id,
        "part": record.subject.part, "language": record.language, "facts": dict(record.facts),
        "state_hash": record.state_hash, "probabilities": dict(record.probabilities),
        "rule_outcome": record.rule_outcome, "outcome": record.outcome,
        "reason": record.reason.value, "source": record.source.value,
        "latency_ms": record.latency_ms, "jev_snapshot": record.jev_snapshot,
        "jev_request_id": record.jev_request_id,
    }  # fmt: skip
