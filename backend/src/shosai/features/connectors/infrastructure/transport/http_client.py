"""The process's one HTTP client for every provider call (connectors plan §3.6).

Bounded timeouts, a bounded pool, no redirects followed — a provider's redirect is never a
way to another host — and TLS verified. Each call sets its own deadlines from the provider's
descriptor; nothing here retries.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Final

import httpx

TIMEOUT: Final = httpx.Timeout(15.0, connect=3.0)
LIMITS: Final = httpx.Limits(max_connections=200, max_keepalive_connections=40)
USER_AGENT: Final = "Shosai-Connectors/1"


@asynccontextmanager
async def open_connectors_http() -> AsyncIterator[httpx.AsyncClient]:
    """The connectors' client, closed with the process."""
    async with httpx.AsyncClient(
        timeout=TIMEOUT, limits=LIMITS, follow_redirects=False,
        headers={"User-Agent": USER_AGENT},
    ) as client:  # fmt: skip
        yield client
