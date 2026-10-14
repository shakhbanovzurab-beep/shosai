"""Distributed locks in Valkey: a token with a TTL, released only by its holder.

`SET key token NX PX ttl` takes a lock; release and extension compare the token inside
one Lua script, so a holder whose lock has expired never deletes or prolongs the lock of
the next holder. A lock lives only for its TTL: long work extends it in time or stops.

When Valkey does not answer within 50 ms (§4.3), the caller's policy decides, and the
caller must state it (draft lesson: a fail-open leader lock risked double charges):
fail closed — `LockUnavailableError`, the guarded work does not run; fail open — the work
runs unguarded, for jobs where a second concurrent run is harmless. A deadline does not
cancel a command Valkey already took: after a timed-out `SET` the caller takes its own
token's lock back, or a lock without a holder would stand for its whole TTL.
"""

import asyncio
import contextlib
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta
from enum import StrEnum
from typing import Final

from redis.asyncio import Redis

from shosai.core.kv.connection import REDIS_FAILURES
from shosai.core.kv.keys import build_key
from shosai.core.kv.metrics import KeyValueMetrics
from shosai.core.observability.outage_log import OutageLog

LOCK_DEADLINE: Final = timedelta(milliseconds=50)
TOKEN_BYTES: Final = 16
RELEASE_SCRIPT: Final = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
  return redis.call('DEL', KEYS[1])
end
return 0
"""
EXTEND_SCRIPT: Final = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
  return redis.call('PEXPIRE', KEYS[1], ARGV[2])
end
return 0
"""


class LockOutagePolicy(StrEnum):
    """What a lock operation does when Valkey does not answer in time."""

    FAIL_CLOSED = "fail_closed"
    FAIL_OPEN = "fail_open"


class LockUnavailableError(Exception):
    """Valkey did not answer a fail-closed lock operation; the guarded work must not go on."""


def lock_milliseconds(ttl: timedelta) -> int:
    """A lock TTL in whole milliseconds; a TTL under one millisecond is a mistake."""
    milliseconds = int(ttl / timedelta(milliseconds=1))
    if milliseconds < 1:
        message = "время жизни блокировки — не меньше 1 мс"
        raise ValueError(message)
    return milliseconds


class LockLease:
    """A held lock. Unguarded when Valkey was out and the policy let the work run anyway."""

    def __init__(
        self, locks: DistributedLocks, key: str, token: str | None, policy: LockOutagePolicy
    ) -> None:
        self._locks = locks
        self._key = key
        self._token = token
        self._policy = policy

    @property
    def guarded(self) -> bool:
        """Whether Valkey actually holds the lock for this lease."""
        return self._token is not None

    async def extend(self, ttl: timedelta) -> bool:
        """Make the lock live `ttl` from now; False when it expired and may have a new holder."""
        if self._token is None:
            return True
        return await self._locks.extend(self._key, self._token, ttl, self._policy)


class DistributedLocks:
    """Named locks shared by every process; slices receive the instance by injection."""

    def __init__(self, client: Redis, metrics: KeyValueMetrics) -> None:
        self._client = client
        self._metrics = metrics
        self._release_script = client.register_script(RELEASE_SCRIPT)
        self._extend_script = client.register_script(EXTEND_SCRIPT)
        self._outages = OutageLog("Valkey не ответил на операцию блокировки")

    @asynccontextmanager
    async def hold(
        self, name: str, *, ttl: timedelta, outage: LockOutagePolicy
    ) -> AsyncIterator[LockLease | None]:
        """The lease of lock `name`, or None while another holder has it; released on exit.

        `outage` is stated by every caller: what to do when Valkey does not answer.
        """
        key = build_key("lock", name)
        token = secrets.token_hex(TOKEN_BYTES)
        acquired = await self._acquire(key, token, ttl, outage)
        if acquired is False:
            yield None
            return
        if acquired is None:
            yield LockLease(self, key, None, outage)
            return
        try:
            yield LockLease(self, key, token, outage)
        finally:
            await self._release(key, token, outage)

    async def extend(self, key: str, token: str, ttl: timedelta, outage: LockOutagePolicy) -> bool:
        """Prolong a lock this process holds; fail closed raises when Valkey is out."""
        try:
            async with asyncio.timeout(LOCK_DEADLINE.total_seconds()):
                extended = await self._extend_script(
                    keys=[key], args=[token, lock_milliseconds(ttl)]
                )
        except REDIS_FAILURES as error:
            self._outage(error, outage, "extend")
            return True
        return int(extended) == 1

    async def _acquire(
        self, key: str, token: str, ttl: timedelta, outage: LockOutagePolicy
    ) -> bool | None:
        """True when taken, False when held elsewhere, None when Valkey was out (fail open)."""
        try:
            async with asyncio.timeout(LOCK_DEADLINE.total_seconds()):
                taken = await self._client.set(key, token, nx=True, px=lock_milliseconds(ttl))
        except REDIS_FAILURES as error:
            if isinstance(error, TimeoutError):
                # Тайм-аут не отменяет SET: замок мог встать, а ответ — опоздать. Без снятия
                # он стоял бы без держателя весь TTL, и остальные пропускали бы работу.
                await self._take_back(key, token)
            self._outage(error, outage, "acquire")
            return None
        return taken is True

    async def _take_back(self, key: str, token: str) -> None:
        """Remove this token's lock if a late SET left it; the outage is counted already."""
        with contextlib.suppress(*REDIS_FAILURES):
            async with asyncio.timeout(LOCK_DEADLINE.total_seconds()):
                await self._release_script(keys=[key], args=[token])

    async def _release(self, key: str, token: str, outage: LockOutagePolicy) -> None:
        """Release the lock; when Valkey is out, it expires by its TTL instead."""
        try:
            async with asyncio.timeout(LOCK_DEADLINE.total_seconds()):
                await self._release_script(keys=[key], args=[token])
        except REDIS_FAILURES as error:
            # Работа уже сделана: ошибка освобождения не делает её неудачной, блокировку
            # снимет TTL. Сбой посчитан и записан в лог.
            self._metrics.count_lock_outage(outage.value)
            self._outages.failed(error, operation="release", policy=outage.value)

    def _outage(self, error: BaseException, outage: LockOutagePolicy, operation: str) -> None:
        """Count and log the failure; fail closed turns it into `LockUnavailableError`."""
        self._metrics.count_lock_outage(outage.value)
        self._outages.failed(error, operation=operation, policy=outage.value)
        if outage is LockOutagePolicy.FAIL_CLOSED:
            raise LockUnavailableError from error
