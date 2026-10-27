"""What other slices may use of decisions: the port and its points (decisions plan §3.2).

A consumer names a point and hands its facts, the rule's own outcome and the person it
decides for; it gets an outcome that is never less careful than its rule, with the reason,
the source and — when the decision was recorded — its id; later it reports what it observed
of the subject (`observe`). Nothing here raises for a provider's failure: a decision that
cannot be made is the rule's outcome with its reason (ADR 0026, ADR 0069).

The points of this plan are `turn.route`, `action.friction` and `content.injection`; memory,
proactive, mail and hubs add theirs with their own steps.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Final, Protocol
from uuid import UUID

from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.keys import PortKey
from shosai.features.decisions.domain.outcomes import (
    DecisionReason,
    DecisionSource,
    Subject,
    SubjectKind,
)
from shosai.features.decisions.domain.policies.action_friction import CardFacts, CardFriction
from shosai.features.decisions.domain.policies.content_injection import (
    InjectionFinding,
    TextFacts,
)
from shosai.features.decisions.domain.policies.turn_route import ToolsetCandidate, TurnFacts
from shosai.features.decisions.domain.policies.voice_approval import VoiceConsent, VoiceFacts

__all__ = [
    "ACTION_FRICTION",
    "CONTENT_INJECTION",
    "DECISION_LAYER",
    "TURN_ROUTE",
    "VOICE_APPROVAL",
    "CardFacts",
    "CardFriction",
    "CardResolution",
    "DecisionCall",
    "DecisionPoint",
    "DecisionReason",
    "DecisionSource",
    "Decisions",
    "InjectionFinding",
    "Outcome",
    "Subject",
    "SubjectKind",
    "TextFacts",
    "ToolsetCandidate",
    "ToolsetsCalled",
    "TurnFacts",
    "VoiceConsent",
    "VoiceFacts",
]


@dataclass(frozen=True, slots=True)
class DecisionPoint[F, V, O]:
    """A decision point: its name, and by type its facts `F`, outcome `V`, observation `O`."""

    name: str


@dataclass(frozen=True, slots=True)
class DecisionCall[F, V]:
    """A decision asked for one person: who pays and whether they consent, what it is about,
    the facts, the rule's own outcome and the person's interface language."""

    scope: TenancyScope
    # Согласие на трансграничную передачу (nfr-14): без него в доме РФ Jev не спрашивают.
    cross_border_consent: bool
    subject: Subject
    facts: F
    rule: V
    language: str

    def __post_init__(self) -> None:
        if self.scope.user_id is None:
            message = "решение принимается для человека: в области нужен user_id"
            raise ValueError(message)


@dataclass(frozen=True, slots=True)
class Outcome[V]:
    """The decision: its value, why, from where, by which policy, and its record's id."""

    value: V
    reason: DecisionReason
    source: DecisionSource
    # `point@version`; None, когда политики не было или решать было нечего.
    policy: str | None = None
    # Id записи, под которым потребитель сообщает исход; None — решение не записано.
    decision_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class ToolsetsCalled:
    """What a routed run went on to call: the observation of `turn.route`."""

    names: frozenset[str]


class CardResolution(StrEnum):
    """How a card ended: the observation of `action.friction`."""

    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class Decisions(Protocol):
    """Decides at a point under its policy in force; never raises for the provider."""

    async def decide[F, V, O](
        self, point: DecisionPoint[F, V, O], call: DecisionCall[F, V]
    ) -> Outcome[V]:
        """The outcome, never less careful than `call.rule`."""
        ...

    async def judges[F, V, O](self, point: DecisionPoint[F, V, O]) -> bool:
        """Whether an active version decides at the point now, as last read (at most a minute
        old); without one every call gets its rule."""
        ...

    def observe[F, V, O](
        self, point: DecisionPoint[F, V, O], home: Home, subject: Subject, seen: O
    ) -> None:
        """Report what followed a decided subject, in the person's home; never blocks and
        never fails the caller."""
        ...


TURN_ROUTE: Final = DecisionPoint[TurnFacts, tuple[str, ...], ToolsetsCalled]("turn.route")
ACTION_FRICTION: Final = DecisionPoint[CardFacts, CardFriction, CardResolution]("action.friction")
# Наблюдать нечего: у человека нет действия, которое подтвердило бы или опровергло ответ.
CONTENT_INJECTION: Final = DecisionPoint[TextFacts, InjectionFinding, None]("content.injection")
# Согласие человека голосом (ограниченное исключение владельца): наблюдать нечего.
VOICE_APPROVAL: Final = DecisionPoint[VoiceFacts, VoiceConsent, None]("voice.approval")
DECISION_LAYER: Final = PortKey[Decisions]("decisions.layer")
