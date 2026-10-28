"""A run's telemetry: its times, its spans and its numbers (agent plan §3.6, Leo §16; step 5b).

A run's times are the person's: from the question's admission (`started_at`) — or, for the
epilogue after a card, from the decision that resumed it — to the worker's pickup, to the
model's first word, to the recorded end. The platform's own time is the run's
wall time less the model's calls and the tools' time in their slices (Leo §11.3): admission,
queue, context, routing and dispatch, the final transaction. Spans carry ids and codes only —
`agent.run` with the run's id, `agent.context`, the provider port's own `ai.call` and a
`tool.<name>` per call inside — never a word of the conversation.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Final

from opentelemetry.trace import Tracer

from shosai.features.agent.application.turn_route import tier_of
from shosai.features.agent.application.turn_task import TurnPayload
from shosai.features.agent.domain.budgets import Segment
from shosai.features.agent.domain.endings import Ending
from shosai.features.agent.domain.runs import Channel
from shosai.features.agent.infrastructure.run_metrics import RunMetrics
from shosai.features.agent.infrastructure.turn_graph import ModelAnswer

MICRO: Final = Decimal(1_000_000)


@dataclass
class TurnTimes:
    """When this part of a run began — its admission, or its resume — when its worker took
    it, and how long its model calls and its tools took."""

    began: datetime
    picked_up: datetime
    model: timedelta = timedelta(0)
    tools: timedelta = timedelta(0)
    sizes: dict[Segment, int] = field(default_factory=dict)

    def overhead(self, ended: datetime) -> timedelta:
        """The platform's own time: everything but the model's calls and the tools."""
        return max(ended - self.began - self.model - self.tools, timedelta(0))

    def first_word(self, answer: ModelAnswer | None) -> timedelta | None:
        """From the beginning to the first word, when the model wrote one."""
        if answer is None or answer.first_token_ms is None:
            return None
        return (self.picked_up - self.began) + timedelta(milliseconds=answer.first_token_ms)


def micro_usd(answer: ModelAnswer | None) -> int:
    """What the provider says the call cost, in micro-USD; 0 when it did not say."""
    if answer is None or answer.usage is None or answer.usage.reported_cost_usd is None:
        return 0
    return int(answer.usage.reported_cost_usd * MICRO)


class RunTelemetry:
    """The run's spans and numbers, in the process's tracer and registry."""

    def __init__(self, metrics: RunMetrics, tracer: Tracer) -> None:
        self.metrics = metrics
        self._tracer = tracer

    @contextmanager
    def run(self, payload: TurnPayload) -> Iterator[None]:
        """The run's root span."""
        attributes = {"agent.run_id": str(payload.run_id), "agent.turn_kind": payload.kind.value}
        with self._tracer.start_as_current_span("agent.run", attributes=attributes):
            yield

    @contextmanager
    def context(self) -> Iterator[None]:
        """The context builder's span."""
        with self._tracer.start_as_current_span("agent.context"):
            yield

    def picked(self, times: TurnTimes) -> None:
        """A worker took the turn."""
        self.metrics.picked_up(max((times.picked_up - times.began).total_seconds(), 0.0))

    def ended(
        self,
        payload: TurnPayload,
        result: tuple[Ending, ModelAnswer | None],
        times: TurnTimes,
        now: datetime,
    ) -> None:
        """A run's end, its times, its context and its cost."""
        ending, answer = result
        self.metrics.ended(Channel.WEB, ending.code)
        first = times.first_word(answer)
        overhead = times.overhead(now).total_seconds()
        seconds = None if first is None else first.total_seconds()
        self.metrics.timed(payload.home, overhead, seconds, tier_of(payload.route))
        if times.sizes:
            self.metrics.context(times.sizes)
        if answer is not None:
            self.metrics.cost(tier_of(payload.route), micro_usd(answer) / 1_000_000)
