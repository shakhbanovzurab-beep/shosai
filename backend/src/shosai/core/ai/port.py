"""`AiProviders`: the one facade slices call models through (F6 plan §3.3, ADR 0034).

Every operation takes a `CallContext` and goes through the same steps: admission (enabled
provider, cross-border consent, prices in force), the call within the context's deadline,
and its cost recorded once per effect key. A call the provider charged for although it
failed is recorded too, with the outcome `failed`. A live session is admitted the same way
and then metered: one row per minute (F6-C5). Admission against spend ceilings, retries,
breakers and fallbacks along the route come with F6 steps 5 and 6; this step calls the
route's primary model.
"""

import asyncio
from collections.abc import AsyncGenerator, AsyncIterator, Awaitable, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager, nullcontext
from typing import Protocol

from shosai.core.ai.adapters.openrouter import OpenRouter
from shosai.core.ai.admission import Admission, AiClients
from shosai.core.ai.calls import CallContext, ModelRef, ModelRoute, Provider
from shosai.core.ai.decisions import Decision, DecisionRequest
from shosai.core.ai.documents import OcrPages, OcrRequest
from shosai.core.ai.errors import AiCallError, AiFailure, PaidCallError
from shosai.core.ai.metrics import AiMetrics
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
    Usage,
)
from shosai.core.ai.sessions.live import LiveConnection, LiveSession, LiveSessions


class Metered(Protocol):
    """A result that carries the usage of its call."""

    @property
    def usage(self) -> Usage:
        """What the call consumed."""
        ...


class AiProviders:
    """Calls models for slices and records what each call cost; built once per process."""

    def __init__(
        self,
        clients: AiClients,
        admission: Admission,
        recorder: CallRecorder,
        sessions: LiveSessions,
        metrics: AiMetrics,
    ) -> None:
        self._clients = clients
        self._admission = admission
        self._recorder = recorder
        self._sessions = sessions
        self._metrics = metrics

    async def chat(
        self, context: CallContext, route: ModelRoute, request: ChatRequest
    ) -> ChatResult:
        """A model's answer to a conversation."""
        client, call = await self._openrouter(context, route, "chat")
        return await self._recorded(call, lambda: client.chat(call.model, request))

    async def stream_chat(
        self, context: CallContext, route: ModelRoute, request: ChatRequest
    ) -> AsyncGenerator[ChatDelta]:
        """A model's answer as it is written; the cost is recorded when the usage arrives."""
        client, call = await self._openrouter(context, route, "chat")
        started = recorded = False
        try:
            async with deadline_of(context):
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
        client, call = await self._openrouter(context, route, "embed")
        return await self._recorded(call, lambda: client.embed(call.model, request))

    async def rerank(
        self, context: CallContext, route: ModelRoute, request: RerankRequest
    ) -> Ranking:
        """Documents ordered by relevance to a query."""
        client, call = await self._openrouter(context, route, "rerank")
        return await self._recorded(call, lambda: client.rerank(call.model, request))

    async def generate_image(
        self, context: CallContext, route: ModelRoute, request: ImageRequest
    ) -> GeneratedImage:
        """A picture from a prompt."""
        client, call = await self._openrouter(context, route, "image")
        return await self._recorded(call, lambda: client.generate_image(call.model, request))

    async def transcribe(
        self, context: CallContext, route: ModelRoute, request: TranscriptionRequest
    ) -> Transcript:
        """The text of a recording."""
        client, call = await self._openrouter(context, route, "transcribe")
        return await self._recorded(call, lambda: client.transcribe(call.model, request))

    async def decide(
        self, context: CallContext, route: ModelRoute, request: DecisionRequest
    ) -> Decision:
        """Typed answers of a decision model; the caller always sets the deadline."""
        if context.deadline is None:
            message = "решение всегда со своим сроком (Leo §6.3)"
            raise ValueError(message)
        client, call = await self._openrouter(context, route, "decide")
        return await self._recorded(call, lambda: client.decide(call.model, request))

    async def ocr(self, context: CallContext, route: ModelRoute, request: OcrRequest) -> OcrPages:
        """A scanned document or an image read to Markdown, page by page."""
        client = self._admission.client(
            self._clients.mistral, Provider.MISTRAL, route.primary, "ocr"
        )
        call = await self._admission.admit(context, route, "ocr")
        return await self._recorded(call, lambda: client.ocr(call.model, request))

    async def diarize(
        self, context: CallContext, route: ModelRoute, request: DiarizationRequest
    ) -> Diarization:
        """Who spoke when; a job that failed after it was charged is recorded, then refused."""
        client = self._admission.client(
            self._clients.pyannote, Provider.PYANNOTE, route.primary, "diarize"
        )
        call = await self._admission.admit(context, route, "diarize")
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
        kind = "live_transcription"
        client = self._admission.client(self._clients.openai_realtime, Provider.OPENAI, model, kind)
        return self._live(context, model, kind, lambda: client.connect(model, setup))

    def open_translation_stream(
        self,
        context: CallContext,
        model: ModelRef,
        setup: NativeTranslationSetup | VoiceSetup,
    ) -> AbstractAsyncContextManager[LiveSession]:
        """Speech translated as it is spoken, by a translation model or an interpreter."""
        kind = "live_translation"
        client = self._admission.client(self._clients.gemini_live, Provider.GOOGLE, model, kind)
        return self._live(context, model, kind, lambda: client.connect(model, setup))

    def open_voice_session(
        self, context: CallContext, model: ModelRef, setup: VoiceSetup
    ) -> AbstractAsyncContextManager[LiveSession]:
        """A spoken conversation with a model that may call tools."""
        client = self._admission.client(self._clients.gemini_live, Provider.GOOGLE, model, "voice")
        return self._live(context, model, "voice", lambda: client.connect(model, setup))

    @asynccontextmanager
    async def _live(
        self,
        context: CallContext,
        model: ModelRef,
        kind: str,
        connect: Callable[[], Awaitable[LiveConnection]],
    ) -> AsyncIterator[LiveSession]:
        call = await self._admission.admit(context, ModelRoute(model), kind)
        async with self._sessions.run(call, connect) as session:
            yield session

    async def _openrouter(
        self, context: CallContext, route: ModelRoute, kind: str
    ) -> tuple[OpenRouter, MeteredCall]:
        client = self._admission.client(
            self._clients.openrouter, Provider.OPENROUTER, route.primary, kind
        )
        return client, await self._admission.admit(context, route, kind)

    async def _recorded[R: Metered](self, call: MeteredCall, send: Callable[[], Awaitable[R]]) -> R:
        """Send within the deadline and record the cost; a paid failure is recorded too."""
        try:
            async with deadline_of(call.context):
                result = await send()
        except TimeoutError:
            raise AiCallError(AiFailure.DEADLINE_EXCEEDED) from None
        except PaidCallError as paid:
            await self._recorder.record(call, paid.usage, CallOutcome.FAILED)
            raise AiCallError(paid.failure) from None
        await self._recorder.record(call, result.usage)
        return result


def deadline_of(context: CallContext) -> AbstractAsyncContextManager[object]:
    """The context's deadline, or none."""
    if context.deadline is None:
        return nullcontext()
    return asyncio.timeout(context.deadline.total_seconds())
