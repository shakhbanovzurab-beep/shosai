"""`AiProviders`: the one facade slices call models through (F6 plan §3.3, ADR 0034).

Every operation takes a `CallContext` and a `ModelRoute` and goes through the same steps:
the provider is enabled, a Russian-home call carries the cross-border consent (nfr-14), the
model has a price for each unit its kind is charged in (ADR 0035: no price, no call), the
call runs within the context's deadline, and its cost is recorded once per effect key.
Admission against spend ceilings, retries, breakers and fallbacks along the route come with
F6 steps 5 and 6; this step calls the route's primary model.
"""

import asyncio
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import AbstractAsyncContextManager, nullcontext
from types import MappingProxyType
from typing import Final

from shosai.core.ai.adapters.openrouter import OpenRouter
from shosai.core.ai.calls import CallContext, ModelRef, ModelRoute
from shosai.core.ai.costs.amounts import is_priced
from shosai.core.ai.errors import AiCallError, AiFailure
from shosai.core.ai.metrics import AiMetrics
from shosai.core.ai.pricing.prices import ModelPrices, PriceBook
from shosai.core.ai.recording import CallRecorder
from shosai.core.ai.requests import ChatRequest, EmbeddingRequest, ImageRequest, RerankRequest
from shosai.core.ai.results import ChatDelta, ChatResult, Embeddings, GeneratedImage, Ranking, Unit
from shosai.core.kernel.homes import Home

# Единицы, без цены которых вызов этого вида не уходит.
NEEDED_UNITS: Final = MappingProxyType(
    {
        "chat": frozenset({Unit.INPUT, Unit.OUTPUT}),
        "embed": frozenset({Unit.INPUT}),
        "rerank": frozenset({Unit.REQUEST}),
        "image": frozenset({Unit.IMAGE}),
    }
)


class AiProviders:
    """Calls models for slices and records what each call cost; built once per process."""

    def __init__(
        self,
        openrouter: OpenRouter | None,
        prices: PriceBook,
        recorder: CallRecorder,
        metrics: AiMetrics,
    ) -> None:
        self._openrouter = openrouter
        self._prices = prices
        self._recorder = recorder
        self._metrics = metrics

    async def chat(
        self, context: CallContext, route: ModelRoute, request: ChatRequest
    ) -> ChatResult:
        """A model's answer to a conversation."""
        client, prices = await self._admit(context, route.primary, "chat")
        result = await self._within(context, lambda: client.chat(route.primary, request))
        await self._recorder.record(context, route.primary, "chat", result.usage, prices)
        return result

    async def stream_chat(
        self, context: CallContext, route: ModelRoute, request: ChatRequest
    ) -> AsyncGenerator[ChatDelta]:
        """A model's answer as it is written; the cost is recorded when the usage arrives."""
        client, prices = await self._admit(context, route.primary, "chat")
        started = recorded = False
        try:
            async with self._deadline(context):
                async for delta in client.stream_chat(route.primary, request):
                    if delta.usage is not None and not recorded:
                        await self._recorder.record(
                            context, route.primary, "chat", delta.usage, prices
                        )
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
        client, prices = await self._admit(context, route.primary, "embed")
        result = await self._within(context, lambda: client.embed(route.primary, request))
        await self._recorder.record(context, route.primary, "embed", result.usage, prices)
        return result

    async def rerank(
        self, context: CallContext, route: ModelRoute, request: RerankRequest
    ) -> Ranking:
        """Documents ordered by relevance to a query."""
        client, prices = await self._admit(context, route.primary, "rerank")
        result = await self._within(context, lambda: client.rerank(route.primary, request))
        await self._recorder.record(context, route.primary, "rerank", result.usage, prices)
        return result

    async def generate_image(
        self, context: CallContext, route: ModelRoute, request: ImageRequest
    ) -> GeneratedImage:
        """A picture from a prompt."""
        client, prices = await self._admit(context, route.primary, "image")
        result = await self._within(context, lambda: client.generate_image(route.primary, request))
        await self._recorder.record(context, route.primary, "image", result.usage, prices)
        return result

    async def _admit(
        self, context: CallContext, model: ModelRef, kind: str
    ) -> tuple[OpenRouter, ModelPrices]:
        """The client and prices of a call that may be sent; `AiCallError` otherwise."""
        if self._openrouter is None:
            raise self._refuse(kind, AiFailure.MODEL_UNAVAILABLE)
        scope = context.scope
        if scope is not None and scope.home is Home.RU and not context.cross_border_consent:
            raise self._refuse(kind, AiFailure.CONSENT_REQUIRED)
        prices = await self._prices.prices_of(model)
        if not is_priced(prices, NEEDED_UNITS[kind]):
            raise self._refuse(kind, AiFailure.MODEL_UNPRICED)
        return self._openrouter, prices

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
