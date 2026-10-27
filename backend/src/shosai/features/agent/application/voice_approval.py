"""A card approved by voice (Leo §8.4; Q-6 decided by the owner, ADR 0070 LV-D6).

A write in a voice exchange becomes a card as in a text turn, and Leo reads it back from the
server's rendering — the words the person also sees. A card the rule left standard (reversible
or compensable, after no one else's text) may then be approved by voice, and only when both
hold: the voice model calls `core.confirm` for that card, and every bound judge (decisions'
`voice.approval`) finds the person's phrase, as the server transcribed it, a clear approval of
what was read back. No judge, a judge in doubt, a card with a warning, one not read back in
this conversation, one no longer waiting — the card stays on the screen. An approval by voice
goes the screen's way: one conditional update, the audit, the worker, with `approved_via =
voice`; the conversation's socket is then told, so the screen re-reads the card and the data
it changed.
"""

import json
from dataclasses import dataclass
from uuid import UUID

import structlog
from sqlalchemy import select

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.errors import AppError
from shosai.core.ports.directory import PortDirectory
from shosai.features.agent.application.action_cards import ActionCards
from shosai.features.agent.application.action_decisions import ActionDecisions
from shosai.features.agent.application.action_rows import items_of
from shosai.features.agent.application.turn_task import TurnPayload
from shosai.features.agent.contracts.voice import (
    VOICE_APPROVAL_JUDGE,
    VoiceApprovalFacts,
    VoiceApprovalJudge,
)
from shosai.features.agent.domain.actions import ApprovedVia
from shosai.features.agent.domain.friction import Friction
from shosai.features.agent.infrastructure.run_records import AgentActionRecord
from shosai.features.agent.infrastructure.voice_prompts import (
    CARD_BY_VOICE,
    CARD_ON_SCREEN,
    CONFIRMED,
    NOT_APPROVED,
    NOT_WAITING,
    SCREEN_ONLY,
)
from shosai.features.identity.contracts import Principal

log = structlog.stdlib.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ReadBack:
    """A card as Leo read it back, and whether it may be approved by voice."""

    action_id: UUID
    words: str
    by_voice: bool

    def told(self) -> dict[str, str]:
        """What the voice model reads about the card."""
        note = CARD_BY_VOICE if self.by_voice else CARD_ON_SCREEN
        return {"action_id": str(self.action_id), "read_back": self.words, "next": note}


@dataclass(frozen=True, slots=True)
class Confirmation:
    """The answer `core.confirm` gives the voice model, and the card it approved, if any."""

    answer: str
    approved: UUID | None = None


class VoiceApproval:
    """Reads cards back and approves them by voice."""

    def __init__(
        self,
        transactions: HomeTransactions,
        ports: PortDirectory,
        cards: ActionCards,
        decisions: ActionDecisions,
    ) -> None:
        self._transactions = transactions
        self._ports = ports
        self._cards = cards
        self._decisions = decisions

    @property
    def available(self) -> bool:
        """Whether a judge of spoken approval is bound: without one, no card goes by voice."""
        return bool(self._judges())

    async def read_back(self, payload: TurnPayload, action_id: UUID) -> ReadBack:
        """The card in the person's words; by voice only when standard and a judge is bound."""
        async with self._transactions.begin(payload.scope(), read_only=True) as session:
            record = await session.get(AgentActionRecord, action_id)
        if record is None:
            return ReadBack(action_id, "", by_voice=False)
        items = items_of(record)
        words = "\n".join(self._cards.words(item, payload.language) for item in items)
        standard = record.friction == Friction.STANDARD and len(items) == 1
        return ReadBack(action_id, words, by_voice=standard and self.available)

    async def confirm(
        self, person: Principal, terms: TurnPayload, read: ReadBack | None, heard: str
    ) -> Confirmation:
        """The answer to `core.confirm`: approved and carried out, or why nothing was done."""
        if read is None or not read.by_voice:
            return Confirmation(told(SCREEN_ONLY))
        facts = VoiceApprovalFacts(
            read_back=read.words, utterance=heard.strip(), language=terms.language,
            scope=terms.scope(), cross_border_consent=terms.cross_border_consent,
            action_id=read.action_id,
        )  # fmt: skip
        judges = self._judges()
        verdicts = [await judge.approved(facts) for judge in judges]
        if not facts.utterance or not judges or not all(v is True for v in verdicts):
            log.info("Голосовое одобрение не принято", action_id=str(read.action_id))
            return Confirmation(told(NOT_APPROVED))
        async with self._transactions.begin(person.scope(), read_only=True) as session:
            nonce = await session.scalar(
                select(AgentActionRecord.nonce).where(AgentActionRecord.id == read.action_id)
            )
        if nonce is None:
            return Confirmation(told(NOT_WAITING))
        try:
            decided = await self._decisions.approve(
                person, read.action_id, nonce, ApprovedVia.VOICE
            )
        except AppError as refused:
            log.info(
                "Голосовое одобрение опоздало", action_id=str(read.action_id), code=refused.code
            )
            return Confirmation(told(NOT_WAITING))
        answer = json.dumps({"status": decided.record.status, "next": CONFIRMED})
        return Confirmation(answer, read.action_id)

    def _judges(self) -> tuple[VoiceApprovalJudge, ...]:
        return self._ports.all(VOICE_APPROVAL_JUDGE)


def told(note: str) -> str:
    """An answer of `core.confirm` that did nothing."""
    return json.dumps({"status": "not_done", "next": note})
