"""The engine's parts: the versions in force, Jev's zero-retention status, the settings and the
state hash's key (decisions plan §3.3, ADR 0069 DL-D1)."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import cast

import httpx
import pytest
from prometheus_client import CollectorRegistry
from pydantic import SecretStr, ValidationError
from redis.asyncio import Redis

from shosai.core.config.sections import CryptoSettings
from shosai.core.kernel.homes import Home
from shosai.core.tasks.payloads import HomeTaskPayload
from shosai.features.decisions.application.in_force import (
    PoliciesInForce,
    PoliciesUnreadableError,
    StoredPolicy,
)
from shosai.features.decisions.channels.tasks import zero_retention_check
from shosai.features.decisions.domain.policies import policies_by_key
from shosai.features.decisions.domain.policies.action_friction import ACTION_FRICTION
from shosai.features.decisions.infrastructure.provider_terms import ProviderTerms, status_key
from shosai.features.decisions.infrastructure.state_key import state_hash_key
from shosai.features.decisions.settings import DecisionsSettings
from tests.features.decisions.engine_bench import FRICTION_CUTS, stored

FERNET = "kTzAkBJRvNWYrS3RMbQ2-K5pL2dFvAo9ZtmYQpOn5wQ="
JEV = "typesafe/jev-1.13"


@dataclass
class FlakyStore:
    """Stored versions that a test can make unreadable."""

    stored: list[StoredPolicy] = field(default_factory=list)
    broken: bool = False
    reads: int = 0

    async def in_force(self) -> Sequence[StoredPolicy]:
        """The stored versions, or the store's failure."""
        self.reads += 1
        if self.broken:
            raise PoliciesUnreadableError("down")
        return list(self.stored)


@dataclass
class Clock:
    """Monotonic time a test moves."""

    now: float = 100.0

    def __call__(self) -> float:
        """The reading."""
        return self.now


async def test_versions_are_read_once_a_minute_and_the_last_good_copy_survives() -> None:
    store, clock = FlakyStore([stored(ACTION_FRICTION, "active", FRICTION_CUTS)]), Clock()
    in_force = PoliciesInForce(store, policies_by_key(), clock)

    first = await in_force.of("action.friction")
    clock.now += 30
    await in_force.of("action.friction")
    store.broken, clock.now = True, clock.now + 31
    kept = await in_force.of("action.friction")

    assert store.reads == 2
    assert first.active is not None
    assert kept.active is not None
    assert kept.active.policy is ACTION_FRICTION


async def test_with_nothing_ever_read_no_policy_is_in_force() -> None:
    in_force = PoliciesInForce(FlakyStore(broken=True), policies_by_key(), Clock())

    versions = await in_force.of("action.friction")

    assert (versions.active, versions.shadow) == (None, None)


@pytest.mark.parametrize(
    "row",
    [
        StoredPolicy("action.friction", 1, "active", 1, "0" * 16, FRICTION_CUTS),
        StoredPolicy("action.friction", 9, "active", 1, ACTION_FRICTION.digest(), FRICTION_CUTS),
        stored(ACTION_FRICTION, "active", {"matches": FRICTION_CUTS["matches"]}),
    ],
    ids=["other wording", "unknown version", "a cut missing"],
)
async def test_a_version_this_code_cannot_judge_with_is_not_in_force(row: StoredPolicy) -> None:
    in_force = PoliciesInForce(FlakyStore([row]), policies_by_key(), Clock())

    assert (await in_force.of("action.friction")).active is None


@dataclass
class Valkey:
    """The two Valkey commands the status needs, in memory."""

    values: dict[str, bytes] = field(default_factory=dict)
    ttls: dict[str, int] = field(default_factory=dict)
    failing: bool = False

    async def get(self, key: str) -> bytes | None:
        """A stored value."""
        if self.failing:
            raise ConnectionError(key)
        return self.values.get(key)

    async def set(self, key: str, value: bytes, *, ex: int) -> None:
        """Store a value with its time to live."""
        self.values[key], self.ttls[key] = value, ex


def terms(valkey: Valkey, clock: Clock | None = None) -> ProviderTerms:
    """The status over the in-memory Valkey."""
    # Двойнику хватает двух команд Valkey, которые нужны статусу.
    redis = cast("Redis", valkey)
    return ProviderTerms(redis, "typesafe/jev-1.13", CollectorRegistry(), clock or Clock())


async def test_a_fresh_yes_is_kept_three_days_and_read_once_a_minute() -> None:
    valkey, clock = Valkey(), Clock()
    status = terms(valkey, clock)

    assert await status.zero_retention() is False
    await status.record(keeps_nothing=True)
    assert await status.zero_retention() is True
    valkey.values.clear()
    clock.now += 30
    assert await status.zero_retention() is True
    clock.now += 31
    assert await status.zero_retention() is False
    assert valkey.ttls == {status_key("typesafe/jev-1.13"): 3 * 24 * 3600}


async def test_an_unreadable_status_is_no() -> None:
    valkey = Valkey({status_key("typesafe/jev-1.13"): b"1"}, failing=True)

    assert await terms(valkey).zero_retention() is False


def openrouter(zdr: list[dict[str, str]], endpoints: list[dict[str, str]]) -> httpx.AsyncClient:
    """OpenRouter's two public lists as a test sets them."""

    def answer(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/endpoints/zdr"):
            return httpx.Response(200, json={"data": zdr})
        return httpx.Response(
            200, json={"data": {"id": "typesafe/jev-1.13", "endpoints": endpoints}}
        )

    return httpx.AsyncClient(transport=httpx.MockTransport(answer))


# Список нулевого хранения, эндпоинты модели и ожидаемый статус.
CHECKS = {
    "every endpoint listed": ([{"model_id": JEV, "tag": "typesafe"}], [{"tag": "typesafe"}], b"1"),
    "one endpoint off the list": (
        [{"model_id": JEV, "tag": "typesafe"}],
        [{"tag": "typesafe"}, {"tag": "other"}],
        b"0",
    ),
    "another model listed": (
        [{"model_id": "typesafe/jev-1.14", "tag": "typesafe"}],
        [{"tag": "typesafe"}],
        b"0",
    ),
    "no endpoint": ([{"model_id": JEV, "tag": "typesafe"}], [], b"0"),
}


@pytest.mark.parametrize("case", CHECKS.values(), ids=CHECKS.keys())
async def test_the_daily_check_records_whether_every_endpoint_keeps_nothing(
    case: tuple[list[dict[str, str]], list[dict[str, str]], bytes],
) -> None:
    listed, endpoints, expected = case
    valkey = Valkey()
    status = terms(valkey)
    async with openrouter(listed, endpoints) as client:
        await zero_retention_check(client, status, "typesafe/jev-1.13").handle(
            HomeTaskPayload(home=Home.EU)
        )

    assert valkey.values[status_key(JEV)] == expected


async def test_a_check_that_cannot_read_keeps_the_last_status() -> None:
    valkey = Valkey({status_key("typesafe/jev-1.13"): b"1"})
    failing = httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(503)))

    async with failing:
        await zero_retention_check(failing, terms(valkey), "typesafe/jev-1.13").handle(
            HomeTaskPayload(home=Home.EU)
        )

    assert valkey.values == {status_key("typesafe/jev-1.13"): b"1"}


@pytest.mark.parametrize("model", ["~typesafe/jev-latest", "typesafe/jev-latest", "jev"])
def test_an_alias_of_jev_is_refused(model: str) -> None:
    with pytest.raises(ValidationError, match="закреплённая"):
        DecisionsSettings(decisions_jev_model=model)


def test_the_state_hash_key_is_derived_and_absent_without_fernet() -> None:
    key = state_hash_key(CryptoSettings(fernet_key=SecretStr(FERNET)))

    assert key is not None
    assert len(key) == 32
    assert key == state_hash_key(CryptoSettings(fernet_key=SecretStr(FERNET)))
    assert key != FERNET.encode()[:32]
    assert state_hash_key(CryptoSettings()) is None
