"""`AiProviders`: the one facade slices call models through (F6 plan §3.3, ADR 0034).

Every operation takes a `CallContext` and a `ModelRoute` and goes through the same steps:
the provider is enabled, a Russian-home call carries the cross-border consent (nfr-14), the
model has a price for each unit its kind is charged in (ADR 0035: no price, no call), the
call runs within the context's deadline, and its cost is recorded once per effect key.
Admission against spend ceilings, retries, breakers and fallbacks along the route come with
F6 steps 5 and 6; this step calls the route's primary model.
"""

import asyncio
from collections.abc import AsyncGenerator, AsyncIterator, Awaitable, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager, nullcontext
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from shosai.core.ai.adapters.gemini_live import GeminiLive
from shosai.core.ai.adapters.openai_realtime import OpenAiRealtime
from shosai.core.ai.adapters.openrouter import OpenRouter
from shosai.core.ai.adapters.pyannote import Pyannote
from shosai.core.ai.calls import CallContext, ModelRef, ModelRoute, Provider
from shosai.core.ai.costs.amounts import is_priced
from shosai.core.ai.errors import AiCallError, AiFailure, PaidCallError
from shosai.core.ai.metrics import AiMetrics
from shosai.core.ai.pricing.prices import PriceBook
from shosai.core.ai.recording import CallOutcome, CallRecorder, MeteredCall
from shosai.core.ai.requests import (
    ChatRequest,
    DiarizationRequest,
    EmbeddingRequest,
    ImageRequest,
    LiveTranscriptionSetup,
    NativeTranslationSetup,
    RerankRequest,
    TranscriptionRequest,
    VoiceSetup,
)
from shosai.core.ai.results import (
    ChatDelta,
    ChatResult,
    Diarization,
    Embeddings,
    GeneratedImage,
    Ranking,
    Transcript,
    Unit,
)
from shosai.core.ai.sessions.live import LiveConnection, LiveSession, LiveSessions
from shosai.core.kernel.homes import Home

TOKENS: Final = frozenset({Unit.INPUT, Unit.OUTPUT})
SECONDS: Final = frozenset({Unit.AUDIO_SECOND})
SPOKEN: Final = frozenset({Unit.INPUT_AUDIO, Unit.OUTPUT_AUDIO})
# Наборы единиц, без цены хотя бы одного из которых вызов этого вида не уходит:
# речь у одних моделей тарифицируется токенами, у других — секундами.
NEEDED_UNITS: Final = MappingProxyType(
    {
        "chat": (TOKENS,),
        "embed": (frozenset({Unit.INPUT}),),
        "rerank": (frozenset({Unit.REQUEST}),),
        "image": (frozenset({Unit.IMAGE}),),
        "transcribe": (TOKENS, SECONDS),
        "diarize": (SECONDS,),
        "live_transcription": (SECONDS, TOKENS, frozenset({Unit.INPUT_AUDIO, Unit.OUTPUT})),
        "live_translation": (SECONDS, SPOKEN),
        "voice": (SPOKEN | TOKENS,),
    }
)


@dataclass(frozen=True, slots=True)
class AiClients:
    """The provider clients of the process; None when the provider has no key."""

    openrouter: OpenRouter | None
    pyannote: Pyannote | None
    openai_realtime: OpenAiRealtime | None
    gemini_live: GeminiLive | None


class AiProviders:
    """Calls models for slices and records what each call cost; built once per process."""

    def __init__(
        self,
        clients: AiClients,
        prices: PriceBook,
        recorder: CallRecorder,
        sessions: LiveSessions,
        metrics: AiMetrics,
    ) -> None:
        self._clients = clients
        self._prices = prices
        self._recorder = recorder
        self._sessions = sessions
        self._metrics = metrics

    async def chat(
        self, context: CallContext, route: ModelRoute, request: ChatRequest
    ) -> ChatResult:
        """A model's answer to a conversation."""
        client, call = self._openrouter(route, "chat"), await self._admit(context, route, "chat")
        result = await self._within(context, lambda: client.chat(call.model, request))
        await self._recorder.record(call, result.usage)
        return result

    async def stream_chat(
        self, context: CallContext, route: ModelRoute, request: ChatRequest
    ) -> AsyncGenerator[ChatDelta]:
        """A model's answer as it is written; the cost is recorded when the usage arrives."""
        client, call = self._openrouter(route, "chat"), await self._admit(context, route, "chat")
        started = recorded = False
        try:
            async with self._deadline(context):
                async for delta in client.stream_chat(call.model, request):
                    if delta.usage is not None and not recorded:
                        await self._recorder.record(call, delta.usage)
                        recorded = True
                    started = True
                    yield delta
        except TimeoutError:
            raise AiCallError(AiFailure.DEADLINE_EXCEEDED) from None
        finally:
            if started and not recorded:
                # Провайдер берёт деньги и за оборванный поток, а расход без usage не узнать.
                self._metrics.lost()

    async def embed(
        self, context: CallContext, route: ModelRoute, request: EmbeddingRequest
    ) -> Embeddings:
        """Vectors of texts."""
        client, call = self._openrouter(route, "embed"), await self._admit(context, route, "embed")
        result = await self._within(context, lambda: client.embed(call.model, request))
        await self._recorder.record(call, result.usage)
        return result

    async def rerank(
        self, context: CallContext, route: ModelRoute, request: RerankRequest
    ) -> Ranking:
        """Documents ordered by relevance to a query."""
        client = self._openrouter(route, "rerank")
        call = await self._admit(context, route, "rerank")
        result = await self._within(context, lambda: client.rerank(call.model, request))
        await self._recorder.record(call, result.usage)
        return result

    async def generate_image(
        self, context: CallContext, route: ModelRoute, request: ImageRequest
    ) -> GeneratedImage:
        """A picture from a prompt."""
        client, call = self._openrouter(route, "image"), await self._admit(context, route, "image")
        result = await self._within(context, lambda: client.generate_image(call.model, request))
        await self._recorder.record(call, result.usage)
        return result

    async def transcribe(
        self, context: CallContext, route: ModelRoute, request: TranscriptionRequest
    ) -> Transcript:
        """The text of a recording."""
        client = self._openrouter(route, "transcribe")
        call = await self._admit(context, route, "transcribe")
        result = await self._within(context, lambda: client.transcribe(call.model, request))
        await self._recorder.record(call, result.usage)
        return result

    async def diarize(
        self, context: CallContext, route: ModelRoute, request: DiarizationRequest
    ) -> Diarization:
        """Who spoke when; a job that failed after it was charged is recorded, then refused."""
        client = self._pyannote(route)
        call = await self._admit(context, route, "diarize")
        try:
            # Срок вызова соблюдает сам адаптер: оборвать его ожидание значило бы потерять
            # строку уже оплаченного задания.
            result = await client.diarize(call.model, request, context.deadline)
        except PaidCallError as paid:
            await self._recorder.record(call, paid.usage, CallOutcome.FAILED)
            raise AiCallError(paid.failure) from None
        await self._recorder.record(call, result.usage)
        return result

    def open_transcription_stream(
        self, context: CallContext, model: ModelRef, setup: LiveTranscriptionSetup
    ) -> AbstractAsyncContextManager[LiveSession]:
        """A meeting's speech streamed to text by an OpenAI Realtime model."""
        client = self._clients.openai_realtime
        if client is None or model.provider is not Provider.OPENAI:
            raise self._refuse("live_transcription", AiFailure.MODEL_UNAVAILABLE)
        return self._live(
            context, model, "live_transcription", lambda: client.connect(model, setup)
        )

    def open_translation_stream(
        self,
        context: CallContext,
        model: ModelRef,
        setup: NativeTranslationSetup | VoiceSetup,
    ) -> AbstractAsyncContextManager[LiveSession]:
        """Speech translated as it is spoken, by a translation model or an interpreter."""
        client = self._gemini(model, "live_translation")
        return self._live(context, model, "live_translation", lambda: client.connect(model, setup))

    def open_voice_session(
        self, context: CallContext, model: ModelRef, setup: VoiceSetup
    ) -> AbstractAsyncContextManager[LiveSession]:
        """A spoken conversation with a model that may call tools."""
        client = self._gemini(model, "voice")
        return self._live(context, model, "voice", lambda: client.connect(model, setup))

    @asynccontextmanager
    async def _live(
        self,
        context: CallContext,
        model: ModelRef,
        kind: str,
        connect: Callable[[], Awaitable[LiveConnection]],
    ) -> AsyncIterator[LiveSession]:
        call = await self._admit(context, ModelRoute(model), kind)
        async with self._sessions.run(call, connect) as session:
            yield session

    def _gemini(self, model: ModelRef, kind: str) -> GeminiLive:
        client = self._clients.gemini_live
        if client is None or model.provider is not Provider.GOOGLE:
            raise self._refuse(kind, AiFailure.MODEL_UNAVAILABLE)
        return client

    def _openrouter(self, route: ModelRoute, kind: str) -> OpenRouter:
        client = self._clients.openrouter
        if client is None or route.primary.provider is not Provider.OPENROUTER:
            raise self._refuse(kind, AiFailure.MODEL_UNAVAILABLE)
        return client

    def _pyannote(self, route: ModelRoute) -> Pyannote:
        client = self._clients.pyannote
        if client is None or route.primary.provider is not Provider.PYANNOTE:
            raise self._refuse("diarize", AiFailure.MODEL_UNAVAILABLE)
        return client

    async def _admit(self, context: CallContext, route: ModelRoute, kind: str) -> MeteredCall:
        """The call that may be sent, with its prices; `AiCallError` otherwise."""
        scope = context.scope
        if scope is not None and scope.home is Home.RU and not context.cross_border_consent:
            raise self._refuse(kind, AiFailure.CONSENT_REQUIRED)
        prices = await self._prices.prices_of(route.primary)
        if not is_priced(prices, NEEDED_UNITS[kind]):
            raise self._refuse(kind, AiFailure.MODEL_UNPRICED)
        return MeteredCall(context, route.primary, kind, prices)

    def _refuse(self, kind: str, failure: AiFailure) -> AiCallError:
        self._metrics.refused(kind, failure.value)
        return AiCallError(failure)

    @staticmethod
    def _deadline(context: CallContext) -> AbstractAsyncContextManager[object]:
        if context.deadline is None:
            return nullcontext()
        return asyncio.timeout(context.deadline.total_seconds())

    async def _within[R](self, context: CallContext, call: Callable[[], Awaitable[R]]) -> R:
        try:
            async with self._deadline(context):
                return await call()
        except TimeoutError:
            raise AiCallError(AiFailure.DEADLINE_EXCEEDED) from None
