"""The cache port: what a slice may ask of the LRU cache (target architecture §4.2, §7).

The cache is never a source of truth: every entry can be rebuilt from PostgreSQL, so an
unavailable cache is a miss and the caller reads the source. Every entry has a TTL, the
upper bound of staleness when an invalidation does not arrive. Access rights are never
cached (§7): content may be, the right to see it is checked on every access.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol

from shosai.core.kv.keys import build_key, check_key_part


@dataclass(frozen=True, slots=True)
class CacheKey:
    """One entry: a namespace declared by a slice and an id-like name inside it.

    The namespace is a metric label, so it is a fixed code; it carries the version of the
    value's shape (`directory.v1`), and a new shape takes a new namespace instead of
    reading entries written by the previous release.
    """

    namespace: str
    name: str

    def __post_init__(self) -> None:
        check_key_part(self.namespace)
        check_key_part(self.name)

    def render(self) -> str:
        """The server key: `shosai:cache:<namespace>:<name>`."""
        return build_key("cache", self.namespace, self.name)


class Cache(Protocol):
    """Bytes under keys with a TTL; any failure of the cache reads as a miss."""

    async def get(self, key: CacheKey) -> bytes | None:
        """The cached value, or None on a miss or when the cache does not answer."""
        ...

    async def get_many(self, keys: Sequence[CacheKey]) -> list[bytes | None]:
        """The values in the order of `keys`, None for each miss; one round trip."""
        ...

    async def set(self, key: CacheKey, value: bytes, ttl: timedelta) -> None:
        """Store a value for at most `ttl`; a failure is logged and counted, never raised."""
        ...

    async def delete(self, *keys: CacheKey) -> None:
        """Forget entries after their source changed; if this fails, the TTL bounds staleness."""
        ...
