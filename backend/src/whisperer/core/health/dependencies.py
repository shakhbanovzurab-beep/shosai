"""Probes of the shared services of the plane: Valkey, the cache and the one bucket."""

from redis.asyncio import Redis

from whisperer.core.health.probes import DependencyProbe
from whisperer.core.kv.connection import REDIS_FAILURES
from whisperer.core.storage.errors import StorageRejectedError, StorageUnavailableError
from whisperer.core.storage.port import ObjectStorage


def redis_probe(name: str, client: Redis) -> DependencyProbe:
    """`PING` to a Redis-protocol server: Valkey or the cache."""
    return DependencyProbe(name=name, check=client.ping, failures=REDIS_FAILURES)


def storage_probe(storage: ObjectStorage) -> DependencyProbe:
    """`HeadBucket` on the one bucket: reachable, and the credentials still open it."""
    return DependencyProbe(
        name="storage",
        check=storage.ping,
        failures=(StorageUnavailableError, StorageRejectedError),
    )
