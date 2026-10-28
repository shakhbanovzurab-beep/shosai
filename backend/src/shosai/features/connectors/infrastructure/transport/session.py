"""An authorized session on one connection: the call as the provider's rules allow it (§3.6).

The token is injected, refreshed when it expires and once more on a 401; a second 401 with a
fresh token means the grant is gone at the provider. A 429 — or a 503 with `Retry-After` —
stops that account for every process for the time named. A 5xx or a timeout counts toward the
provider's breaker; a read is tried once more with jitter, a write never. Every other answer,
4xx included, is the consumer's to read. Spans and metrics name the provider and the
operation, never the URL, an id or a token; an answer saying 80% of the application's quota
is used is counted for the provider's alert.
"""

import asyncio
import re
import secrets
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Final
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from opentelemetry.trace import Tracer
from pydantic import SecretStr

from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.connectors.application.grant_tokens import GrantTokens
from shosai.features.connectors.contracts import ConnectionView, NeedsReconnectError
from shosai.features.connectors.contracts.provider import (
    ProviderBusyError,
    ProviderCall,
    ProviderResponse,
    ProviderUnavailableError,
)
from shosai.features.connectors.domain.descriptors import LimitSubject, ProviderDescriptor
from shosai.features.connectors.domain.states import Problem
from shosai.features.connectors.infrastructure.metrics import ConnectorsMetrics
from shosai.features.connectors.infrastructure.transport.guards import ProviderGuards
from shosai.features.connectors.infrastructure.transport.quota import near_quota

OPERATION: Final = re.compile(r"[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+")
SAFE: Final = frozenset({"GET", "HEAD"})
HTTP_UNAUTHORIZED: Final = 401
HTTP_TOO_MANY: Final = 429
HTTP_UNAVAILABLE: Final = 503
SERVER_ERRORS: Final = range(500, 600)
DEFAULT_WAIT: Final = timedelta(seconds=30)
MAX_WAIT: Final = timedelta(hours=1)
RETRY_JITTER: Final = (0.1, 0.4)


@dataclass(frozen=True, slots=True)
class SessionParts:
    """What every session of the process shares."""

    tokens: GrantTokens
    guards: ProviderGuards
    http: httpx.AsyncClient
    metrics: ConnectorsMetrics
    tracer: Tracer


@dataclass(frozen=True, slots=True)
class SessionTarget:
    """Whose grant a session acts with, and the provider's rules."""

    scope: TenancyScope
    connection: ConnectionView
    grant_id: UUID
    descriptor: ProviderDescriptor


def retry_after(response: httpx.Response) -> timedelta:
    """The wait a provider named, in seconds or as a date; 30 seconds when it named none."""
    value = response.headers.get("Retry-After", "").strip()
    if value.isdigit():
        wait = timedelta(seconds=int(value))
    else:
        try:
            wait = parsedate_to_datetime(value) - datetime.now(UTC)
        except TypeError, ValueError:
            wait = DEFAULT_WAIT
    return min(max(wait, timedelta(seconds=1)), MAX_WAIT)


class AuthorizedSession:
    """The `ProviderSession` of one connection."""

    def __init__(self, parts: SessionParts, target: SessionTarget) -> None:
        self._parts = parts
        self._target = target

    @property
    def connection(self) -> ConnectionView:
        """The connection this session acts for."""
        return self._target.connection

    async def request(self, call: ProviderCall) -> ProviderResponse:
        """One call with the connection's token; refusals and outages raise."""
        if not OPERATION.fullmatch(call.operation) or urlsplit(call.url).scheme != "https":
            message = "вызов провайдера: имя операции «срез.действие», адрес — HTTPS"
            raise ValueError(message)
        target, parts = self._target, self._parts
        subjects = {
            LimitSubject.APPLICATION: target.descriptor.client_key,
            LimitSubject.ACCOUNT: str(target.grant_id),
            LimitSubject.CONNECTION: str(target.connection.id),
        }
        started = time.monotonic()
        outcome = "unavailable"
        with parts.tracer.start_as_current_span("connectors.provider.call") as span:
            span.set_attribute("connectors.provider", target.descriptor.provider.value)
            span.set_attribute("connectors.operation", call.operation)
            try:
                await parts.guards.admit(target.descriptor, subjects)
                async with parts.guards.slot(target.descriptor, str(target.grant_id)):
                    response = await self._authorized(call)
                outcome = f"{response.status_code // 100}xx"
                span.set_attribute("http.response.status_code", response.status_code)
                if near_quota(response.headers):
                    parts.metrics.quota_near(target.descriptor.provider)
                return ProviderResponse(
                    response.status_code, dict(response.headers), response.content
                )
            except ProviderBusyError:
                outcome = "busy"
                raise
            except NeedsReconnectError:
                outcome = "needs_reconnect"
                raise
            finally:
                seconds = time.monotonic() - started
                parts.metrics.called(target.descriptor.provider, call.operation, outcome, seconds)

    async def _authorized(self, call: ProviderCall) -> httpx.Response:
        tokens, target = self._parts.tokens, self._target
        token = await tokens.access(target.scope, target.grant_id)
        response = await self._sent(call, token)
        if response.status_code == HTTP_UNAUTHORIZED:
            token = await tokens.access(target.scope, target.grant_id, refused=token)
            response = await self._sent(call, token)
            if response.status_code == HTTP_UNAUTHORIZED:
                await tokens.revoked_at_provider(target.scope, target.grant_id)
                raise NeedsReconnectError(Problem.GRANT_REVOKED)
        if response.status_code == HTTP_TOO_MANY or (
            response.status_code == HTTP_UNAVAILABLE and "Retry-After" in response.headers
        ):
            wait = retry_after(response)
            await self._parts.guards.cool_down(target.descriptor, str(target.grant_id), wait)
            raise ProviderBusyError(int(wait.total_seconds()))
        return response

    async def _sent(self, call: ProviderCall, token: SecretStr) -> httpx.Response:
        descriptor = self._target.descriptor
        headers = {
            **(call.headers or {}),
            "Authorization": f"{descriptor.auth_scheme} {token.get_secret_value()}",
            "Accept": (call.headers or {}).get("Accept", "application/json"),
        }
        timeout = httpx.Timeout(
            descriptor.timeouts.read.total_seconds(),
            connect=descriptor.timeouts.connect.total_seconds(),
        )
        attempts = 2 if call.method.upper() in SAFE else 1
        for attempt in range(1, attempts + 1):
            try:
                response = await self._parts.http.request(
                    call.method, call.url, params=call.params, json=call.json_body,
                    headers=headers, timeout=timeout,
                )  # fmt: skip
            except httpx.TransportError:
                await self._parts.guards.provider_failed(descriptor)
                if attempt == attempts:
                    raise ProviderUnavailableError from None
            else:
                if response.status_code not in SERVER_ERRORS or (
                    response.status_code == HTTP_UNAVAILABLE and "Retry-After" in response.headers
                ):
                    return response
                await self._parts.guards.provider_failed(descriptor)
                if attempt == attempts:
                    raise ProviderUnavailableError
            await asyncio.sleep(secrets.SystemRandom().uniform(*RETRY_JITTER))
        raise ProviderUnavailableError
