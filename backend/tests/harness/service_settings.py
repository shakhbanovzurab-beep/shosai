"""Test settings of the shared services: Valkey, the Redis cache and the bucket (ADR 0009).

A run's slot `N` is the database index `N` of Valkey and of the cache — development uses
0, so the addresses are given without an index and the harness adds it — and the prefix
`tests/slot-<N>/` of the one bucket. The bucket may be the development one: tests write
only under their prefix and empty it after every test (ADR 0009, item 2 as amended).
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Final, Self
from urllib.parse import urlsplit

from pydantic import SecretStr, ValidationError

from shosai.core.config.sections import StorageSettings

VALKEY_VARIABLE: Final = "TEST_VALKEY_URL"
REDIS_CACHE_VARIABLE: Final = "TEST_REDIS_CACHE_URL"
STORAGE_PREFIX: Final = "TEST_"
STORAGE_FIELDS: Final = tuple(StorageSettings.model_fields)
REDIS_SCHEMES: Final = frozenset({"redis", "rediss"})
MISSING_ERROR_TYPE: Final = "missing"


def storage_variable(name: str) -> str:
    """`s3_bucket` → `TEST_S3_BUCKET`."""
    return f"{STORAGE_PREFIX}{name.upper()}"


@dataclass(frozen=True, slots=True)
class RedisTarget:
    """A Redis-protocol server without a database index; the slot chooses the index."""

    variable: str
    host: str
    url: str = field(repr=False)

    def for_slot(self, slot: int) -> SecretStr:
        """The address with the slot's database index: `redis://…:16379` → `…:16379/<slot>`."""
        return SecretStr(urlsplit(self.url)._replace(path=f"/{slot}").geturl())


@dataclass(frozen=True, slots=True)
class ServiceTargets:
    """Valkey, the cache and the bucket of the test runs."""

    valkey: RedisTarget
    cache: RedisTarget
    storage: StorageSettings

    @classmethod
    def read(cls, environ: Mapping[str, str], problems: list[str]) -> Self | None:
        """The targets, or None with every problem appended to `problems`."""
        valkey = _read_redis(environ, VALKEY_VARIABLE, problems)
        cache = _read_redis(environ, REDIS_CACHE_VARIABLE, problems)
        storage = _read_storage(environ, problems)
        if valkey is None or cache is None or storage is None:
            return None
        return cls(valkey=valkey, cache=cache, storage=storage)

    def storage_host(self) -> str:
        """The host of the bucket's endpoint, for the loopback guard."""
        # Адрес IPv6 pydantic отдаёт в скобках, как в URL.
        return (self.storage.s3_endpoint_url.host or "").strip("[]")


def _read_redis(
    environ: Mapping[str, str], variable: str, problems: list[str]
) -> RedisTarget | None:
    url = environ.get(variable)
    if not url:
        problems.append(f"{variable}: не задана")
        return None
    parts = urlsplit(url)
    if parts.scheme not in REDIS_SCHEMES or not parts.hostname:
        problems.append(f"{variable}: ожидается адрес redis://… или rediss://… с хостом")
        return None
    if parts.path not in {"", "/"} or parts.query or parts.fragment:
        problems.append(f"{variable}: адрес без номера базы и параметров — номер базы задаёт слот")
        return None
    return RedisTarget(variable=variable, host=parts.hostname, url=url)


def _read_storage(environ: Mapping[str, str], problems: list[str]) -> StorageSettings | None:
    values = {
        name: environ[storage_variable(name)]
        for name in STORAGE_FIELDS
        if environ.get(storage_variable(name))
    }
    try:
        return StorageSettings.model_validate(values)
    except ValidationError as error:
        for item in error.errors(include_url=False, include_input=False, include_context=False):
            name = str(item["loc"][0]) if item["loc"] else ""
            reason = "не задана" if item["type"] == MISSING_ERROR_TYPE else item["msg"]
            problems.append(f"{storage_variable(name)}: {reason}")
        return None
