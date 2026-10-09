"""The shared services over the run's slot: Valkey and cache databases, the bucket prefix.

Slot `N` is database `N` of Valkey and of the cache and the prefix `tests/slot-<N>/` of
the bucket (ADR 0009, item 4). A client opens once per run, when the first test asks, and
first empties what a crashed run left there. A test that writes takes `valkey`,
`redis_cache` or `bucket`: each empties the slot's part after the test. At the end of the
run the slot must be empty, or the run fails.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

import pytest
import pytest_asyncio
from redis.asyncio import Redis

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
    """The run's prefix in the bucket and a raw client to inspect what tests stored."""

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
async def slot_bucket(
    run_slot: RunSlot, harness_settings: HarnessSettings
) -> AsyncIterator[SlotBucket]:
    """The run's prefix in the bucket; emptied at start and checked empty at the end."""
    storage = harness_settings.services.storage
    async with open_s3_client(storage) as client:
        bucket = SlotBucket(client, storage.s3_bucket, f"tests/slot-{run_slot.claimed.number}/")
        await bucket.empty()
        yield bucket
        left = await bucket.empty()
        if left:
            pytest.fail(f"в бакете под {bucket.root} остались объекты: {left}", pytrace=False)


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
async def bucket(slot_bucket: SlotBucket) -> AsyncIterator[SlotBucket]:
    """The bucket for a test that writes; the run's prefix is emptied after it."""
    try:
        yield slot_bucket
    finally:
        await slot_bucket.empty()
