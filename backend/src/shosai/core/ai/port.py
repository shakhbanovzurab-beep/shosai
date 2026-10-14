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

from collections.abc import AsyncGenerator, AsyncIterator, Awaitable, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from decimal import Decimal

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
from shosai.core.ai.resilience.operations import (
    Metered,
    Operation,
    StreamOperation,
    as_standard,
    deadline_of,
    standard_of,
)
from shosai.core.ai.resilience.routing import RouteRunner
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
from shosai.core.ai.spend.estimates import (
    chat_estimate,
    decision_estimate,
    embedding_estimate,
    ocr_estimate,
    per_item,
    speech_estimate,
)


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
        operation = Operation(
            "chat", self._openrouter("chat"), lambda c, m: c.chat(m, request),
            chat_estimate(request),
        )  # fmt: skip
        return await self._routed(context, route, operation)

    async def stream_chat(
        self, context: CallContext, route: ModelRoute, request: ChatRequest
    ) -> AsyncGenerator[ChatDelta]:
        """A model's answer as it is written; the cost is recorded when the usage arrives."""
        operation = StreamOperation(
            self._openrouter("chat"), lambda c, m: c.stream_chat(m, request),
            chat_estimate(request),
        )  # fmt: skip
        started = False
        try:
            async with deadline_of(context):
                try:
                    async for delta in self._runner.stream(context, route, operation):
                        started = True
                        yield delta
                except AiCallError as paused:
                    if started or standard_of(route, paused) is None:
                        raise
                    async for delta in self._runner.stream(
                        as_standard(context), standard_of(route, paused) or route, operation
                    ):
                        yield delta
        except TimeoutError:
            raise AiCallError(AiFailure.DEADLINE_EXCEEDED) from None

    async def embed(
        self, context: CallContext, route: ModelRoute, request: EmbeddingRequest
    ) -> Embeddings:
        """Vectors of texts."""
        operation = Operation(
            "embed", self._openrouter("embed"), lambda c, m: c.embed(m, request),
            embedding_estimate(request),
        )  # fmt: skip
        return await self._routed(context, route, operation)

    async def rerank(
        self, context: CallContext, route: ModelRoute, request: RerankRequest
    ) -> Ranking:
        """Documents ordered by relevance to a query."""
        operation = Operation(
            "rerank", self._openrouter("rerank"), lambda c, m: c.rerank(m, request),
            per_item(Unit.REQUEST),
        )  # fmt: skip
        return await self._routed(context, route, operation)

    async def generate_image(
        self, context: CallContext, route: ModelRoute, request: ImageRequest
    ) -> GeneratedImage:
        """A picture from a prompt."""
        operation = Operation(
            "image", self._openrouter("image"), lambda c, m: c.generate_image(m, request),
            per_item(Unit.IMAGE),
        )  # fmt: skip
        return await self._routed(context, route, operation)

    async def transcribe(
        self, context: CallContext, route: ModelRoute, request: TranscriptionRequest
    ) -> Transcript:
        """The text of a recording."""
        operation = Operation(
            "transcribe", self._openrouter("transcribe"), lambda c, m: c.transcribe(m, request),
            speech_estimate(request.audio),
        )  # fmt: skip
        return await self._routed(context, route, operation)

    async def decide(
        self, context: CallContext, route: ModelRoute, request: DecisionRequest
    ) -> Decision:
        """Typed answers of a decision model; the caller always sets the deadline."""
        if context.deadline is None:
            message = "решение всегда со своим сроком (Leo §6.3)"
            raise ValueError(message)
        operation = Operation(
            "decide", self._openrouter("decide"), lambda c, m: c.decide(m, request),
            decision_estimate(request),
        )  # fmt: skip
        return await self._routed(context, route, operation)

    async def ocr(self, context: CallContext, route: ModelRoute, request: OcrRequest) -> OcrPages:
        """A scanned document or an image read to Markdown, page by page."""
        operation = Operation(
            "ocr", self._mistral("ocr"), lambda c, m: c.ocr(m, request), ocr_estimate(request)
        )
        return await self._routed(context, route, operation)

    async def diarize(
        self, context: CallContext, route: ModelRoute, request: DiarizationRequest
    ) -> Diarization:
        """Who spoke when; a job that failed after it was charged is recorded, then refused."""
        # Срок вызова соблюдает сам адаптер: оборвать его ожидание значило бы потерять
        # строку уже оплаченного задания.
        operation = Operation(
            "diarize", self._pyannote("diarize"),
            lambda c, m: c.diarize(m, request, context.deadline), speech_estimate(request.audio),
        )  # fmt: skip
        return await self._runner.call(context, route, operation)

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

    def turn(
        self, context: CallContext, estimate_usd: Decimal
    ) -> AbstractAsyncContextManager[CallContext]:
        """A Leo turn's reservation: the context it yields makes every call draw on it."""
        return self._runner.spend.turn(context, estimate_usd)

    async def _routed[C, R: Metered](
        self, context: CallContext, route: ModelRoute, operation: Operation[C, R]
    ) -> R:
        """The call along its route within the context's deadline; the route's standard model
        answers an expensive call while the kill switch pauses it."""
        try:
            async with deadline_of(context):
                try:
                    return await self._runner.call(context, route, operation)
                except AiCallError as paused:
                    standard = standard_of(route, paused)
                    if standard is None:
                        raise
                return await self._runner.call(as_standard(context), standard, operation)
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
