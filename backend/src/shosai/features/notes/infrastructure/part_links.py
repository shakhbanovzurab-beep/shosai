"""A recording's part sent on to the bucket by its presigned link, as it arrives (step 11).

The API does not hold a part: the request's body goes to the bucket's link for that part
chunk by chunk, with the length the client declared, so a part costs the process a chunk,
not 10 MiB. At most sixteen parts go at once per process; a part that waits over ten
seconds for its turn is 503 `parts_busy` and the client sends it again. The bucket's
refusal of a part is `StorageRejectedError`, its silence `StorageUnavailableError`.
"""

import asyncio
from collections.abc import AsyncIterator
from http import HTTPStatus
from typing import Final

import httpx
import structlog

from shosai.core.kernel.errors import AppError
from shosai.core.storage.errors import StorageRejectedError, StorageUnavailableError
from shosai.core.storage.port import PresignedRequest

PARTS_AT_ONCE: Final = 16
TURN_WAIT_SECONDS: Final = 10.0
# Часть в 5 МиБ на медленной сети клиента едет минутами: запись в бакет ждёт его байтов.
TIMEOUT: Final = httpx.Timeout(connect=10.0, read=60.0, write=300.0, pool=10.0)
log = structlog.stdlib.get_logger(__name__)

type PartBody = AsyncIterator[bytes] | bytes


def part_client() -> httpx.AsyncClient:
    """The process's client of the bucket's part links: no key travels, the link is signed."""
    return httpx.AsyncClient(
        timeout=TIMEOUT,
        limits=httpx.Limits(max_connections=PARTS_AT_ONCE, max_keepalive_connections=4),
    )


class PartLinks:
    """Sends parts to their presigned links, a bounded number at once."""

    def __init__(self, http: httpx.AsyncClient) -> None:
        self._http = http
        self._turns = asyncio.Semaphore(PARTS_AT_ONCE)

    async def send(self, link: PresignedRequest, body: PartBody) -> None:
        """Send the part's body to its link."""
        try:
            await asyncio.wait_for(self._turns.acquire(), TURN_WAIT_SECONDS)
        except TimeoutError:
            log.warning("Часть записи не дождалась очереди к бакету")
            raise AppError("parts_busy", HTTPStatus.SERVICE_UNAVAILABLE) from None
        try:
            answer = await self._http.request(
                link.method, link.url, headers=dict(link.headers), content=body
            )
        except httpx.TransportError as error:
            log.warning("Бакет не принял часть записи", error_type=type(error).__name__)
            raise StorageUnavailableError from error
        finally:
            self._turns.release()
        if answer.status_code >= 500:
            log.warning("Бакет не принял часть записи", status=answer.status_code)
            raise StorageUnavailableError
        if answer.status_code >= 400:
            raise StorageRejectedError(f"HTTP {answer.status_code}")
