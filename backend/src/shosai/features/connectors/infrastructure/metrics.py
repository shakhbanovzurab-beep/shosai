"""Connectors' metrics (plan §3.11): refreshes, lost tokens, revocations, broken apps.

Labels are closed sets — a provider, an app, a problem, an outcome, an OAuth application's
key, a home — never an id, an account or an address. Counters start at zero for their known
series, so the monitors' `increase` sees the first event after a restart.
"""

from typing import Final

from prometheus_client import CollectorRegistry, Counter, Gauge

from shosai.core.kernel.homes import Home
from shosai.features.connectors.domain.catalogue import App, Provider
from shosai.features.connectors.domain.refresh import RefreshOutcome
from shosai.features.connectors.domain.states import Problem

REFRESHES: Final = "shosai_connectors_refreshes_total"
REFRESH_LOST: Final = "shosai_connectors_refresh_lost_total"
REVOKE_FAILURES: Final = "shosai_connectors_revoke_failures_total"
CLIENT_MISCONFIGURED: Final = "shosai_connectors_client_misconfigured_total"
BROKEN: Final = "shosai_connectors_broken_total"
UNDECRYPTABLE: Final = "shosai_connectors_undecryptable_secrets"


class ConnectorsMetrics:
    """The counters and gauges of the grant lifecycle."""

    def __init__(self, registry: CollectorRegistry) -> None:
        self._refreshes = Counter(
            REFRESHES, "Token refreshes by provider and outcome", ["provider", "outcome"],
            registry=registry,
        )  # fmt: skip
        self._lost = Counter(
            REFRESH_LOST, "Rotated refresh tokens that could not be written", registry=registry
        )
        self._revoke_failures = Counter(
            REVOKE_FAILURES, "Grants forgotten after the provider refused every revocation",
            ["provider"], registry=registry,
        )  # fmt: skip
        self._misconfigured = Counter(
            CLIENT_MISCONFIGURED, "Token endpoint answers refusing Shosai's own application",
            ["client"], registry=registry,
        )  # fmt: skip
        self._broken = Counter(
            BROKEN, "Apps that newly need their person, by app and problem", ["app", "problem"],
            registry=registry,
        )  # fmt: skip
        self._undecryptable = Gauge(
            UNDECRYPTABLE, "Secrets no key of the ring decrypts, per home", ["home"],
            registry=registry,
        )  # fmt: skip
        for provider in Provider:
            self._revoke_failures.labels(provider=provider.value)
            for outcome in RefreshOutcome:
                self._refreshes.labels(provider=provider.value, outcome=outcome.value)
        for home in Home:
            self._undecryptable.labels(home=home.value).set(0)

    def refreshed(self, provider: Provider, outcome: RefreshOutcome) -> None:
        """Count one refresh's outcome."""
        self._refreshes.labels(provider=provider.value, outcome=outcome.value).inc()

    def refresh_lost(self) -> None:
        """Count a rotated refresh token that could not be written."""
        self._lost.inc()

    def revoke_failed(self, provider: Provider) -> None:
        """Count a grant forgotten without its provider's revocation."""
        self._revoke_failures.labels(provider=provider.value).inc()

    def client_misconfigured(self, client_key: str) -> None:
        """Count a refusal of Shosai's own application."""
        self._misconfigured.labels(client=client_key).inc()

    def broken(self, app: App, problem: Problem, count: int = 1) -> None:
        """Count apps that newly need their person."""
        if count:
            self._broken.labels(app=app.value, problem=problem.value).inc(count)

    def undecryptable(self, home: Home, count: int) -> None:
        """Set how many secrets of a home no key decrypts."""
        self._undecryptable.labels(home=home.value).set(count)
