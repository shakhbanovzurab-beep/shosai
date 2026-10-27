"""Leo's voice conversations on the agent's threads (ADR 0070, LV-D4…LV-D6).

A conversation opens on the person's thread of a space, or on a new one, after the same
checks as a text turn: the thread is theirs and in that space, the cross-border consent of the
RU home, and voice mode switched on in Settings > Leo. The voice model gets the instruction in
English with the answer language, and the tools a text turn on that page would offer, but for
loading toolsets and opening pages, which a session fixed at its start cannot use. A tool call
runs through the same round as a text turn's — reads under the access policy with their
sources, a write as a card, never executed — and each exchange is recorded as a run of channel
`voice`. An operator has no voice conversation: the admin panel's Leo is text only.
"""

import asyncio
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Final
from uuid import UUID

from shosai.core.ai.requests import TextPart, ToolCall, ToolSchema
from shosai.core.db.transactions import HomeTransactions
from shosai.core.events.outbox import EventOutbox
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.homes import Home
from shosai.core.kernel.ids import new_id
from shosai.core.ports.directory import PortDirectory
from shosai.features.agent.application.preferences import preferences_of
from shosai.features.agent.application.run_work import RunWork
from shosai.features.agent.application.threads import Threads
from shosai.features.agent.application.token_admission import standard_tokens
from shosai.features.agent.application.tool_offer import TurnOffer, TurnRouting
from shosai.features.agent.application.tool_round import ToolParts, ToolRound
from shosai.features.agent.application.turn_task import TurnPayload
from shosai.features.agent.application.voice_emitter import VoiceEmitter
from shosai.features.agent.application.voice_records import (
    VoiceRecord,
    open_voice_run,
    record_exchange,
)
from shosai.features.agent.contracts.voice import VoiceEvents, VoiceExchange, VoiceStart
from shosai.features.agent.domain.core_tools import LOAD_TOOLSET, NAVIGATE
from shosai.features.agent.domain.operator import is_operator
from shosai.features.agent.domain.preferences import AUTO, Switch, answer_language
from shosai.features.agent.domain.threads import ScopeKind, ThreadScope
from shosai.features.agent.infrastructure.person_records import AgentSettingsRecord
from shosai.features.agent.infrastructure.turn_graph import ModelAnswer
from shosai.features.agent.infrastructure.voice_prompts import voice_instruction
from shosai.features.identity.contracts import CONSENT_READER, Principal

# Сессия голоса задаёт инструменты один раз: догрузка наборов и переход по страницам ей не подходят.
FIXED_SESSION_SKIPS: Final = frozenset({LOAD_TOOLSET, NAVIGATE})


@dataclass(frozen=True, slots=True)
class VoiceParts:
    """What voice conversations work with."""

    transactions: HomeTransactions
    ports: PortDirectory
    threads: Threads
    routing: TurnRouting
    tools: ToolParts
    outbox: EventOutbox


@dataclass(slots=True)
class Exchange:
    """The exchange in progress: its terms, its work, and whether its run is written."""

    payload: TurnPayload
    work: RunWork
    run_open: bool = False


@dataclass(slots=True)
class VoiceTalk:
    """An open conversation; `exchange` is the one in progress, if any."""

    parts: VoiceParts
    terms: TurnPayload
    offer: TurnOffer
    instruction: str
    clock: Callable[[], datetime]
    exchange: Exchange | None = None
    # Вызовы и запись обмена идут по одному: строка прогона пишется один раз.
    turn: asyncio.Lock = field(default_factory=asyncio.Lock)

    @property
    def thread_id(self) -> UUID:
        """The thread the exchanges go to."""
        return self.terms.thread_id

    @property
    def cross_border_consent(self) -> bool:
        """Whether the person consented to cross-border transfer, as read at the start."""
        return self.terms.cross_border_consent

    @property
    def tools(self) -> tuple[ToolSchema, ...]:
        """The page's tools for the voice model, without the ones a fixed session cannot use."""
        return tuple(
            schema
            for schema in self.offer.schemas()
            if (offered := self.offer.tool(schema.name)) is not None
            and offered.spec.name not in FIXED_SESSION_SKIPS
        )

    def current(self) -> Exchange:
        """The exchange in progress, begun now when there is none."""
        if self.exchange is None:
            payload = self.terms.model_copy(
                update={
                    "run_id": new_id(), "question_id": new_id(), "reply_id": new_id(),
                    "started_at": self.clock(),
                }
            )  # fmt: skip
            self.exchange = Exchange(payload, RunWork(offer=self.offer))
        return self.exchange

    async def call(self, call_id: str, name: str, arguments: str, events: VoiceEvents) -> str:
        """One tool call of the voice model, answered as a text turn's round answers it."""
        async with self.turn:
            exchange = self.current()
            if not exchange.run_open:
                await open_voice_run(self.parts.transactions, exchange.payload)
                exchange.run_open = True
            answer = ModelAnswer(
                text="", finish_reason="tool_calls", usage=None, first_token_ms=None,
                tool_calls=(ToolCall(call_id, name, arguments),),
            )  # fmt: skip
            work = exchange.work
            work.answers.append(answer)
            run = (exchange.payload, work, VoiceEmitter(events))
            produced = await ToolRound(self.parts.tools, run).run(work.round_number, answer)
        replied = produced[-1].parts
        content = replied[0].text if replied and isinstance(replied[0], TextPart) else ""
        return json.dumps({"result": content}, ensure_ascii=False)

    async def record(self, exchange: VoiceExchange) -> None:
        """Write the exchange to the thread and begin the next one fresh."""
        async with self.turn:
            current = self.current()
            self.exchange = None
            record = VoiceRecord(current.payload, current.work, current.run_open)
            await record_exchange((self.parts.transactions, self.parts.outbox), record, exchange)


class AgentVoiceTurns:
    """Opens voice conversations (agent's `VOICE_TURNS`)."""

    def __init__(
        self, parts: VoiceParts, clock: Callable[[], datetime] = lambda: datetime.now(UTC)
    ) -> None:
        self._parts = parts
        self._clock = clock

    async def open(self, principal: Principal, start: VoiceStart) -> VoiceTalk:
        """A conversation on the named thread or a new one, after a text turn's checks."""
        if is_operator(principal.user_id):
            raise AppError("voice_not_available", HTTPStatus.FORBIDDEN)
        scope = (
            ThreadScope(ScopeKind.WORKSPACE, org_id=start.workspace_id)
            if start.workspace_id is not None
            else ThreadScope(ScopeKind.PERSONAL)
        )
        parts = self._parts
        async with parts.transactions.begin(principal.scope(), read_only=True) as session:
            if start.thread_id is not None:
                thread = await parts.threads.visible_thread(
                    session, principal.user_id, start.thread_id
                )
                if (thread.scope_kind, thread.org_id) != (scope.kind.value, scope.org_id):
                    raise AppError("thread_not_found", HTTPStatus.NOT_FOUND)
            consent = await parts.ports.get(CONSENT_READER).cross_border(session, principal.user_id)
            preferences = preferences_of(await session.get(AgentSettingsRecord, principal.user_id))
        if principal.home is Home.RU and not consent:
            raise AppError("consent_required", HTTPStatus.FORBIDDEN)
        if not preferences.switched_on(Switch.VOICE_MODE):
            raise AppError("voice_mode_off", HTTPStatus.FORBIDDEN)
        route = (await standard_tokens(parts.ports, principal)).value
        thread_id = start.thread_id
        if thread_id is None:
            thread_id = (await parts.threads.create(principal, scope, f"voice:{new_id()}")).id
        language = answer_language(preferences, start.locale)
        terms = TurnPayload(
            home=principal.home, user_id=principal.user_id, run_id=new_id(), thread_id=thread_id,
            started_at=self._clock(), question_id=new_id(), reply_id=new_id(), language=language,
            length=preferences.response_length, cross_border_consent=consent, token_route=route,
            path=start.path,
            switches_on=tuple(s.value for s in Switch if preferences.switched_on(s)),
        )  # fmt: skip
        async with parts.transactions.begin(principal.scope(), read_only=True) as session:
            offer = await parts.routing.offer(session, terms)
        instruction = voice_instruction(language, fixed=preferences.response_language != AUTO)
        return VoiceTalk(parts, terms, offer, instruction, self._clock)
