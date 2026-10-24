"""A run's telemetry: its times, its spans and its numbers (agent plan §3.6, Leo §16; step 5b).

A run's times are the person's: from the question's admission (`started_at`) to the worker's
pickup, to the model's call and its first word, to the model's last word and the recorded end.
The platform's own time is everything but the model: admission, queue and context before the
call, the final transaction after it. Spans carry ids and codes only — `agent.run` with the
run's id, `agent.context`, and the provider port's own `ai.call` inside — never a word of the
conversation.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Final

from opentelemetry.trace import Tracer

from shosai.features.agent.application.turn_task import TurnPayload
from shosai.features.agent.domain.budgets import Segment
from shosai.features.agent.domain.endings import Ending
from shosai.features.agent.domain.runs import Channel
from shosai.features.agent.infrastructure.run_metrics import RunMetrics
from shosai.features.agent.infrastructure.turn_graph import ModelAnswer

TIER: Final = "standard"
MICRO: Final = Decimal(1_000_000)


@dataclass
class TurnTimes:
    """When a run's worker took it, and when its model call began and ended."""

    picked_up: datetime
    model_started: datetime | None = None
    model_ended: datetime | None = None
    sizes: dict[Segment, int] = field(default_factory=dict)

    def overhead(self, started: datetime, ended: datetime) -> timedelta:
        """The platform's own time: everything but the model's call."""
        if self.model_started is None or self.model_ended is None:
            return ended - started
        return (self.model_started - started) + (ended - self.model_ended)

    def first_word(self, started: datetime, answer: ModelAnswer | None) -> timedelta | None:
        """From the admission to the first word, when the model wrote one."""
        if answer is None or answer.first_token_ms is None:
            return None
        return (self.picked_up - started) + timedelta(milliseconds=answer.first_token_ms)


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

    def picked(self, payload: TurnPayload, times: TurnTimes) -> None:
        """A worker took the run."""
        self.metrics.picked_up(max((times.picked_up - payload.started_at).total_seconds(), 0.0))

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
        first = times.first_word(payload.started_at, answer)
        overhead = times.overhead(payload.started_at, now).total_seconds()
        seconds = None if first is None else first.total_seconds()
        self.metrics.timed(payload.home, overhead, seconds, TIER)
        if times.sizes:
            self.metrics.context(times.sizes)
        if answer is not None:
            self.metrics.cost(TIER, micro_usd(answer) / 1_000_000)
