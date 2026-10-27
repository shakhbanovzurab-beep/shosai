"""The Decision Layer's engine: `decide` and `observe` (decisions plan §3.3, ADR 0026, ADR 0069).

1. The point's versions in force; none → the rule's outcome (`policy_off`).
2. Pre-rules: nothing the policy could change → the rule's outcome, counted only; a state
   over its budget, no consent in the Russian home, the process's calls in flight at their
   cap, or Jev's endpoint not confirmed zero-retention → the rule's outcome, recorded.
3. Jev through the port, the caller waiting only the policy's deadline; a later answer is
   recorded when it lands.
4. Verdicts, the policy's outcome, the more careful of it and the rule's.
5. A shadow version is answered beside the active one and acts on nothing.
6. A record per consulted decision, metrics and the span `decision.<point>`.

Nothing here raises for a provider: every failure is the rule's outcome with its reason.
"""

import asyncio
import time
from collections.abc import Coroutine
from typing import Any, Final

import structlog
from opentelemetry.trace import Tracer

from shosai.core.kernel.homes import Home
from shosai.core.kernel.ids import new_id
from shosai.features.decisions.application.asking import Answered, Asker, Payer
from shosai.features.decisions.application.in_force import InForce, PoliciesInForce
from shosai.features.decisions.application.judging import Asked
from shosai.features.decisions.application.recording import Prepared, Recorder, prepare
from shosai.features.decisions.contracts import DecisionCall, DecisionPoint, Outcome
from shosai.features.decisions.domain.outcomes import DecisionReason, DecisionSource, Subject
from shosai.features.decisions.infrastructure.metrics import DecisionMetrics

SECONDS_TO_DRAIN: Final = 2.5
RULE = DecisionSource.RULE
FALLBACK = DecisionSource.FALLBACK
log = structlog.stdlib.get_logger(__name__)


class DecisionEngine:
    """Decides at a point under its policy in force; the `Decisions` port."""

    def __init__(
        self,
        parts: tuple[PoliciesInForce, Asker, Recorder],
        telemetry: tuple[DecisionMetrics, Tracer],
        *,
        max_in_flight: int,
    ) -> None:
        self._in_force, self._asker, self._recorder = parts
        self._metrics, self._tracer = telemetry
        self._max_in_flight = max_in_flight
        self._pending: set[asyncio.Task[Any]] = set()

    async def decide[F, V, O](
        self, point: DecisionPoint[F, V, O], call: DecisionCall[F, V]
    ) -> Outcome[V]:
        """The outcome, never less careful than `call.rule`."""
        started = time.monotonic()
        with self._tracer.start_as_current_span(f"decision.{point.name}") as span:
            outcome = await self._decide(point, call)
            span.set_attributes(
                {"decision.source": outcome.source.value, "decision.reason": outcome.reason.value,
                 "decision.policy": outcome.policy or ""}
            )  # fmt: skip
        self._metrics.decided(
            point.name, outcome.source.value, outcome.reason.value,
            changed=outcome.value != call.rule, seconds=time.monotonic() - started,
        )  # fmt: skip
        return outcome

    def observe[F, V, O](
        self, point: DecisionPoint[F, V, O], home: Home, subject: Subject, seen: O
    ) -> None:
        """Report what followed a decided subject; buffered, never blocking."""
        self._recorder.observed(point.name, home, subject, seen)

    async def drain(self) -> None:
        """Let the calls in flight land and be recorded, within the port's own deadline."""
        if self._pending:
            await asyncio.wait(set(self._pending), timeout=SECONDS_TO_DRAIN)

    async def _decide[F, V, O](
        self, point: DecisionPoint[F, V, O], call: DecisionCall[F, V]
    ) -> Outcome[V]:
        versions = await self._in_force.of(point.name)
        lead = versions.active or versions.shadow
        if lead is None:
            return Outcome(call.rule, DecisionReason.POLICY_OFF, RULE)
        if lead.policy.settled(call.facts, call.rule):
            return Outcome(call.rule, DecisionReason.NOTHING_TO_DECIDE, RULE, lead.policy.key)
        prepared = prepare(lead, call, self._recorder.hash_key)
        asked = asked_for(call, prepared)
        reason = prepared if isinstance(prepared, DecisionReason) else await self._blocked(call)
        if reason is not None or not isinstance(prepared, Prepared):
            reason = reason or DecisionReason.CONTRACT
            self._recorder.fallback(lead, asked, reason, shadow=versions.active is None)
            return Outcome(call.rule, reason, FALLBACK, lead.policy.key, asked.decision_id)
        payer = Payer(call.scope, call.cross_border_consent)
        if versions.active is None:
            self._detach(self._alone(lead, asked, prepared, payer))
            return Outcome(call.rule, DecisionReason.POLICY_OFF, RULE, None, asked.decision_id)
        shadow = versions.shadow
        if shadow is not None and shadow.policy.digest() != versions.active.policy.digest():
            self._shadow_apart(shadow, call, payer)
            shadow = None
        return await self._in_time(versions.active, shadow, asked, prepared, payer)

    async def _in_time(
        self,
        active: InForce,
        shadow: InForce | None,
        asked: Asked,
        prepared: Prepared,
        payer: Payer,
    ) -> Outcome[Any]:
        """Wait for Jev up to the policy's deadline; a later answer is recorded as late."""
        ask = self._asker.ask(active.policy, payer, prepared.request, asked.decision_id)
        task = self._spawn(ask)
        done, _ = await asyncio.wait({task}, timeout=active.policy.deadline.total_seconds())
        if task in done:
            return self._recorder.answered(active, shadow, asked, task.result())

        def landed(finished: asyncio.Task[Answered]) -> None:
            if finished.cancelled() or finished.exception() is not None:
                log.error("Опоздавший вызов Jev не завершился", point=active.policy.point)
                return
            self._recorder.landed_late(active, shadow, asked, finished.result())

        task.add_done_callback(landed)
        return Outcome(
            asked.rule, DecisionReason.DEADLINE, FALLBACK, active.policy.key, asked.decision_id
        )

    async def _alone(self, shadow: InForce, asked: Asked, prepared: Prepared, payer: Payer) -> None:
        """A shadow asked on its own: recorded, acting on nothing."""
        answered = await self._asker.ask(shadow.policy, payer, prepared.request, asked.decision_id)
        self._recorder.shadowed(shadow, asked, answered)

    def _shadow_apart(self, shadow: InForce, call: DecisionCall[Any, Any], payer: Payer) -> None:
        """A shadow with questions of its own asks in the background, if it can."""
        prepared = prepare(shadow, call, self._recorder.hash_key)
        if isinstance(prepared, Prepared):
            self._detach(self._alone(shadow, asked_for(call, prepared), prepared, payer))

    async def _blocked(self, call: DecisionCall[Any, Any]) -> DecisionReason | None:
        """Why Jev may not be asked now, if anything stops it."""
        if call.scope.home is Home.RU and not call.cross_border_consent:
            return DecisionReason.NO_CONSENT
        if len(self._pending) >= self._max_in_flight:
            return DecisionReason.BUSY
        if not await self._recorder.terms.zero_retention():
            return DecisionReason.NOT_ZDR
        return None

    def _spawn[T](self, work: Coroutine[Any, Any, T]) -> asyncio.Task[T]:
        """A tracked task: counted in flight until it ends, awaited by `drain`."""
        task = asyncio.create_task(work)
        self._pending.add(task)
        self._metrics.in_flight(len(self._pending))
        task.add_done_callback(self._finished)
        return task

    def _detach(self, work: Coroutine[Any, Any, None]) -> None:
        """A tracked task nobody awaits: its failure is logged when it ends."""
        self._spawn(work).add_done_callback(report_failure)

    def _finished(self, task: asyncio.Task[Any]) -> None:
        self._pending.discard(task)
        self._metrics.in_flight(len(self._pending))


def asked_for(call: DecisionCall[Any, Any], prepared: Prepared | DecisionReason) -> Asked:
    """A new decision of this call, with the state's hash when the request was made."""
    digest = prepared.hash if isinstance(prepared, Prepared) else None
    home = call.scope.home
    return Asked(new_id(), call.subject, home, call.language, call.facts, call.rule, digest)


def report_failure(task: asyncio.Task[Any]) -> None:
    """Log a background task that ended with an error nobody awaited."""
    if not task.cancelled() and task.exception() is not None:
        log.error("Теневое решение не завершилось", error=type(task.exception()).__name__)
