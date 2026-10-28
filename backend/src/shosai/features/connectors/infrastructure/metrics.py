"""Connectors' metrics (plan §3.11): refreshes, lost tokens, revocations, broken apps.

Labels are closed sets — a provider, an app, a problem, an outcome, an OAuth application's
key, a home — never an id, an account or an address. Counters start at zero for their known
series, so the monitors' `increase` sees the first event after a restart.
"""

from collections.abc import Iterable
from typing import Final

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

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
CALLS: Final = "shosai_connectors_provider_requests_total"
CALL_SECONDS: Final = "shosai_connectors_provider_request_seconds"
CALL_BUCKETS: Final = (0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0)
ACCOUNTS_REPORTED: Final = "shosai_connectors_accounts_reported_total"
QUOTA_NEAR: Final = "shosai_connectors_provider_quota_near_total"
REPORT_VERDICTS: Final = ("reported", "closed", "updated")


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
        self._calls = Counter(
            CALLS, "Calls to providers by provider, operation and outcome",
            ["provider", "operation", "outcome"], registry=registry,
        )  # fmt: skip
        self._call_seconds = Histogram(
            CALL_SECONDS, "Time of calls to providers, by provider and operation",
            ["provider", "operation"], buckets=CALL_BUCKETS, registry=registry,
        )  # fmt: skip
        self._reported = Counter(
            ACCOUNTS_REPORTED, "Accounts reported to a provider, and its verdicts on them",
            ["provider", "verdict"], registry=registry,
        )  # fmt: skip
        self._quota_near = Counter(
            QUOTA_NEAR, "Provider answers saying Shosai used 80% of its application's quota",
            ["provider"], registry=registry,
        )  # fmt: skip
        for verdict in REPORT_VERDICTS:
            self._reported.labels(provider=Provider.ATLASSIAN.value, verdict=verdict)
        for provider in Provider:
            self._quota_near.labels(provider=provider.value)
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

    def called(self, provider: Provider, operation: str, outcome: str, seconds: float) -> None:
        """Count one provider call by its outcome: a status class, busy or unavailable."""
        self._calls.labels(provider=provider.value, operation=operation, outcome=outcome).inc()
        self._call_seconds.labels(provider=provider.value, operation=operation).observe(seconds)

    def reported(self, provider: Provider, accounts: int, verdicts: Iterable[str]) -> None:
        """Count the accounts of one report and the provider's verdicts on them."""
        self._reported.labels(provider=provider.value, verdict="reported").inc(accounts)
        for verdict in verdicts:
            self._reported.labels(provider=provider.value, verdict=verdict).inc()

    def quota_near(self, provider: Provider) -> None:
        """Count an answer that says the application's quota is at least 80% used."""
        self._quota_near.labels(provider=provider.value).inc()
