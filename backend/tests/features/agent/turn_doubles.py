"""The doubles a turn's tests run with (agent step 5a): the model, the `agent` queue, the plan's
terms, the person's profile and the meetings a page can show.

The model is a script of pieces, holding the first calls at a gate when asked; the queue drives a
sent turn at once in the background unless it holds it to play a lost worker.
"""

import asyncio
import uuid
from collections.abc import AsyncIterator, Callable, Collection, Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Final

from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.ai.calls import CallContext, ModelRef, ModelRoute, Provider
from shosai.core.ai.requests import ChatRequest
from shosai.core.ai.results import ChatDelta, ChatResult, Usage
from shosai.core.kernel.homes import Home
from shosai.core.tasks.declaration import TaskDeclaration
from shosai.features.agent.application.after_turn import ThreadTask
from shosai.features.agent.application.run_engine import RunEngine
from shosai.features.agent.application.turn_task import TurnPayload
from shosai.features.billing.contracts import ModelTier, TokenDecision, TokenRoute
from shosai.features.identity.contracts import AccountProfile
from shosai.features.notes.contracts import MeetingFacts, TranscriptPage
from shosai.features.workspaces.contracts import Viewer

WAIT: Final = 15.0
type Script = list[ChatDelta] | Callable[[ChatRequest], list[ChatDelta]]


@dataclass
class ScriptedModel:
    """Answers every call with its pieces; `gate` holds it before each piece when cleared."""

    pieces: list[ChatDelta] = field(
        default_factory=lambda: [
            ChatDelta(text="Hello"),
            ChatDelta(text=", world."),
            ChatDelta(
                finish_reason="stop",
                usage=Usage(input_tokens=12, output_tokens=3, reported_cost_usd=Decimal("0.0012")),
                model=ModelRef(Provider.OPENROUTER, "probe/leo"),
            ),
        ]
    )
    # Свой сценарий на каждый вызов по порядку, последний — для остальных; пусто — `pieces`.
    # Сценарий-функция читает запрос: так модель берёт ссылку из прочитанного результата.
    scripts: list[Script] = field(default_factory=list)
    gate: asyncio.Event = field(default_factory=asyncio.Event)
    # Сколько первых вызовов после первого куска ждут открытых ворот; остальные идут сразу.
    held_calls: int = 0
    failure: Exception | None = None
    calls: list[ChatRequest] = field(default_factory=list)
    # Кто платит каждый вызов: человек или платформенный счёт оператора.
    contexts: list[CallContext] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.gate.set()

    async def stream_chat(
        self, context: CallContext, route: ModelRoute, request: ChatRequest
    ) -> AsyncIterator[ChatDelta]:
        """The script, piece by piece."""
        del route
        self.contexts.append(context)
        held = len(self.calls) < self.held_calls
        script = self.scripts[min(len(self.calls), len(self.scripts) - 1)] if self.scripts else None
        pieces = self.pieces if script is None else script(request) if callable(script) else script
        self.calls.append(request)
        for index, piece in enumerate(pieces):
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
    """The plan's token decision, who consents to cross-border transfer and who lets their
    conversations help improve the models."""

    route: TokenRoute = TokenRoute.WITHIN_ALLOWANCE
    consenting: set[uuid.UUID] = field(default_factory=set)
    improving: set[uuid.UUID] = field(default_factory=set)

    async def decision(self, home: Home, user_id: uuid.UUID, tier: ModelTier) -> TokenDecision:
        """The route the test set."""
        del home, user_id, tier
        return TokenDecision(self.route)

    async def cross_border(self, session: AsyncSession, user_id: uuid.UUID) -> bool:
        """Whether the person consented."""
        del session
        return user_id in self.consenting

    async def improve_models(self, session: AsyncSession, user_id: uuid.UUID) -> bool:
        """Whether the person lets their conversations help improve the models."""
        del session
        return user_id in self.improving


@dataclass
class Profiles:
    """Each person's profile as identity gives it: a name, a language and a time zone."""

    zones: dict[uuid.UUID, str] = field(default_factory=dict)
    languages: dict[uuid.UUID, str] = field(default_factory=dict)

    async def profile(self, session: AsyncSession, user_id: uuid.UUID) -> AccountProfile | None:
        """The person's profile."""
        del session
        language = self.languages.get(user_id, "en")
        return AccountProfile("Anna Petrova", language, self.zones.get(user_id, "Europe/Berlin"))

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


@dataclass
class SentTasks:
    """The default queue: what the code under test sent to it, by task name."""

    sent: list[tuple[str, ThreadTask]] = field(default_factory=list)

    async def send(self, task: TaskDeclaration[ThreadTask], payload: ThreadTask) -> str:
        """Keep the task."""
        self.sent.append((task.name, payload))
        return str(uuid.uuid4())


@dataclass
class Utility:
    """The utility model: answers each call with the next of its answers."""

    answers: list[str] = field(default_factory=list)
    requests: list[ChatRequest] = field(default_factory=list)

    async def chat(
        self, context: CallContext, route: ModelRoute, request: ChatRequest
    ) -> ChatResult:
        """The next answer."""
        del context
        self.requests.append(request)
        return ChatResult(self.answers.pop(0), (), "stop", route.primary, Usage())


ADMIN_SESSION: Final = "admin-session"


class AdminSession:
    """The admin's session: the cookie `admin-session` is a live one."""

    async def admitted(self, cookie: str | None) -> bool:
        """Whether the cookie is the bench's admin session."""
        return cookie == ADMIN_SESSION
