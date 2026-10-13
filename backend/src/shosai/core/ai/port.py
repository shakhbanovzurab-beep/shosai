"""`AiProviders`: the one facade slices call models through (F6 plan §3.3, ADR 0034).

Every operation takes a `CallContext` and runs along its route (§3.5): each model admitted
(enabled provider, cross-border consent, prices in force), let through by its breaker, given
a slot of its provider and retried once before the first byte; a failing model hands the
call to the next one. The deadline of the context covers the whole route. The cost of the
answer is recorded once per effect key; a call the provider charged for although it failed
is recorded too, with the outcome `failed`. A live session is admitted the same way, holds a
slot for its whole length and is metered one row per minute (F6-C5). Spend ceilings come
with F6 step 6.
"""

import asyncio
from collections.abc import AsyncGenerator, AsyncIterator, Awaitable, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager, nullcontext

from shosai.core.ai.adapters.mistral_ocr import MistralOcr
from shosai.core.ai.adapters.openrouter import OpenRouter
from shosai.core.ai.adapters.pyannote import Pyannote
from shosai.core.ai.admission import AiClients
from shosai.core.ai.calls import CallContext, ModelRef, ModelRoute, Provider
from shosai.core.ai.decisions import Decision, DecisionRequest
from shosai.core.ai.documents import OcrPages, OcrRequest
from shosai.core.ai.errors import AiCallError, AiFailure
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
from shosai.core.ai.resilience.breakers import Gate
from shosai.core.ai.resilience.routing import Metered, RouteRunner
from shosai.core.ai.results import (
    ChatDelta,
    ChatResult,
    Diarization,
    Embeddings,
    GeneratedImage,
    Ranking,
    Transcript,
)
from shosai.core.ai.sessions.live import LiveConnection, LiveSession, LiveSessions


class AiProviders:
    """Calls models for slices and records what each call cost; built once per process."""

    def __init__(self, clients: AiClients, runner: RouteRunner, sessions: LiveSessions) -> None:
        self._clients = clients
        self._runner = runner
        self._sessions = sessions

    async def chat(
        self, context: CallContext, route: ModelRoute, request: ChatRequest
    ) -> ChatResult:
        """A model's answer to a conversation."""
        return await self._routed(
            context, route, "chat", self._openrouter, lambda c, m: c.chat(m, request)
        )

    async def stream_chat(
        self, context: CallContext, route: ModelRoute, request: ChatRequest
    ) -> AsyncGenerator[ChatDelta]:
        """A model's answer as it is written; the cost is recorded when the usage arrives."""
        stream = self._runner.stream(
            context, route, self._openrouter("chat"), lambda c, m: c.stream_chat(m, request)
        )
        try:
            async with deadline_of(context):
                async for delta in stream:
                    yield delta
        except TimeoutError:
            raise AiCallError(AiFailure.DEADLINE_EXCEEDED) from None
        finally:
            await stream.aclose()

    async def embed(
        self, context: CallContext, route: ModelRoute, request: EmbeddingRequest
    ) -> Embeddings:
        """Vectors of texts."""
        return await self._routed(
            context, route, "embed", self._openrouter, lambda c, m: c.embed(m, request)
        )

    async def rerank(
        self, context: CallContext, route: ModelRoute, request: RerankRequest
    ) -> Ranking:
        """Documents ordered by relevance to a query."""
        return await self._routed(
            context, route, "rerank", self._openrouter, lambda c, m: c.rerank(m, request)
        )

    async def generate_image(
        self, context: CallContext, route: ModelRoute, request: ImageRequest
    ) -> GeneratedImage:
        """A picture from a prompt."""
        return await self._routed(
            context, route, "image", self._openrouter, lambda c, m: c.generate_image(m, request)
        )

    async def transcribe(
        self, context: CallContext, route: ModelRoute, request: TranscriptionRequest
    ) -> Transcript:
        """The text of a recording."""
        return await self._routed(
            context, route, "transcribe", self._openrouter, lambda c, m: c.transcribe(m, request)
        )

    async def decide(
        self, context: CallContext, route: ModelRoute, request: DecisionRequest
    ) -> Decision:
        """Typed answers of a decision model; the caller always sets the deadline."""
        if context.deadline is None:
            message = "решение всегда со своим сроком (Leo §6.3)"
            raise ValueError(message)
        return await self._routed(
            context, route, "decide", self._openrouter, lambda c, m: c.decide(m, request)
        )

    async def ocr(self, context: CallContext, route: ModelRoute, request: OcrRequest) -> OcrPages:
        """A scanned document or an image read to Markdown, page by page."""
        return await self._routed(
            context, route, "ocr", self._mistral, lambda c, m: c.ocr(m, request)
        )

    async def diarize(
        self, context: CallContext, route: ModelRoute, request: DiarizationRequest
    ) -> Diarization:
        """Who spoke when; a job that failed after it was charged is recorded, then refused."""
        # Срок вызова соблюдает сам адаптер: оборвать его ожидание значило бы потерять
        # строку уже оплаченного задания.
        return await self._runner.call(
            context,
            route,
            "diarize",
            self._pyannote("diarize"),
            lambda c, m: c.diarize(m, request, context.deadline),
        )

    def open_transcription_stream(
        self, context: CallContext, model: ModelRef, setup: LiveTranscriptionSetup
    ) -> AbstractAsyncContextManager[LiveSession]:
        """A meeting's speech streamed to text by an OpenAI Realtime model."""
        kind = "live_transcription"
        client = self._runner.admission.client(
            self._clients.openai_realtime, Provider.OPENAI, model, kind
        )
        return self._live(context, model, kind, lambda: client.connect(model, setup))

    def open_translation_stream(
        self,
        context: CallContext,
        model: ModelRef,
        setup: NativeTranslationSetup | VoiceSetup,
    ) -> AbstractAsyncContextManager[LiveSession]:
        """Speech translated as it is spoken, by a translation model or an interpreter."""
        kind = "live_translation"
        client = self._runner.admission.client(
            self._clients.gemini_live, Provider.GOOGLE, model, kind
        )
        return self._live(context, model, kind, lambda: client.connect(model, setup))

    def open_voice_session(
        self, context: CallContext, model: ModelRef, setup: VoiceSetup
    ) -> AbstractAsyncContextManager[LiveSession]:
        """A spoken conversation with a model that may call tools."""
        client = self._runner.admission.client(
            self._clients.gemini_live, Provider.GOOGLE, model, "voice"
        )
        return self._live(context, model, "voice", lambda: client.connect(model, setup))

    @asynccontextmanager
    async def _live(
        self,
        context: CallContext,
        model: ModelRef,
        kind: str,
        connect: Callable[[], Awaitable[LiveConnection]],
    ) -> AsyncIterator[LiveSession]:
        """An admitted session holding a slot of its provider, its breaker told how it opened."""
        call = await self._runner.admission.admit(context, ModelRoute(model), kind)
        breakers = self._runner.guards.breakers
        gate = await breakers.allow(model)
        if gate is Gate.OPEN:
            raise AiCallError(AiFailure.RETRY_LATER)

        async def guarded() -> LiveConnection:
            try:
                connection = await connect()
            except AiCallError:
                await breakers.failed(model)
                raise
            await breakers.succeeded(model, gate)
            return connection

        slots = self._runner.guards.slots
        async with (
            slots.held(model.provider, context.call_class, session=True),
            self._sessions.run(call, guarded) as session,
        ):
            yield session

    async def _routed[C, R: Metered](
        self,
        context: CallContext,
        route: ModelRoute,
        kind: str,
        client_of: Callable[[str], Callable[[ModelRef], C]],
        send: Callable[[C, ModelRef], Awaitable[R]],
    ) -> R:
        """The call along its route within the context's deadline."""
        try:
            async with deadline_of(context):
                return await self._runner.call(context, route, kind, client_of(kind), send)
        except TimeoutError:
            raise AiCallError(AiFailure.DEADLINE_EXCEEDED) from None

    def _openrouter(self, kind: str) -> Callable[[ModelRef], OpenRouter]:
        return lambda model: self._runner.admission.client(
            self._clients.openrouter, Provider.OPENROUTER, model, kind
        )

    def _pyannote(self, kind: str) -> Callable[[ModelRef], Pyannote]:
        return lambda model: self._runner.admission.client(
            self._clients.pyannote, Provider.PYANNOTE, model, kind
        )

    def _mistral(self, kind: str) -> Callable[[ModelRef], MistralOcr]:
        return lambda model: self._runner.admission.client(
            self._clients.mistral, Provider.MISTRAL, model, kind
        )


def deadline_of(context: CallContext) -> AbstractAsyncContextManager[object]:
    """The context's deadline, or none."""
    if context.deadline is None:
        return nullcontext()
    return asyncio.timeout(context.deadline.total_seconds())
