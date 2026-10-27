"""One question set to Jev through the provider port (Leo §6.2 step 4, ADR 0069 DL-D2).

A decision is paid by the person it serves, as background work: origin `background` keeps it
out of their Leo tokens and inside their background day budget; the effect key
`decision:<id>` gives it exactly one cost row (inv-9). The port's own deadline is three times
the policy's, at most two seconds: the caller waits only the policy's deadline, but a call
that answers later still lands, is paid and recorded once, and calibrates the next deadline.
A failure of the port becomes the reason of the rule's outcome; it never reaches the caller.
"""

import time
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Final, Protocol
from uuid import UUID

from shosai.core.ai.calls import CallClass, CallContext, CallOrigin, ModelRoute
from shosai.core.ai.decisions import Decision, DecisionRequest
from shosai.core.ai.errors import AiCallError, AiFailure
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.decisions.domain.outcomes import DecisionReason
from shosai.features.decisions.domain.policy import Policy
from shosai.features.decisions.domain.records import effect_key

LATE_FACTOR: Final = 3
LATEST: Final = timedelta(seconds=2)
FAILURES: Final[Mapping[AiFailure, DecisionReason]] = {
    AiFailure.DEADLINE_EXCEEDED: DecisionReason.DEADLINE,
    AiFailure.CONSENT_REQUIRED: DecisionReason.NO_CONSENT,
    AiFailure.SPEND_LIMIT: DecisionReason.BUDGET,
    AiFailure.EXPENSIVE_PAUSED: DecisionReason.BUDGET,
    AiFailure.INPUT_TOO_LARGE: DecisionReason.CONTRACT,
    AiFailure.CONTEXT_LENGTH_EXCEEDED: DecisionReason.CONTRACT,
}


class JevPort(Protocol):
    """The provider port's decision call."""

    async def decide(
        self, context: CallContext, route: ModelRoute, request: DecisionRequest
    ) -> Decision:
        """Typed answers of a decision model."""
        ...


@dataclass(frozen=True, slots=True)
class Answered:
    """Jev's answer, or why there is none, and how long the call took."""

    decision: Decision | None
    failure: DecisionReason | None
    latency_ms: int


@dataclass(frozen=True, slots=True)
class Payer:
    """Who a decision is for and whether their text may cross the border."""

    scope: TenancyScope
    consent: bool


class Asker:
    """Sends a decision's questions to Jev and reports what came back."""

    def __init__(self, jev: JevPort, route: ModelRoute) -> None:
        self._jev = jev
        self._route = route

    async def ask(
        self, policy: Policy[Any, Any], payer: Payer, request: DecisionRequest, decision_id: UUID
    ) -> Answered:
        """The answer, or the reason the call failed."""
        started = time.monotonic()
        context = CallContext(
            effect_key=effect_key(decision_id),
            feature=f"decisions.{policy.point}",
            call_class=CallClass.STANDARD,
            origin=CallOrigin.BACKGROUND,
            scope=payer.scope,
            cross_border_consent=payer.consent,
            deadline=min(policy.deadline * LATE_FACTOR, LATEST),
        )
        try:
            decision = await self._jev.decide(context, self._route, request)
        except AiCallError as error:
            reason = FAILURES.get(error.failure, DecisionReason.PROVIDER_ERROR)
            return Answered(None, reason, elapsed_ms(started))
        return Answered(decision, None, elapsed_ms(started))


def elapsed_ms(started: float) -> int:
    """Milliseconds since `started`."""
    return int((time.monotonic() - started) * 1000)
