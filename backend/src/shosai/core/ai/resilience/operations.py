"""What a routed call is: its operation, its result's usage, and the helpers of its route."""

import asyncio
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import AbstractAsyncContextManager, aclosing, nullcontext
from dataclasses import dataclass, replace
from typing import Protocol

from shosai.core.ai.calls import CallClass, CallContext, ModelRef, ModelRoute
from shosai.core.ai.errors import AiCallError, AiFailure
from shosai.core.ai.recording import MeteredCall
from shosai.core.ai.resilience.breakers import Breakers, Gate
from shosai.core.ai.resilience.metrics import ResilienceMetrics
from shosai.core.ai.resilience.retries import RetryBudget
from shosai.core.ai.resilience.slots import ProviderSlots
from shosai.core.ai.results import ChatDelta, Usage


class Metered(Protocol):
    """A result that carries the usage of its call."""

    @property
    def usage(self) -> Usage:
        """What the call consumed."""
        ...


@dataclass(frozen=True, slots=True)
class Operation[C, R]:
    """What a call does: its kind, its client per model, how it is sent, what it may cost."""

    kind: str
    client_of: Callable[[ModelRef], C]
    send: Callable[[C, ModelRef], Awaitable[R]]
    estimate: Usage
    # Строка стоимости — задачей записи, не транзакцией на пути вызова (решения Jev).
    cost_later: bool = False


@dataclass(frozen=True, slots=True)
class StreamOperation[C]:
    """A streamed chat: its client per model, how the stream opens, what it may cost."""

    client_of: Callable[[ModelRef], C]
    open: Callable[[C, ModelRef], AsyncGenerator[ChatDelta]]
    estimate: Usage


def standard_of(route: ModelRoute, failure: AiCallError) -> ModelRoute | None:
    """The route of the standard model, when the kill switch paused an expensive call."""
    if failure.failure is not AiFailure.EXPENSIVE_PAUSED or route.standard is None:
        return None
    return ModelRoute(route.standard)


def as_standard(context: CallContext) -> CallContext:
    """The same call as a standard one."""
    return replace(context, call_class=CallClass.STANDARD)


def deadline_of(context: CallContext) -> AbstractAsyncContextManager[object]:
    """The context's deadline, or none."""
    if context.deadline is None:
        return nullcontext()
    return asyncio.timeout(context.deadline.total_seconds())


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


async def replay(
    first: ChatDelta | None, rest: AsyncGenerator[ChatDelta] | None
) -> AsyncGenerator[ChatDelta]:
    """The first piece again, then the rest of the stream."""
    if first is None or rest is None:
        return
    yield first
    async with aclosing(rest):
        async for delta in rest:
            yield delta
