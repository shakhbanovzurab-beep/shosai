"""The agent's voice turns over the action bench, a call's socket and a judge of spoken approval."""

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Final
from uuid import UUID

from prometheus_client import CollectorRegistry

from shosai.core.idempotency.ledger import EffectLedger
from shosai.core.idempotency.metrics import EffectKeyMetrics
from shosai.core.ports.directory import PortDirectory
from shosai.features.agent.application.action_cards import ActionCards
from shosai.features.agent.application.action_decisions import ActionDecisions
from shosai.features.agent.application.threads import Threads
from shosai.features.agent.application.voice_approval import VoiceApproval
from shosai.features.agent.application.voice_turns import AgentVoiceTurns, VoiceParts
from shosai.features.agent.contracts.voice import VOICE_APPROVAL_JUDGE, VoiceApprovalFacts
from tests.features.agent.action_bench import ActionBench

WAIT: Final = timedelta(seconds=3)


@dataclass
class Heard:
    """What a call told the conversation's socket: its steps, cards and voice approvals."""

    steps: list[tuple[str, str]] = field(default_factory=list)
    cards: list[UUID] = field(default_factory=list)
    approvals: list[UUID] = field(default_factory=list)

    async def step(self, activity: str, status: str) -> None:
        """A step and its status."""
        self.steps.append((activity, status))

    async def proposed(self, action_id: UUID) -> None:
        """A card."""
        self.cards.append(action_id)

    async def decided(self, action_id: UUID) -> None:
        """A card approved by voice."""
        self.approvals.append(action_id)


@dataclass
class ApprovalJudge:
    """Decisions' `voice.approval` as a test sets it: one verdict for every phrase it hears,
    and whether an active version is in force."""

    verdict: bool | None = True
    active: bool = True
    heard: list[VoiceApprovalFacts] = field(default_factory=list)

    async def ready(self) -> bool:
        """Whether the test put an active version in force."""
        return self.active

    async def approved(self, facts: VoiceApprovalFacts) -> bool | None:
        """The verdict the test set."""
        self.heard.append(facts)
        return self.verdict


def agent_voices(actions: ActionBench, judge: ApprovalJudge | None = None) -> AgentVoiceTurns:
    """The agent's voice turns over the bench, approving cards through its gateway; without a
    judge nothing is approved by voice."""
    turn = actions.turns
    transactions, ports = turn.homes.transactions, turn.ports
    threads = Threads(transactions, (ports, EffectLedger(EffectKeyMetrics(CollectorRegistry()))))
    judges = PortDirectory()
    judges.install([VOICE_APPROVAL_JUDGE.bind(judge)] if judge is not None else [])
    decisions = ActionDecisions(transactions, actions.parts, wait=WAIT, judging=actions.judging)
    approval = VoiceApproval(transactions, judges, ActionCards(turn.catalog, ports), decisions)
    parts = turn.parts
    return AgentVoiceTurns(
        VoiceParts(transactions, ports, threads, parts.routing, parts.tools, parts.outbox, approval)
    )
