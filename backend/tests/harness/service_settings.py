"""Test settings of the shared services: Valkey, the Redis cache, the homes' buckets (ADR 0009).

A run's slot `N` is the database index `N` of Valkey and of the cache — development uses
0, so the addresses are given without an index and the harness adds it — and the prefix
`tests/slot-<N>/` of each home's bucket (ADR 0044). The buckets may be the development
ones: tests write only under their prefix and empty it after every test.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Final, Self
from urllib.parse import urlsplit

from pydantic import SecretStr, ValidationError

from shosai.core.config.sections import StorageSettings, home_prefix
from shosai.core.kernel.homes import Home

VALKEY_VARIABLE: Final = "TEST_VALKEY_URL"
REDIS_CACHE_VARIABLE: Final = "TEST_REDIS_CACHE_URL"
STORAGE_PREFIX: Final = "TEST_"
STORAGE_FIELDS: Final = tuple(StorageSettings.model_fields)
REDIS_SCHEMES: Final = frozenset({"redis", "rediss"})
MISSING_ERROR_TYPE: Final = "missing"


def storage_variable(home: Home, name: str) -> str:
    """`(Home.RU, "s3_bucket")` → `TEST_HOME_RU_S3_BUCKET`."""
    return f"{STORAGE_PREFIX}{home_prefix(home)}{name.upper()}"


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
    """Valkey, the cache and the homes' buckets of the test runs."""

    valkey: RedisTarget
    cache: RedisTarget
    storage: Mapping[Home, StorageSettings]

    @classmethod
    def read(cls, environ: Mapping[str, str], problems: list[str]) -> Self | None:
        """The targets, or None with every problem appended to `problems`."""
        valkey = _read_redis(environ, VALKEY_VARIABLE, problems)
        cache = _read_redis(environ, REDIS_CACHE_VARIABLE, problems)
        storage = {home: _read_storage(environ, home, problems) for home in Home}
        if valkey is None or cache is None:
            return None
        found = {home: section for home, section in storage.items() if section is not None}
        if len(found) != len(storage):
            return None
        return cls(valkey=valkey, cache=cache, storage=found)

    def storage_hosts(self) -> dict[str, str]:
        """The host of each bucket's endpoint by its variable, for the loopback guard."""
        # Адрес IPv6 pydantic отдаёт в скобках, как в URL.
        return {
            storage_variable(home, "s3_endpoint_url"): (section.s3_endpoint_url.host or "").strip(
                "[]"
            )
            for home, section in self.storage.items()
        }


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


def _read_storage(
    environ: Mapping[str, str], home: Home, problems: list[str]
) -> StorageSettings | None:
    values = {
        name: environ[storage_variable(home, name)]
        for name in STORAGE_FIELDS
        if environ.get(storage_variable(home, name))
    }
    try:
        return StorageSettings.model_validate(values)
    except ValidationError as error:
        for item in error.errors(include_url=False, include_input=False, include_context=False):
            name = str(item["loc"][0]) if item["loc"] else ""
            reason = "не задана" if item["type"] == MISSING_ERROR_TYPE else item["msg"]
            problems.append(f"{storage_variable(home, name)}: {reason}")
        return None
