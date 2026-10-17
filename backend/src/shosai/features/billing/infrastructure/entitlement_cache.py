"""Entitlement entries in Valkey, guarded by the subscription version and the catalogue mark.

One hash per person holds the entry, its subscription version and a floor: a change
raises the floor and drops the entry before it commits, and an entry is stored only when
its version reaches the floor and its catalogue mark is the current one, both checked in
one script. A reader that saw the database before a change therefore never stores what
it saw after the change. The catalogue mark changes after every committed catalogue edit.
Valkey out of reach is a miss: the reader goes to the database and stores nothing; a
change that could not raise the floor leaves an old entry for at most its TTL.
"""

import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final
from uuid import UUID

import structlog
from redis.asyncio import Redis

from shosai.core.kv.connection import REDIS_FAILURES
from shosai.core.kv.keys import build_key
from shosai.features.billing.application.entitlement_entries import EntitlementEntry
from shosai.features.billing.infrastructure.entitlement_codec import decode, encode

READ_DEADLINE: Final = timedelta(milliseconds=50)
WRITE_DEADLINE: Final = timedelta(milliseconds=200)
# Запись живёт не дольше этого: потерянное повышение пола устаревает за этот срок.
ENTRY_TTL: Final = timedelta(minutes=10)
# Пол переживает медленного читателя и откат изменения, после которого запись не кешируется.
FLOOR_TTL: Final = timedelta(hours=1)
CATALOGUE_KEY: Final = build_key("billing", "catalogue_mark")
STORE_SCRIPT: Final = """
if redis.call('GET', KEYS[2]) ~= ARGV[1] then return 0 end
local floor = tonumber(redis.call('HGET', KEYS[1], 'floor') or '0')
local held = tonumber(redis.call('HGET', KEYS[1], 'version') or '-1')
local version = tonumber(ARGV[2])
if version < floor or version < held then return 0 end
redis.call('HSET', KEYS[1], 'version', ARGV[2], 'entry', ARGV[3])
if redis.call('TTL', KEYS[1]) < tonumber(ARGV[4]) then
  redis.call('EXPIRE', KEYS[1], ARGV[4])
end
return 1
"""
RAISE_FLOOR_SCRIPT: Final = """
local floor = tonumber(redis.call('HGET', KEYS[1], 'floor') or '0')
if tonumber(ARGV[1]) > floor then redis.call('HSET', KEYS[1], 'floor', ARGV[1]) end
redis.call('HDEL', KEYS[1], 'entry', 'version')
redis.call('EXPIRE', KEYS[1], ARGV[2])
return 1
"""

log = structlog.stdlib.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class CacheReading:
    """What Valkey holds for a person: the entry and the current catalogue mark."""

    entry: EntitlementEntry | None
    catalogue: str | None


def entry_key(user_id: UUID) -> str:
    """The person's hash."""
    return build_key("billing", "entitlement.v1", user_id.hex)


class EntitlementCache:
    """Entries by person in Valkey; every failure reads as a miss and is logged."""

    def __init__(self, valkey: Redis) -> None:
        self._valkey = valkey

    async def read(self, user_id: UUID) -> CacheReading:
        """The person's entry and the catalogue mark, in one round trip."""
        try:
            async with asyncio.timeout(READ_DEADLINE.total_seconds()):
                async with self._valkey.pipeline(transaction=False) as pipe:
                    await pipe.hmget(entry_key(user_id), ["floor", "version", "entry"])
                    await pipe.get(CATALOGUE_KEY)
                    (floor, version, raw), mark = await pipe.execute()
        except REDIS_FAILURES:
            log.warning("Снимок прав не прочитан из Valkey: читаем базу")
            return CacheReading(None, None)
        catalogue = None if mark is None else _text(mark)
        if raw is None or version is None or int(version) < int(floor or 0):
            return CacheReading(None, catalogue)
        try:
            return CacheReading(decode(raw), catalogue)
        except ValueError:
            log.warning("Снимок прав в Valkey не разобран: читаем базу")
            return CacheReading(None, catalogue)

    async def catalogue_mark(self, known: str | None) -> str | None:
        """The current catalogue mark, set when Valkey has none; None when Valkey is silent."""
        if known is not None:
            return known
        fresh = uuid.uuid4().hex
        try:
            async with asyncio.timeout(WRITE_DEADLINE.total_seconds()):
                previous = await self._valkey.set(CATALOGUE_KEY, fresh, nx=True, get=True)
        except REDIS_FAILURES:
            log.warning("Метка каталога не прочитана: снимок прав не кешируется")
            return None
        return fresh if previous is None or isinstance(previous, bool) else _text(previous)

    async def store(self, entry: EntitlementEntry, now: datetime) -> bool:
        """Keep the entry unless a newer version or another catalogue came first."""
        ttl = ENTRY_TTL if entry.valid_until is None else min(ENTRY_TTL, entry.valid_until - now)
        seconds = int(ttl.total_seconds())
        if not entry.catalogue or seconds < 1:
            return False
        keep = max(seconds, int(FLOOR_TTL.total_seconds()))
        args = (entry.catalogue, str(entry.snapshot.version), encode(entry), str(keep))
        try:
            async with asyncio.timeout(WRITE_DEADLINE.total_seconds()):
                stored = await self._valkey.eval(
                    STORE_SCRIPT, 2, entry_key(entry.snapshot.user_id), CATALOGUE_KEY, *args
                )
        except REDIS_FAILURES:
            log.warning("Снимок прав не записан в Valkey")
            return False
        return bool(stored)

    async def raise_floor(self, user_id: UUID, version: int) -> bool:
        """Before a change commits: drop the entry and refuse any older one from now on."""
        seconds = str(int(FLOOR_TTL.total_seconds()))
        try:
            async with asyncio.timeout(WRITE_DEADLINE.total_seconds()):
                await self._valkey.eval(
                    RAISE_FLOOR_SCRIPT, 1, entry_key(user_id), str(version), seconds
                )
        except REDIS_FAILURES:
            log.warning("Пол версии прав не поднят: старый снимок живёт до своего срока")
            return False
        return True

    async def catalogue_changed(self) -> None:
        """After a catalogue edit commits: every entry built on the old catalogue stops."""
        try:
            async with asyncio.timeout(WRITE_DEADLINE.total_seconds()):
                await self._valkey.set(CATALOGUE_KEY, uuid.uuid4().hex)
        except REDIS_FAILURES:
            log.warning("Метка каталога не сменилась: снимки прав живут до своего срока")


def _text(value: bytes | str) -> str:
    return value.decode("ascii") if isinstance(value, bytes) else value
