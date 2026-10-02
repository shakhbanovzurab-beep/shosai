"""Metrics of the Valkey mechanisms of one process (target architecture §16.5, §16.7).

Labels come from closed sets: the limit name is declared in code by the slice that owns
the route, the decision and the outage policy are enums. Lock names carry ids and are
never labels.
"""

from typing import Literal

from prometheus_client import CollectorRegistry, Counter

type RateDecisionName = Literal["allowed", "limited", "failed_open"]


class KeyValueMetrics:
    """Rate-limit decisions and lock operations Valkey did not answer in time."""

    def __init__(self, registry: CollectorRegistry) -> None:
        self._rate_decisions = Counter(
            "whisperer_rate_limit_decisions",
            "Решения лимитов запросов: пропущен, отклонён, пропущен без проверки",
            ("limit", "decision"),
            registry=registry,
        )
        self._lock_outages = Counter(
            "whisperer_lock_outages",
            "Операции блокировок, на которые Valkey не ответил вовремя",
            ("policy",),
            registry=registry,
        )

    def count_rate_decision(self, limit: str, decision: RateDecisionName) -> None:
        """Count one decision of a limit."""
        self._rate_decisions.labels(limit=limit, decision=decision).inc()

    def count_lock_outage(self, policy: str) -> None:
        """Count one lock operation Valkey did not answer; `policy` is a `LockOutagePolicy`."""
        self._lock_outages.labels(policy=policy).inc()
