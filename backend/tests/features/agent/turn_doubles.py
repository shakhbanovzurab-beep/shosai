"""The doubles a turn's tests run with (agent step 5a): the model, the `agent` queue, the plan's
terms, the person's profile and the meetings a page can show.

The model is a script of pieces, holding the first calls at a gate when asked; the queue drives a
sent turn at once in the background unless it holds it to play a lost worker.
"""

import asyncio
import uuid
from collections.abc import AsyncIterator, Collection, Mapping
from dataclasses import dataclass, field
from typing import Final

from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.ai.calls import CallContext, ModelRoute
from shosai.core.ai.requests import ChatRequest
from shosai.core.ai.results import ChatDelta, Usage
from shosai.core.kernel.homes import Home
from shosai.core.tasks.declaration import TaskDeclaration
from shosai.features.agent.application.run_engine import RunEngine
from shosai.features.agent.application.turn_task import TurnPayload
from shosai.features.billing.contracts import ModelTier, TokenDecision, TokenRoute
from shosai.features.identity.contracts import AccountProfile
from shosai.features.notes.contracts import MeetingFacts, TranscriptPage
from shosai.features.workspaces.contracts import Viewer

WAIT: Final = 15.0


@dataclass
class ScriptedModel:
    """Answers every call with its pieces; `gate` holds it before each piece when cleared."""

    pieces: list[ChatDelta] = field(
        default_factory=lambda: [
            ChatDelta(text="Hello"),
            ChatDelta(text=", world."),
            ChatDelta(finish_reason="stop", usage=Usage(input_tokens=12, output_tokens=3)),
        ]
    )
    gate: asyncio.Event = field(default_factory=asyncio.Event)
    # Сколько первых вызовов после первого куска ждут открытых ворот; остальные идут сразу.
    held_calls: int = 0
    failure: Exception | None = None
    calls: list[ChatRequest] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.gate.set()

    async def stream_chat(
        self, context: CallContext, route: ModelRoute, request: ChatRequest
    ) -> AsyncIterator[ChatDelta]:
        """The script, piece by piece."""
        del context, route
        held = len(self.calls) < self.held_calls
        self.calls.append(request)
        for index, piece in enumerate(self.pieces):
            if held and index > 0:
                await self.gate.wait()
            yield piece
        if self.failure is not None:
            raise self.failure


@dataclass
class InlineQueue:
    """The `agent` queue: a sent turn runs at once, or waits while `hold` plays a lost worker."""

    engine: RunEngine | None = None
    hold: bool = False
    sent: list[TurnPayload] = field(default_factory=list)
    running: list[asyncio.Task[None]] = field(default_factory=list)

    async def send(self, task: TaskDeclaration[TurnPayload], payload: TurnPayload) -> str:
        """Run the turn in the background."""
        del task
        self.sent.append(payload)
        if not self.hold and self.engine is not None:
            self.running.append(asyncio.create_task(self.engine.run(payload)))
        return str(uuid.uuid4())

    async def settle(self) -> None:
        """Wait for every turn sent so far to end."""
        await asyncio.wait_for(asyncio.gather(*self.running), WAIT)


@dataclass
class Terms:
    """The plan's token decision and who consents to cross-border transfer."""

    route: TokenRoute = TokenRoute.WITHIN_ALLOWANCE
    consenting: set[uuid.UUID] = field(default_factory=set)

    async def decision(self, home: Home, user_id: uuid.UUID, tier: ModelTier) -> TokenDecision:
        """The route the test set."""
        del home, user_id, tier
        return TokenDecision(self.route)

    async def cross_border(self, session: AsyncSession, user_id: uuid.UUID) -> bool:
        """Whether the person consented."""
        del session
        return user_id in self.consenting


@dataclass
class Profiles:
    """Each person's profile as identity gives it: a name and a time zone."""

    zones: dict[uuid.UUID, str] = field(default_factory=dict)

    async def profile(self, session: AsyncSession, user_id: uuid.UUID) -> AccountProfile | None:
        """The person's profile."""
        del session
        return AccountProfile("Anna Petrova", "en", self.zones.get(user_id, "Europe/Berlin"))

    async def names(
        self, session: AsyncSession, user_ids: Collection[uuid.UUID]
    ) -> Mapping[uuid.UUID, str]:
        """Every person is Anna here."""
        del session
        return dict.fromkeys(user_ids, "Anna Petrova")


@dataclass
class Meetings:
    """Meetings the person may read: only those the test shows."""

    shown: dict[uuid.UUID, MeetingFacts] = field(default_factory=dict)

    async def facts(
        self, session: AsyncSession, viewer: Viewer, meeting_ids: Collection[uuid.UUID]
    ) -> Mapping[uuid.UUID, MeetingFacts]:
        """The shown ones among the ids."""
        del session, viewer
        return {key: self.shown[key] for key in meeting_ids if key in self.shown}

    async def readable(
        self, session: AsyncSession, viewer: Viewer, meeting_ids: Collection[uuid.UUID]
    ) -> frozenset[uuid.UUID]:
        """The shown ones among the ids."""
        return frozenset(await self.facts(session, viewer, meeting_ids))

    async def transcript(
        self, home: Home, viewer: Viewer, meeting_id: uuid.UUID, cursor: str | None, limit: int
    ) -> TranscriptPage:
        """No transcript is read before Leo's tools."""
        del home, viewer, meeting_id, cursor, limit
        return TranscriptPage((), None)
