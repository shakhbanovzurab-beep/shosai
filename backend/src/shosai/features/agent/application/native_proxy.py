"""The native model proxy: a shipped client's conversation or screenshots, answered by the
model of the person's Studio role as a stream (agent plan §1.1, §3.3, step 14, studio step 11b).

macOS and Windows 1.4.5 call it when their realtime connection is down. A request is the
person's like a Leo turn and is refused before anything is sent: `consent_required` (403) in
the Russian home without consent to cross-border transfer, `token_limit` (402) once the plan's
standard tokens are spent, `rate_limited` (429) past 30 a minute, `model_role_unconfigured`
(503) when the role has no default and no `AGENT_STANDARD_MODEL` stands in, `model_unavailable`
(503) with neither. The model is studio's route of the role, and the prompt carries studio's
layers (`proxy_studio.py`). The call goes through the provider port, which holds the person's two
streams, the input caps and the spend ceilings and records its cost. A task of the proxy's own
reads the answer from the provider to its end, so a client that leaves mid-answer leaves the
call to finish and its cost row to be written. The proxy waits up to 20 s for the first piece:
a refusal of the port by then is the request's error status, and the model that answers names
`X-Model`; a slower first piece streams anyway, and a failure after it ends the answer with a
short note in the person's language.
"""

import asyncio
import time
from collections.abc import AsyncGenerator, AsyncIterator, Callable
from dataclasses import dataclass, field
from datetime import timedelta
from http import HTTPStatus
from typing import Final, Protocol

import structlog

from shosai.core.ai.calls import CallClass, CallContext, CallOrigin, ModelRoute
from shosai.core.ai.errors import AiCallError
from shosai.core.ai.requests import ChatRequest
from shosai.core.ai.results import ChatDelta
from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.homes import Home
from shosai.core.kernel.ids import new_id
from shosai.core.kv.connection import REDIS_FAILURES
from shosai.core.kv.rate_limits import RateLimit, RateLimiter
from shosai.core.ports.directory import PortDirectory
from shosai.core.web.rate_limit import RateLimitedError
from shosai.features.agent.application.preferences import preferences_of
from shosai.features.agent.application.proxy_requests import (
    ChatAsk,
    Tuning,
    VisionAsk,
    chat_frame,
    chat_request,
    vision_frame,
    vision_request,
)
from shosai.features.agent.application.proxy_studio import (
    StudioLayers,
    studio_layers,
    system_messages,
)
from shosai.features.agent.application.turn_route import studio_route
from shosai.features.agent.domain.preferences import answer_language
from shosai.features.agent.domain.proxy_words import answer_stopped
from shosai.features.agent.infrastructure.person_records import AgentSettingsRecord
from shosai.features.agent.infrastructure.proxy_metrics import (
    ProxyMetrics,
    ProxyOutcome,
    ProxyRoute,
)
from shosai.features.identity.contracts import ACCOUNT_PROFILE_READER, CONSENT_READER, Principal
from shosai.features.studio.contracts import ModelRole, PromptRole, ResolvedRoute

PROXY_LIMIT: Final = RateLimit("agent.proxy", 30, timedelta(minutes=1), 10)
PROXY_DEADLINE: Final = timedelta(minutes=5)
FIRST_PIECE: Final = 20.0
FEATURES: Final = {ProxyRoute.CHAT: "agent.proxy", ProxyRoute.VISION: "agent.proxy_vision"}
ERROR_FINISH: Final = "error"
STOP_FINISH: Final = "stop"
log = structlog.stdlib.get_logger(__name__)

type Item = ChatDelta | Exception | None


class ProxyModels(Protocol):
    """The provider port's streamed chat, as the proxy uses it."""

    def stream_chat(
        self, context: CallContext, route: ModelRoute, request: ChatRequest
    ) -> AsyncIterator[ChatDelta]:
        """The model's answer as it is written."""
        ...


@dataclass(frozen=True, slots=True)
class Piece:
    """A piece of the answer for the client: text, or the finish with its reason."""

    text: str = ""
    finish: str | None = None


@dataclass
class ProxyAnswer:
    """An answer under way: the model that answers, and the pieces still to come."""

    model: str
    language: str
    route: ProxyRoute
    metrics: ProxyMetrics
    queue: asyncio.Queue[Item]
    first: list[Item] = field(default_factory=list)

    async def pieces(self) -> AsyncGenerator[Piece]:
        """The text as it comes, then the finish; a failure ends it with a short note."""
        while True:
            item = self.first.pop(0) if self.first else await self.queue.get()
            if isinstance(item, Exception):
                self.metrics.ended(self.route, ProxyOutcome.INTERRUPTED)
                yield Piece(answer_stopped(self.language), ERROR_FINISH)
                return
            if item is None or item.finish_reason is not None:
                self.metrics.ended(self.route, ProxyOutcome.ANSWERED)
                text = "" if item is None else item.text
                if text:
                    yield Piece(text)
                yield Piece(finish=STOP_FINISH if item is None else item.finish_reason)
                return
            if item.text:
                yield Piece(item.text)


@dataclass(frozen=True, slots=True)
class Admitted:
    """A person let through: their consent, their answer language, studio's route of the
    role — none is the legacy standard model — and studio's layers."""

    consent: bool
    language: str
    resolved: ResolvedRoute | None = None
    layers: StudioLayers = field(default_factory=StudioLayers)

    def tuning(self) -> Tuning | None:
        """The role's output limit and temperature, with studio's route."""
        resolved = self.resolved
        return None if resolved is None else Tuning(resolved.max_tokens, resolved.temperature)


class NativeProxy:
    """Answers the shipped clients' conversations and screenshots."""

    def __init__(
        self,
        parts: tuple[HomeTransactions, PortDirectory, ProxyModels, RateLimiter],
        route: Callable[[], ModelRoute | None],
        metrics: ProxyMetrics,
        limit: RateLimit = PROXY_LIMIT,
    ) -> None:
        self._transactions, self._ports, self._models, self._limiter = parts
        self._route, self._metrics, self._limit = route, metrics, limit
        # Задачи, читающие ответы провайдера до конца: сильные ссылки, пока они идут.
        self._readers: set[asyncio.Task[None]] = set()

    async def chat(
        self, principal: Principal, ask: ChatAsk, role: PromptRole = PromptRole.LIVE_ANSWERS
    ) -> ProxyAnswer:
        """The conversation's answer in the role, under way."""
        admitted = await self._admitted(principal, ProxyRoute.CHAT, role)
        system = system_messages(chat_frame(admitted.language), role, admitted.layers)
        request = chat_request(ask, system, admitted.tuning())
        if request is None:
            self._metrics.ended(ProxyRoute.CHAT, ProxyOutcome.REFUSED)
            raise AppError("conversation_empty", HTTPStatus.BAD_REQUEST)
        return await self._answer(principal, admitted, request, ProxyRoute.CHAT)

    async def vision(self, principal: Principal, ask: VisionAsk) -> ProxyAnswer:
        """The screenshots' answer, under way."""
        if not ask.frames:
            self._metrics.ended(ProxyRoute.VISION, ProxyOutcome.REFUSED)
            raise AppError("no_valid_image", HTTPStatus.BAD_REQUEST)
        role = PromptRole.SCREENSHOTS
        admitted = await self._admitted(principal, ProxyRoute.VISION, role)
        system = system_messages(vision_frame(ask, admitted.language), role, admitted.layers)
        request = vision_request(ask, system, admitted.tuning())
        return await self._answer(principal, admitted, request, ProxyRoute.VISION)

    async def _admitted(
        self, principal: Principal, route: ProxyRoute, role: PromptRole
    ) -> Admitted:
        try:
            return await self._admission(principal, role)
        except AppError:
            self._metrics.ended(route, ProxyOutcome.REFUSED)
            raise

    async def _admission(self, principal: Principal, role: PromptRole) -> Admitted:
        async with self._transactions.begin(principal.scope(), read_only=True) as session:
            consent = await self._ports.get(CONSENT_READER).cross_border(session, principal.user_id)
            stored = await session.get(AgentSettingsRecord, principal.user_id)
            profile = await self._ports.get(ACCOUNT_PROFILE_READER).profile(
                session, principal.user_id
            )
            layers = await studio_layers(self._ports, session, principal.user_id, role)
        if principal.home is Home.RU and not consent:
            raise AppError("consent_required", HTTPStatus.FORBIDDEN)
        resolved, _ = await studio_route(
            (self._ports, self._transactions), principal,
            (ModelRole(role.value), None, frozenset()), legacy=self._route() is not None,
        )  # fmt: skip
        try:
            verdict = await self._limiter.check(self._limit, str(principal.user_id))
        except REDIS_FAILURES as error:
            raise AppError("agent_unavailable", HTTPStatus.SERVICE_UNAVAILABLE) from error
        if not verdict.allowed:
            raise RateLimitedError(verdict.retry_after)
        interface = profile.language if profile is not None else None
        language = answer_language(preferences_of(stored), interface)
        return Admitted(consent, language, resolved, layers)

    async def _answer(
        self, principal: Principal, admitted: Admitted, request: ChatRequest, route: ProxyRoute
    ) -> ProxyAnswer:
        resolved = admitted.resolved
        chosen = resolved.route if resolved is not None else self._route()
        if chosen is None:
            self._metrics.ended(route, ProxyOutcome.REFUSED)
            raise AppError("model_unavailable", HTTPStatus.SERVICE_UNAVAILABLE)
        context = CallContext(
            effect_key=f"{FEATURES[route]}:{new_id()}", feature=FEATURES[route],
            call_class=resolved.call_class if resolved is not None else CallClass.STANDARD,
            origin=CallOrigin.INTERACTIVE,
            scope=principal.scope(), cross_border_consent=admitted.consent,
            deadline=PROXY_DEADLINE,
        )  # fmt: skip
        queue: asyncio.Queue[Item] = asyncio.Queue()
        reader = asyncio.create_task(
            self._read(self._models.stream_chat(context, chosen, request), queue)
        )
        self._readers.add(reader)
        reader.add_done_callback(self._readers.discard)
        answer = ProxyAnswer(chosen.primary.model, admitted.language, route, self._metrics, queue)
        began = time.monotonic()
        try:
            first = await asyncio.wait_for(queue.get(), FIRST_PIECE)
        except TimeoutError:
            # Первый кусок не пришёл за 20 с: заголовки уходят, ответ придёт в потоке.
            self._metrics.first_piece(route, time.monotonic() - began)
            return answer
        self._metrics.first_piece(route, time.monotonic() - began)
        if isinstance(first, AppError):
            self._metrics.ended(route, ProxyOutcome.REFUSED)
            raise first
        if isinstance(first, ChatDelta) and first.model is not None:
            answer.model = first.model.model
        answer.first.append(first)
        return answer

    @staticmethod
    async def _read(deltas: AsyncIterator[ChatDelta], queue: asyncio.Queue[Item]) -> None:
        """Read the provider's answer to its end, whoever still listens."""
        try:
            async for delta in deltas:
                queue.put_nowait(delta)
        except AiCallError as error:
            queue.put_nowait(error)
        # Неожиданный сбой чтения — конец ответа с заметкой клиенту; стек — в журнал.
        except Exception as error:
            log.exception("Ответ модели для нативного прокси оборвался")
            queue.put_nowait(error)
        finally:
            queue.put_nowait(None)
