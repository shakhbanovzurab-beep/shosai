"""The agent's ports this slice binds (agent plan §3.2, ADR 0068 AG-D7, ADR 0069).

`FrictionJudge`: a card the agent's rule left standard is asked as `action.friction`; the card
takes the outcome only when it is stronger than the rule's, and each card's end is reported
as what followed the decision about it. A warning or a refusal from the rule is never asked:
nothing could make it lighter.

`TurnRouter`: the toolsets that fill a turn's room are asked as `turn.route`; the ranking of
an active version goes back to the agent, a shadow's is only recorded. A routed run's called
toolsets are reported as what followed.

`InjectionJudge`: each piece of untrusted text entering a run is asked as `content.injection`,
its subject the run and the piece's number; only an active version's finding reaches the run.

`VoiceApprovalJudge`: the person's reply to a card read back is asked as `voice.approval`,
its subject the action; the owner's bounded exception — approved only when an active
version's answer in time found a clear yes, never from a shadow, a late answer or a fallback.
"""

from typing import Final
from uuid import UUID

from shosai.core.kernel.homes import Home
from shosai.features.agent.contracts import (
    CardEnd,
    Friction,
    FrictionFacts,
    InjectionPiece,
    RouteRequest,
)
from shosai.features.agent.contracts.voice import VoiceApprovalFacts
from shosai.features.decisions.contracts import (
    ACTION_FRICTION,
    CONTENT_INJECTION,
    TURN_ROUTE,
    VOICE_APPROVAL,
    CardFacts,
    CardFriction,
    CardResolution,
    DecisionCall,
    Decisions,
    DecisionSource,
    InjectionFinding,
    Subject,
    SubjectKind,
    TextFacts,
    ToolsetsCalled,
    TurnFacts,
    VoiceConsent,
    VoiceFacts,
)
from shosai.features.decisions.domain.policies.turn_route import TOOLSET_NAME, ToolsetCandidate

AS_FRICTION: Final = {
    CardFriction.STANDARD: Friction.STANDARD,
    CardFriction.WARNING: Friction.WARNING,
}


class AgentFrictionJudge:
    """The agent's `FrictionJudge` over `action.friction`."""

    def __init__(self, decisions: Decisions) -> None:
        self._decisions = decisions

    async def judge(self, facts: FrictionFacts) -> Friction | None:
        """A stronger friction than the rule's, or None."""
        if facts.rule is not Friction.STANDARD:
            return None
        card = CardFacts(
            tool=facts.tool, toolset=facts.toolset, reversibility=facts.reversibility,
            items=facts.items, other_space=facts.other_space, rounds=facts.rounds,
            request=facts.question, card=facts.card,
        )  # fmt: skip
        call = DecisionCall(
            facts.scope, facts.cross_border_consent, Subject(SubjectKind.ACTION, facts.action_id),
            card, CardFriction.STANDARD, facts.language,
        )  # fmt: skip
        outcome = await self._decisions.decide(ACTION_FRICTION, call)
        return AS_FRICTION[outcome.value] if outcome.value > CardFriction.STANDARD else None

    def ended(self, home: Home, action_id: UUID, end: CardEnd) -> None:
        """What followed a card: its approval, rejection or expiry."""
        subject = Subject(SubjectKind.ACTION, action_id)
        self._decisions.observe(ACTION_FRICTION, home, subject, CardResolution(end.value))


class AgentTurnRouter:
    """The agent's `TurnRouter` over `turn.route`."""

    def __init__(self, decisions: Decisions) -> None:
        self._decisions = decisions

    async def route(self, request: RouteRequest) -> tuple[str, ...] | None:
        """The candidates an active version found needed, likeliest first; None for none."""
        candidates = tuple(
            ToolsetCandidate(name, summary)
            for name, summary in request.candidates
            if TOOLSET_NAME.fullmatch(name)
        )
        facts = TurnFacts(
            question=request.question, previous=request.previous, section=request.section,
            candidates=candidates, forced=request.forced, room=request.room, turn=request.turn,
        )  # fmt: skip
        call = DecisionCall(
            request.scope, request.cross_border_consent, Subject(SubjectKind.RUN, request.run_id),
            facts, (), request.language,
        )  # fmt: skip
        outcome = await self._decisions.decide(TURN_ROUTE, call)
        return outcome.value or None

    def ended(self, home: Home, run_id: UUID, called: frozenset[str]) -> None:
        """What a routed run called."""
        subject = Subject(SubjectKind.RUN, run_id)
        self._decisions.observe(TURN_ROUTE, home, subject, ToolsetsCalled(called))


class AgentInjectionJudge:
    """The agent's `InjectionJudge` over `content.injection`."""

    def __init__(self, decisions: Decisions) -> None:
        self._decisions = decisions

    async def judge(self, piece: InjectionPiece) -> bool | None:
        """True when an active version found instructions for an AI; None otherwise."""
        facts = TextFacts(label=piece.label, tool=piece.tool, text=piece.text)
        subject = Subject(SubjectKind.TEXT, piece.run_id, piece.part)
        call = DecisionCall(
            piece.scope, piece.cross_border_consent, subject, facts, InjectionFinding.CLEAN,
            piece.language,
        )  # fmt: skip
        outcome = await self._decisions.decide(CONTENT_INJECTION, call)
        return True if outcome.value is InjectionFinding.SUSPICIOUS else None


class AgentVoiceApprovalJudge:
    """The agent's `VoiceApprovalJudge` over `voice.approval`."""

    def __init__(self, decisions: Decisions) -> None:
        self._decisions = decisions

    async def approved(self, facts: VoiceApprovalFacts) -> bool | None:
        """True only when an active version's answer in time found a clear yes."""
        call = DecisionCall(
            facts.scope, facts.cross_border_consent, Subject(SubjectKind.ACTION, facts.action_id),
            VoiceFacts(read_back=facts.read_back, utterance=facts.utterance),
            VoiceConsent.NOT_GIVEN, facts.language,
        )  # fmt: skip
        outcome = await self._decisions.decide(VOICE_APPROVAL, call)
        given = outcome.value is VoiceConsent.GIVEN and outcome.source is DecisionSource.JEV
        return True if given else None
