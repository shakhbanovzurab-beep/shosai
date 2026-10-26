"""The OpenRouter client: chat, streaming, vision, web search, embeddings, rerank, images,
transcription of recordings and Jev decisions.

One HTTPX client per process, built by composition with the key and the limits (draft
lesson: seven router call sites leaked two pools each). Deadlines of §4.3: connect 10 s,
120 s for an answer, 45 s of silence in a stream; retries, breakers and fallbacks come with
F6 step 5. Every failure leaves as `AiCallError` with a closed code; the answer's text is
never logged, only its status and length.
"""

from collections.abc import AsyncGenerator
from typing import Final

import httpx
import structlog

from shosai.core.ai.adapters.http_calls import Json, call_json, failed
from shosai.core.ai.adapters.openrouter_audio import (
    segments_of,
    transcript_text,
    transcription_body,
    transcription_usage,
)
from shosai.core.ai.adapters.openrouter_decisions import (
    DECISIONS_PATH,
    decision_body,
    decision_of,
    decision_usage,
)
from shosai.core.ai.adapters.openrouter_wire import (
    StreamedToolCalls,
    chat_body,
    citations_of,
    data_url,
    first_choice,
    image_of,
    image_usage,
    stream_chunk,
    tool_calls_of,
    usage_of,
)
from shosai.core.ai.calls import ModelRef, Provider
from shosai.core.ai.decisions import Decision, DecisionRequest
from shosai.core.ai.errors import AiCallError, AiFailure, PaidCallError
from shosai.core.ai.requests import (
    ChatRequest,
    EmbeddingRequest,
    ImageRequest,
    RerankRequest,
    TranscriptionRequest,
)
from shosai.core.ai.results import (
    ChatDelta,
    ChatResult,
    Embeddings,
    GeneratedImage,
    RankedDocument,
    Ranking,
    Transcript,
    Unit,
)

OPENROUTER_API: Final = "https://openrouter.ai/api/v1"
CALL_TIMEOUT: Final = httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=5.0)
# В потоке ждём не ответа целиком, а следующего куска: 45 с тишины — обрыв (§4.3).
STREAM_TIMEOUT: Final = httpx.Timeout(connect=10.0, read=45.0, write=30.0, pool=5.0)
log = structlog.stdlib.get_logger(__name__)


def openrouter_client(api_key: str, base_url: str = OPENROUTER_API) -> httpx.AsyncClient:
    """The process's client: authorised, with the deadlines of §4.3 and bounded pools."""
    return httpx.AsyncClient(
        base_url=base_url.rstrip("/") + "/",
        headers={"Authorization": f"Bearer {api_key}", "X-Title": "Shosai"},
        timeout=CALL_TIMEOUT,
        limits=httpx.Limits(
            max_connections=128, max_keepalive_connections=32, keepalive_expiry=120
        ),
    )


class OpenRouter:
    """Calls OpenRouter and turns its answers into the port's results."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def chat(self, model: ModelRef, request: ChatRequest) -> ChatResult:
        """One answer, with tool calls and web search when the request asks for them."""
        answer = await self._post("chat/completions", chat_body(model.model, request, stream=False))
        choice = first_choice(answer)
        message = choice.get("message") or {}
        return ChatResult(
            text=str(message.get("content") or ""),
            tool_calls=tool_calls_of(message),
            finish_reason=choice.get("finish_reason"),
            model=model,
            usage=usage_of(answer.get("usage")),
            citations=citations_of(message),
        )

    async def stream_chat(self, model: ModelRef, request: ChatRequest) -> AsyncGenerator[ChatDelta]:
        """The answer as it is written; the last delta carries the usage of the whole call."""
        body = chat_body(model.model, request, stream=True)
        calls = StreamedToolCalls()
        try:
            async with self._client.stream(
                "POST", "chat/completions", json=body, timeout=STREAM_TIMEOUT
            ) as response:
                if response.status_code != httpx.codes.OK:
                    text = (await response.aread()).decode(errors="replace")
                    raise failed(Provider.OPENROUTER, response.status_code, text)
                async for line in response.aiter_lines():
                    chunk = stream_chunk(line)
                    if chunk is not None:
                        yield self._delta(chunk, model, calls)
        except httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout:
            raise AiCallError(AiFailure.PROVIDER_ERROR, retryable=True) from None
        except httpx.TimeoutException:
            raise AiCallError(AiFailure.DEADLINE_EXCEEDED) from None
        except httpx.TransportError:
            raise AiCallError(AiFailure.PROVIDER_ERROR) from None

    async def embed(self, model: ModelRef, request: EmbeddingRequest) -> Embeddings:
        """One vector per text, ordered by the request."""
        body: Json = {"model": model.model, "input": list(request.texts)}
        if request.dimensions is not None:
            body["dimensions"] = request.dimensions
        answer = await self._post("embeddings", body)
        rows = answer.get("data")
        if not isinstance(rows, list) or len(rows) != len(request.texts):
            raise AiCallError(AiFailure.PROVIDER_ERROR)
        vectors: list[tuple[float, ...]] = [() for _ in request.texts]
        for row in rows:
            index = row.get("index") if isinstance(row, dict) else None
            vector = row.get("embedding") if isinstance(row, dict) else None
            if not isinstance(index, int) or not 0 <= index < len(vectors) or not vector:
                raise AiCallError(AiFailure.PROVIDER_ERROR)
            vectors[index] = tuple(float(value) for value in vector)
        if any(not vector for vector in vectors):
            raise AiCallError(AiFailure.PROVIDER_ERROR)
        return Embeddings(vectors=tuple(vectors), model=model, usage=usage_of(answer.get("usage")))

    async def rerank(self, model: ModelRef, request: RerankRequest) -> Ranking:
        """The documents ordered by relevance, the most relevant first."""
        body: Json = {
            "model": model.model,
            "query": request.query,
            "documents": list(request.documents),
        }
        if request.top_n is not None:
            body["top_n"] = min(request.top_n, len(request.documents))
        answer = await self._post("rerank", body)
        results = answer.get("results")
        if not isinstance(results, list):
            raise AiCallError(AiFailure.PROVIDER_ERROR)
        ranked = []
        for item in results:
            index = item.get("index") if isinstance(item, dict) else None
            score = item.get("relevance_score") if isinstance(item, dict) else None
            if not isinstance(index, int) or not 0 <= index < len(request.documents):
                raise AiCallError(AiFailure.PROVIDER_ERROR)
            if not isinstance(score, int | float):
                raise AiCallError(AiFailure.PROVIDER_ERROR)
            ranked.append(RankedDocument(index=index, score=float(score)))
        ranked.sort(key=lambda document: document.score, reverse=True)
        usage = usage_of(answer.get("usage"), unit=Unit.REQUEST, units_field="search_units")
        return Ranking(documents=tuple(ranked), model=model, usage=usage)

    async def generate_image(self, model: ModelRef, request: ImageRequest) -> GeneratedImage:
        """One picture; only `image` is asked as output, which every image model serves."""
        content: list[Json] = [{"type": "text", "text": request.prompt}]
        content += [
            {"type": "image_url", "image_url": {"url": data_url(ref)}} for ref in request.references
        ]
        body: Json = {
            "model": model.model,
            "messages": [{"role": "user", "content": content}],
            "modalities": ["image"],
        }
        answer = await self._post("chat/completions", body)
        data, media_type = image_of(first_choice(answer).get("message") or {})
        usage = image_usage(answer.get("usage"))
        return GeneratedImage(data=data, media_type=media_type, model=model, usage=usage)

    async def transcribe(self, model: ModelRef, request: TranscriptionRequest) -> Transcript:
        """The text of a recording, with timed segments when the request asks for them."""
        answer = await self._post("audio/transcriptions", transcription_body(model.model, request))
        language = answer.get("language")
        return Transcript(
            text=transcript_text(answer),
            segments=segments_of(answer.get("segments")) if request.timestamps else (),
            language=language if isinstance(language, str) else request.language,
            model=model,
            usage=transcription_usage(answer.get("usage")),
        )

    async def decide(self, model: ModelRef, request: DecisionRequest) -> Decision:
        """Typed answers to the questions about the state; one round trip."""
        url = self._client.base_url.join(DECISIONS_PATH)
        built = self._client.build_request("POST", url, json=decision_body(model.model, request))
        answer = await call_json(self._client, Provider.OPENROUTER, built)
        usage = decision_usage(answer.get("usage"))
        try:
            return decision_of(answer, model, request)
        except AiCallError as broken:
            # Ответ оплачен, но вне контракта альфа-API: строку пишем, решение — нет.
            log.error("Ответ Decisions API вне контракта", snapshot=str(answer.get("model")))
            raise PaidCallError(broken.failure, usage) from None

    async def _post(self, path: str, body: Json) -> Json:
        request = self._client.build_request("POST", path, json=body)
        return await call_json(self._client, Provider.OPENROUTER, request)

    @staticmethod
    def _delta(chunk: Json, model: ModelRef, calls: StreamedToolCalls) -> ChatDelta:
        choices = chunk.get("choices") or []
        choice = choices[0] if choices and isinstance(choices[0], dict) else {}
        delta = choice.get("delta") or {}
        if isinstance(delta, dict):
            calls.take(delta)
        usage = chunk.get("usage")
        finish = choice.get("finish_reason")
        return ChatDelta(
            text=str(delta.get("content") or ""),
            finish_reason=finish,
            usage=usage_of(usage) if isinstance(usage, dict) else None,
            model=model,
            # Вызовы целы только к концу ответа: отдаются с причиной остановки.
            tool_calls=calls.calls() if finish else (),
        )
