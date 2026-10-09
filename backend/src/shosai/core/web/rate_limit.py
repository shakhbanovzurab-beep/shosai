"""The rate-limit dependency of a route (ADR 0011): 429 with the envelope and `Retry-After`.

A slice declares the limit where it builds its router; the limiter comes from composition:

    sign_in = RateLimit("sign_in", rate=5, period=timedelta(minutes=1), burst=5)
    router.post("/v1/auth/login", dependencies=[Depends(rate_limited(limiter, sign_in))])

The subject is the client address by default — uvicorn sets it from `X-Forwarded-For`
only for the trusted proxies — or any dependency returning a key, such as the user id.
WebSocket routes are not limited this way; the WS gateway has its own slot limits.
"""

import math
from collections.abc import Awaitable, Callable
from datetime import timedelta
from http import HTTPStatus
from typing import Annotated, Final

from fastapi import Depends
from starlette.requests import Request

from shosai.core.kernel.errors import AppError, CompatibleDetail
from shosai.core.kv.rate_limits import RateLimit, RateLimiter

# Без адреса клиента (сокет UNIX) запросы делят один счётчик; за edge адрес есть всегда.
UNKNOWN_CLIENT: Final = "unknown"

type RateLimitSubject = Callable[..., str] | Callable[..., Awaitable[str]]


class RateLimitedError(AppError):
    """The subject used up its allowance; the client retries after `Retry-After` seconds."""

    def __init__(self, retry_after: timedelta, detail: CompatibleDetail | None = None) -> None:
        seconds = max(math.ceil(retry_after.total_seconds()), 1)
        super().__init__(
            "rate_limited",
            HTTPStatus.TOO_MANY_REQUESTS,
            params={"retry_after_seconds": seconds},
            detail=detail,
        )


def client_address(request: Request) -> str:
    """The client's IP address as the server resolved it behind the trusted proxies."""
    return request.client.host if request.client is not None else UNKNOWN_CLIENT


def rate_limited(
    limiter: RateLimiter,
    limit: RateLimit,
    subject: RateLimitSubject = client_address,
    *,
    detail: CompatibleDetail | None = None,
) -> Callable[..., Awaitable[None]]:
    """A route dependency that takes one request from the subject's allowance or answers 429.

    `detail` keeps the draft's `detail` on a native route whose contract had one (ADR 0008).
    """

    async def enforce_rate_limit(key: Annotated[str, Depends(subject)]) -> None:
        decision = await limiter.check(limit, key)
        if not decision.allowed:
            raise RateLimitedError(decision.retry_after, detail)

    return enforce_rate_limit
