"""Failed sign-ins per address and per account: when the captcha is shown (ID-D1).

The draft had no lockout, no per-account throttle and a captcha anyone could skip with a
header. Here three failures in 15 minutes, from a client address or for an account,
make the next sign-in show the captcha, for every client. Counting happens in Valkey; if
it does not answer, the captcha is required (fail closed): the gate holds without it.
"""

import asyncio
import hashlib
from datetime import timedelta
from typing import Final

from redis.asyncio import Redis

from shosai.core.kv.connection import REDIS_FAILURES
from shosai.core.kv.keys import build_key

FAILURES_BEFORE_CAPTCHA: Final = 3
WINDOW: Final = timedelta(minutes=15)
DEADLINE: Final = timedelta(milliseconds=50)
COUNT: Final = """
local count = redis.call('INCR', KEYS[1])
redis.call('EXPIRE', KEYS[1], ARGV[1])
redis.call('INCR', KEYS[2])
redis.call('EXPIRE', KEYS[2], ARGV[1])
return count
"""


class SignInFailures:
    """Counts failures; says whether the captcha is due."""

    def __init__(self, valkey: Redis) -> None:
        self._valkey = valkey

    async def captcha_due(self, address: str, email_hmac: bytes) -> bool:
        """Whether either counter reached three failures in the window."""
        try:
            async with asyncio.timeout(DEADLINE.total_seconds()):
                values = await self._valkey.mget(_address_key(address), _account_key(email_hmac))
        except REDIS_FAILURES:
            return True
        return any(int(value or 0) >= FAILURES_BEFORE_CAPTCHA for value in values)

    async def failed(self, address: str, email_hmac: bytes) -> None:
        """Count one failure for the address and the account; a lost count is harmless."""
        seconds = str(int(WINDOW.total_seconds()))
        try:
            async with asyncio.timeout(DEADLINE.total_seconds()):
                await self._valkey.eval(
                    COUNT, 2, _address_key(address), _account_key(email_hmac), seconds
                )
        except REDIS_FAILURES:
            return

    async def succeeded(self, email_hmac: bytes) -> None:
        """Forget the account's failures after a correct sign-in."""
        try:
            async with asyncio.timeout(DEADLINE.total_seconds()):
                await self._valkey.delete(_account_key(email_hmac))
        except REDIS_FAILURES:
            return


def _address_key(address: str) -> str:
    # В ключ не попадает сам адрес: двоеточия IPv6 не входят в алфавит ключей.
    digest = hashlib.blake2b(address.encode("utf-8"), digest_size=16).hexdigest()
    return build_key("identity", "failures", "address", digest)


def _account_key(email_hmac: bytes) -> str:
    return build_key("identity", "failures", "account", email_hmac.hex())
