"""The shared services over the run's slot: Valkey and cache databases, the buckets' prefix.

Slot `N` is database `N` of Valkey and of the cache and the prefix `tests/slot-<N>/` of
each home's bucket (ADR 0009, item 4; ADR 0044). A client opens once per run, when the
first test asks, and first empties what a crashed run left there. A test that writes takes
`valkey`, `redis_cache`, `buckets` (both homes) or `bucket` (the Russian home's): each
empties the slot's part after the test. At the end of the run the slot must be empty, or
the run fails.
"""

from collections.abc import AsyncIterator, Mapping
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

import pytest
import pytest_asyncio
from redis.asyncio import Redis

from shosai.core.kernel.homes import Home
from shosai.core.kv.connection import connect_redis
from shosai.core.storage.s3_client import open_s3_client
from tests.harness.run_slot import RunSlot
from tests.harness.service_settings import RedisTarget
from tests.harness.settings import HarnessSettings

if TYPE_CHECKING:
    from types_aiobotocore_s3 import S3Client
    from types_aiobotocore_s3.type_defs import ObjectIdentifierTypeDef

CLIENT_NAME: Final = "shosai-tests"


@dataclass(frozen=True, slots=True)
class SlotBucket:
    """The run's prefix in a home's bucket and a raw client to inspect what tests stored."""

    home: Home
    client: S3Client
    bucket: str
    root: str

    async def empty(self) -> int:
        """Delete every object and abort every upload under the prefix; return how many."""
        return await self._delete_objects() + await self._abort_uploads()

    async def _delete_objects(self) -> int:
        removed = 0
        while True:
            page = await self.client.list_objects_v2(Bucket=self.bucket, Prefix=self.root)
            keys: list[ObjectIdentifierTypeDef] = [
                {"Key": item["Key"]} for item in page.get("Contents", [])
            ]
            if not keys:
                return removed
            await self.client.delete_objects(
                Bucket=self.bucket, Delete={"Objects": keys, "Quiet": True}
            )
            removed += len(keys)

    async def _abort_uploads(self) -> int:
        removed = 0
        while True:
            page = await self.client.list_multipart_uploads(Bucket=self.bucket, Prefix=self.root)
            uploads = page.get("Uploads", [])
            if not uploads:
                return removed
            for upload in uploads:
                await self.client.abort_multipart_upload(
                    Bucket=self.bucket, Key=upload["Key"], UploadId=upload["UploadId"]
                )
            removed += len(uploads)


@asynccontextmanager
async def slot_database(target: RedisTarget, slot: int) -> AsyncIterator[Redis]:
    """A client of the slot's database; emptied at start, checked empty at the end."""
    client = connect_redis(target.for_slot(slot), CLIENT_NAME)
    try:
        await client.flushdb()
        yield client
        left = await client.dbsize()
        await client.flushdb()
        if left:
            pytest.fail(
                f"{target.variable}: в базе слота {slot} остались ключи: {left}", pytrace=False
            )
    finally:
        await client.aclose()


@pytest_asyncio.fixture(scope="session")
async def valkey_server(
    run_slot: RunSlot, harness_settings: HarnessSettings
) -> AsyncIterator[Redis]:
    """Valkey's database of the run's slot, for the whole run."""
    async with slot_database(harness_settings.services.valkey, run_slot.claimed.number) as client:
        yield client


@pytest_asyncio.fixture(scope="session")
async def cache_server(
    run_slot: RunSlot, harness_settings: HarnessSettings
) -> AsyncIterator[Redis]:
    """The cache's database of the run's slot, for the whole run."""
    async with slot_database(harness_settings.services.cache, run_slot.claimed.number) as client:
        yield client


@pytest_asyncio.fixture(scope="session")
async def slot_buckets(
    run_slot: RunSlot, harness_settings: HarnessSettings
) -> AsyncIterator[Mapping[Home, SlotBucket]]:
    """The run's prefix in each home's bucket; emptied at start and checked empty at the end."""
    root = f"tests/slot-{run_slot.claimed.number}/"
    async with AsyncExitStack() as clients:
        buckets: dict[Home, SlotBucket] = {}
        for home, storage in harness_settings.services.storage.items():
            client = await clients.enter_async_context(open_s3_client(storage))
            buckets[home] = SlotBucket(home, client, storage.s3_bucket, root)
            await buckets[home].empty()
        yield buckets
        left = {home: await bucket.empty() for home, bucket in buckets.items()}
        if any(left.values()):
            pytest.fail(f"в бакетах домов под {root} остались объекты: {left}", pytrace=False)


@pytest_asyncio.fixture
async def valkey(valkey_server: Redis) -> AsyncIterator[Redis]:
    """Valkey for a test that writes; the slot's database is emptied after it."""
    try:
        yield valkey_server
    finally:
        await valkey_server.flushdb()


@pytest_asyncio.fixture
async def redis_cache(cache_server: Redis) -> AsyncIterator[Redis]:
    """The cache for a test that writes; the slot's database is emptied after it."""
    try:
        yield cache_server
    finally:
        await cache_server.flushdb()


@pytest_asyncio.fixture
async def buckets(
    slot_buckets: Mapping[Home, SlotBucket],
) -> AsyncIterator[Mapping[Home, SlotBucket]]:
    """Both homes' buckets for a test that writes; the run's prefix is emptied after it."""
    try:
        yield slot_buckets
    finally:
        for slot_bucket in slot_buckets.values():
            await slot_bucket.empty()


@pytest.fixture
def bucket(buckets: Mapping[Home, SlotBucket]) -> SlotBucket:
    """The Russian home's bucket, for a test of the adapters; both are emptied after it."""
    return buckets[Home.RU]
