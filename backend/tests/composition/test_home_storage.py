"""Each home's files go to its own bucket; a bucket out of reach stops only its home (ADR 0044)."""

from collections.abc import Mapping

from shosai.core.health.probes import probe_dependencies
from shosai.core.kernel.homes import Home
from tests.composition.platform_bench import platform_over_slot
from tests.core.kv.outages import closed_port
from tests.harness.run_slot import RunSlot
from tests.harness.settings import HarnessSettings
from tests.harness.shared_services import SlotBucket


async def keys_in(bucket: SlotBucket) -> list[str]:
    """The keys under the run's prefix of a home's bucket."""
    page = await bucket.client.list_objects_v2(Bucket=bucket.bucket, Prefix=bucket.root)
    return [item["Key"] for item in page.get("Contents", [])]


async def test_each_home_writes_only_to_its_own_bucket(
    run_slot: RunSlot, harness_settings: HarnessSettings, buckets: Mapping[Home, SlotBucket]
) -> None:
    root = buckets[Home.RU].root
    async with platform_over_slot(run_slot, harness_settings, ()) as bench:
        objects = bench.platform.services.objects
        for home in Home:
            await objects[home].put(f"{root}u-1/{home.value}.txt", b"x", content_type="text/plain")
        found = await objects[Home.EU].head(f"{root}u-1/ru.txt")

    assert await keys_in(buckets[Home.RU]) == [f"{root}u-1/ru.txt"]
    assert await keys_in(buckets[Home.EU]) == [f"{root}u-1/eu.txt"]
    assert found is None


async def test_a_bucket_out_of_reach_is_down_for_its_home_only(
    run_slot: RunSlot, harness_settings: HarnessSettings
) -> None:
    unreachable = {"HOME_EU_S3_ENDPOINT_URL": f"http://127.0.0.1:{closed_port()}"}
    async with platform_over_slot(run_slot, harness_settings, (), overrides=unreachable) as bench:
        statuses = await probe_dependencies(bench.platform.probes)

    assert statuses["storage.eu"] == "down"
    assert statuses["storage.ru"] == "ok"
    assert statuses["homes.eu"] == "ok"
