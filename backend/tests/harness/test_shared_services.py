"""The run's slot in Valkey, the cache and the bucket is emptied, and a leftover fails the run."""

import pytest

from tests.harness.run_slot import RunSlot
from tests.harness.service_settings import RedisTarget
from tests.harness.settings import HarnessSettings
from tests.harness.shared_services import SlotBucket, slot_database


async def leave_two_keys(target: RedisTarget, slot: int) -> None:
    async with slot_database(target, slot) as client:
        await client.set("whisperer:probe:left", "1")
        await client.set("whisperer:probe:also", "1")


async def test_a_slot_database_left_with_keys_fails_the_run(
    harness_settings: HarnessSettings, run_slot: RunSlot
) -> None:
    target = harness_settings.services.cache

    with pytest.raises(pytest.fail.Exception, match="остались ключи: 2"):
        await leave_two_keys(target, run_slot.claimed.number)

    async with slot_database(target, run_slot.claimed.number) as client:
        assert await client.dbsize() == 0


async def test_emptying_the_prefix_removes_objects_and_pending_uploads(
    bucket: SlotBucket,
) -> None:
    for name in ("a.txt", "b/c.txt"):
        await bucket.client.put_object(Bucket=bucket.bucket, Key=bucket.root + name, Body=b"x")
    await bucket.client.create_multipart_upload(Bucket=bucket.bucket, Key=bucket.root + "d.webm")

    assert await bucket.empty() == 3

    listed = await bucket.client.list_objects_v2(Bucket=bucket.bucket, Prefix=bucket.root)
    uploads = await bucket.client.list_multipart_uploads(Bucket=bucket.bucket, Prefix=bucket.root)
    assert listed.get("Contents", []) == []
    assert uploads.get("Uploads", []) == []
