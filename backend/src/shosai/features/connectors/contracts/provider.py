"""An authorized session on one connection and the errors its calls end with (plan §3.3).

A consumer names each call by an operation (`jira.search`, `gmail.history`): the session's
spans and metrics carry the operation, never the URL, an id or an email. The session keeps
the provider's limits and its `Retry-After` for every process, so a consumer that gets
`ProviderBusyError` waits the time it names; `ProviderUnavailableError` is the provider's
outage; `ProviderRefusedError` a refusal that a retry does not cure. A write is never
retried by the session (draft lesson: a retried 5xx sent a second email).
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from http import HTTPStatus
from typing import Final, Protocol

from shosai.core.kernel.errors import PARAM_TEXT, AppError

MAX_RETRY_AFTER_SECONDS: Final = 3600


@dataclass(frozen=True, slots=True)
class ProviderResponse:
    """A provider's answer to one call."""

    status: int
    headers: Mapping[str, str]
    body: bytes

    def json(self) -> object:
        """The body as JSON; `ProviderRefusedError` when it is not JSON."""
        try:
            return json.loads(self.body)
        except ValueError:
            raise ProviderRefusedError(self.status) from None


@dataclass(frozen=True, slots=True)
class ProviderCall:
    """One call a consumer makes: the operation names it in spans and metrics."""

    method: str
    operation: str
    url: str
    params: Mapping[str, str] | None = None
    json_body: object | None = None
    headers: Mapping[str, str] | None = None


class ProviderSession(Protocol):
    """One connection's authorized client, for the time of one request or task."""

    async def request(self, call: ProviderCall) -> ProviderResponse:
        """One call with the connection's token; refusals and outages raise."""
        ...


class ProviderBusyError(AppError):
    """The provider asked Shosai to wait; every process waits the same time."""

    def __init__(self, retry_after_seconds: int) -> None:
        wait = max(1, min(retry_after_seconds, MAX_RETRY_AFTER_SECONDS))
        super().__init__(
            "provider_busy", HTTPStatus.SERVICE_UNAVAILABLE, params={"retry_after_seconds": wait}
        )
        self.retry_after_seconds = wait


class ProviderUnavailableError(AppError):
    """The provider did not answer, answered 5xx, or its breaker is open."""

    def __init__(self) -> None:
        super().__init__("provider_unavailable", HTTPStatus.SERVICE_UNAVAILABLE)


class ProviderRefusedError(AppError):
    """The provider refused the call for a reason a retry does not cure."""

    def __init__(self, provider_status: int, provider_code: str | None = None) -> None:
        params: dict[str, int | str] = {"provider_status": provider_status}
        if provider_code is not None and PARAM_TEXT.fullmatch(provider_code):
            params["provider_code"] = provider_code
        super().__init__("provider_refused", HTTPStatus.BAD_GATEWAY, params=params)
        self.provider_status = provider_status
        self.provider_code = provider_code
