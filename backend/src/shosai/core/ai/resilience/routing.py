"""A call along its route: each model admitted, guarded and tried in turn (§3.5).

For each model of the `ModelRoute`, in order: admission (its provider's client, consent,
prices), its breaker, a slot of its provider, then the call with one retry before the first
byte. A provider failure — or an open breaker, a full provider, a missing client or price —
moves the call to the next model; a refusal of the input or of consent stops it at once.
Only when the route is exhausted does the caller see the last failure. The deadline of the
context covers the whole route.

A stream is retried and moved on only before its first piece: once a piece reached the
caller, a failure ends the stream.
"""

from collections.abc import AsyncGenerator, AsyncIterator, Awaitable, Callable
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from typing import Final

from shosai.core.ai.admission import Admission
from shosai.core.ai.calls import CallContext, ModelRef, ModelRoute
from shosai.core.ai.errors import AiCallError, AiFailure, PaidCallError
from shosai.core.ai.metrics import AiMetrics
from shosai.core.ai.recording import CallRecorder, MeteredCall
from shosai.core.ai.resilience.breakers import Breakers, Gate
from shosai.core.ai.resilience.metrics import ResilienceMetrics
from shosai.core.ai.resilience.operations import Metered, Operation, StreamOperation
from shosai.core.ai.resilience.retries import RetryBudget
from shosai.core.ai.resilience.slots import ProviderSlots
from shosai.core.ai.results import ChatDelta
from shosai.core.ai.spend.guard import SpendGuard

# Сбои провайдера: их считает выключатель модели.
PROVIDER_FAILURES: Final = frozenset(
    {AiFailure.PROVIDER_ERROR, AiFailure.RATE_LIMITED, AiFailure.DEADLINE_EXCEEDED}
)
# С этими отказами вызов уходит к следующей модели маршрута.
NEXT_MODEL: Final = PROVIDER_FAILURES | {
    AiFailure.MODEL_UNAVAILABLE,
    AiFailure.MODEL_UNPRICED,
    AiFailure.RETRY_LATER,
}


@dataclass(frozen=True, slots=True)
class Resilience:
    """The guards of every call: breakers, provider slots, the retry budget, their metrics."""

    breakers: Breakers
    slots: ProviderSlots
    retries: RetryBudget
    metrics: ResilienceMetrics


@dataclass(frozen=True, slots=True)
class Attempt[C]:
    """One model of the route, admitted and let through by its breaker."""

    index: int
    client: C
    call: MeteredCall
    gate: Gate


class RouteRunner:
    """Runs calls along their routes and records what each answered call cost."""

    def __init__(
        self,
        admission: Admission,
        recorder: CallRecorder,
        resilience: Resilience,
        spend: SpendGuard,
        metrics: AiMetrics,
    ) -> None:
        self._admission = admission
        self._recorder = recorder
        self._guards = resilience
        self._spend = spend
        self._metrics = metrics

    @property
    def admission(self) -> Admission:
        """The admission of calls, for the port's live sessions."""
        return self._admission

    @property
    def guards(self) -> Resilience:
        """Breakers and slots, for the port's live sessions."""
        return self._guards

    @property
    def spend(self) -> SpendGuard:
        """Spend control, for the port's turns and live sessions."""
        return self._spend

    async def call[C, R: Metered](
        self, context: CallContext, route: ModelRoute, operation: Operation[C, R]
    ) -> R:
        """The answer of the first model of the route that gives one."""
        last: AiCallError | None = None
        async for attempt in self._attempts(context, route, operation.kind, operation.client_of):
            if isinstance(attempt, AiCallError):
                last = attempt
                continue
            hold = await self._spend.reserve(attempt.call, operation.estimate)
            try:
                result = await self._sent(attempt, context, operation.send)
            except PaidCallError as paid:
                await self._recorder.record_failed(attempt.call, paid.usage, attempt.index)
                last = await self._failed(attempt.call.model, AiCallError(paid.failure))
                continue
            except AiCallError as error:
                last = await self._failed(attempt.call.model, error)
                continue
            else:
                await self._answered(attempt, operation.kind)
                await self._recorder.record(attempt.call, result.usage)
                await self._spend.consume(context, result.usage, attempt.call)
                return result
            finally:
                await self._spend.release(hold)
        raise last or AiCallError(AiFailure.MODEL_UNAVAILABLE)

    async def stream[C](
        self,
        context: CallContext,
        route: ModelRoute,
        operation: StreamOperation[C],
    ) -> AsyncGenerator[ChatDelta]:
        """The pieces of the first model that starts answering; usage recorded once."""
        last: AiCallError | None = None
        async for attempt in self._attempts(context, route, "chat", operation.client_of):
            if isinstance(attempt, AiCallError):
                last = attempt
                continue
            hold = await self._spend.reserve(attempt.call, operation.estimate)
            try:
                async with self._started(attempt, context, operation.open) as opened:
                    if isinstance(opened, AiCallError):
                        last = await self._failed(attempt.call.model, opened)
                        continue
                    await self._answered(attempt, "chat")
                    async for delta in self._recorded(attempt, opened):
                        yield delta
                    return
            finally:
                await self._spend.release(hold)
        raise last or AiCallError(AiFailure.MODEL_UNAVAILABLE)

    async def _attempts[C](
        self,
        context: CallContext,
        route: ModelRoute,
        kind: str,
        client_of: Callable[[ModelRef], C],
    ) -> AsyncIterator[Attempt[C] | AiCallError]:
        """Each model of the route: tried, or why it is skipped; a refusal of consent stops all."""
        for index, model in enumerate(route.models):
            try:
                client = client_of(model)
                call = await self._admission.admit(context, ModelRoute(model), kind)
            except AiCallError as refused:
                if refused.failure not in NEXT_MODEL:
                    raise
                yield refused
                continue
            gate = await self._guards.breakers.allow(model)
            if gate is Gate.OPEN:
                yield AiCallError(AiFailure.MODEL_UNAVAILABLE)
                continue
            yield Attempt(index, client, call, gate)

    async def _sent[C, R](
        self, attempt: Attempt[C], context: CallContext, send: Callable[[C, ModelRef], Awaitable[R]]
    ) -> R:
        """The call within a slot of its provider, retried once before the first byte."""
        model = attempt.call.model
        async with self._guards.slots.held(model.provider, context.call_class, session=False):
            return await self._guards.retries.attempt(
                model.provider, lambda: send(attempt.client, model)
            )

    @asynccontextmanager
    async def _started[C](
        self,
        attempt: Attempt[C],
        context: CallContext,
        open_stream: Callable[[C, ModelRef], AsyncGenerator[ChatDelta]],
    ) -> AsyncIterator[AsyncGenerator[ChatDelta] | AiCallError]:
        """A stream whose first piece arrived, holding its slot; or the failure before it.

        Only the slot and the first piece are guarded here: a failure of a started stream
        reaches the caller through the stream itself.
        """
        model = attempt.call.model

        async def first_piece() -> AsyncGenerator[ChatDelta]:
            pieces = open_stream(attempt.client, model)
            try:
                first = await anext(pieces)
            except StopAsyncIteration:
                return replay(None, None)
            return replay(first, pieces)

        async with AsyncExitStack() as held:
            try:
                await held.enter_async_context(
                    self._guards.slots.held(model.provider, context.call_class, session=False)
                )
                stream = await self._guards.retries.attempt(model.provider, first_piece)
            except AiCallError as refused:
                yield refused
                return
            yield stream

    async def _recorded[C](
        self, attempt: Attempt[C], pieces: AsyncGenerator[ChatDelta]
    ) -> AsyncGenerator[ChatDelta]:
        """The pieces of a started stream; the usage of its last piece is recorded once."""
        recorded = False
        try:
            async for delta in pieces:
                if delta.usage is not None and not recorded:
                    await self._recorder.record(attempt.call, delta.usage)
                    await self._spend.consume(attempt.call.context, delta.usage, attempt.call)
                    recorded = True
                yield delta
        except AiCallError as broken:
            if broken.failure in PROVIDER_FAILURES:
                await self._guards.breakers.failed(attempt.call.model)
            raise
        finally:
            if not recorded:
                # Провайдер берёт деньги и за оборванный поток, а расход без usage не узнать.
                self._metrics.lost()

    async def _failed(self, model: ModelRef, error: AiCallError) -> AiCallError:
        """Count a provider failure on the model's breaker; stop on any other refusal."""
        if error.failure in PROVIDER_FAILURES:
            await self._guards.breakers.failed(model)
        if error.failure not in NEXT_MODEL:
            raise error
        return error

    async def _answered[C](self, attempt: Attempt[C], kind: str) -> None:
        await self._guards.breakers.succeeded(attempt.call.model, attempt.gate)
        if attempt.index:
            self._guards.metrics.fell_back(attempt.call.model.provider.value, kind)


async def replay(
    first: ChatDelta | None, rest: AsyncGenerator[ChatDelta] | None
) -> AsyncGenerator[ChatDelta]:
    """The first piece again, then the rest of the stream."""
    if first is None or rest is None:
        return
    yield first
    async for delta in rest:
        yield delta
