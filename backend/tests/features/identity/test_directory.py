"""The directory: claims, the sign-in cache with its fallback, and the claim sweep (§6)."""

from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from prometheus_client import CollectorRegistry
from redis.asyncio import Redis

from shosai.core.cache.metrics import CacheMetrics
from shosai.core.cache.redis_cache import RedisCache
from shosai.core.db.errors import HomeUnavailableError
from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.ids import new_id
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.identity.application.sweeps import purge_pending, settle_claims
from shosai.features.identity.domain.registration import DirectoryState
from shosai.features.identity.infrastructure import directory as directory_module
from shosai.features.identity.infrastructure.directory import (
    ClaimOutcome,
    Directory,
    DirectoryRecord,
)
from shosai.features.identity.infrastructure.records import PendingRegistration, User
from tests.features.identity.registration_bench import EuUnreachable
from tests.harness.connections import fetch_rows
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot

ADDRESS = bytes(range(32))


def directory(transactions: HomeTransactions, cache: Redis) -> Directory:
    return Directory(transactions, RedisCache(cache, CacheMetrics(CollectorRegistry())))


async def test_the_first_claim_wins_a_repeat_is_ours_and_another_is_refused(
    homes: DatabaseAccess, redis_cache: Redis
) -> None:
    store = directory(homes.transactions, redis_cache)
    first, second = new_id(), new_id()

    won = await store.claim(ADDRESS, first, Home.RU)
    repeated = await store.claim(ADDRESS, first, Home.RU)
    lost = await store.claim(ADDRESS, second, Home.EU)

    assert (won, repeated, lost) == (
        ClaimOutcome.WON,
        ClaimOutcome.ALREADY_OURS,
        ClaimOutcome.TAKEN,
    )
    record = await store.find_fresh(ADDRESS)
    assert record == DirectoryRecord(first, Home.RU, DirectoryState.CLAIMED)


async def test_an_erased_accounts_address_is_free_again(
    homes: DatabaseAccess, run_slot: RunSlot, redis_cache: Redis
) -> None:
    store = directory(homes.transactions, redis_cache)
    old, new = new_id(), new_id()
    await store.claim(ADDRESS, old, Home.RU)
    await run_slot.claimed.connections[Home.EU].execute(
        "UPDATE directory_entries SET state = 'deleted'"
    )

    outcome = await store.claim(ADDRESS, new, Home.EU)

    assert outcome is ClaimOutcome.WON
    assert await store.find_fresh(ADDRESS) == DirectoryRecord(new, Home.EU, DirectoryState.CLAIMED)


async def test_sign_in_reads_the_last_copy_when_the_eu_home_is_down(
    homes: DatabaseAccess, redis_cache: Redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = directory(homes.transactions, redis_cache)
    outage = directory(cast("HomeTransactions", EuUnreachable(homes.transactions)), redis_cache)
    user_id = new_id()
    await store.claim(ADDRESS, user_id, Home.RU)
    await store.activate(ADDRESS, user_id)

    with pytest.raises(HomeUnavailableError):
        await outage.find(ADDRESS)
    cached = await store.find(ADDRESS)
    # Копия старше своих 60 с: свежая взялась бы из кеша, не спрашивая каталог.
    monkeypatch.setattr(directory_module, "FRESH_FOR", timedelta(0))
    fallback = await outage.find(ADDRESS)

    assert cached == fallback == DirectoryRecord(user_id, Home.RU, DirectoryState.ACTIVE)


async def test_the_sweep_activates_written_accounts_and_releases_the_rest(
    homes: DatabaseAccess, run_slot: RunSlot, redis_cache: Redis
) -> None:
    store = directory(homes.transactions, redis_cache)
    written, abandoned = new_id(), new_id()
    await store.claim(ADDRESS, written, Home.RU)
    await store.claim(bytes(reversed(range(32))), abandoned, Home.RU)
    async with homes.transactions.begin(TenancyScope(Home.RU, written)) as session:
        session.add(User(id=written, email="a@example.com", full_name="A", language="en"))
    await run_slot.claimed.connections[Home.EU].execute(
        "UPDATE directory_entries SET updated_at = now() - interval '11 minutes'"
    )

    settled = await settle_claims(homes.transactions, store)

    assert settled == 2
    states = await fetch_rows(
        run_slot.claimed.connections[Home.EU], "SELECT user_id, state FROM directory_entries"
    )
    assert [(row["user_id"], row["state"]) for row in states] == [(written, "active")]


async def test_a_fresh_claim_is_left_to_its_verification(
    homes: DatabaseAccess, redis_cache: Redis
) -> None:
    store = directory(homes.transactions, redis_cache)
    await store.claim(ADDRESS, new_id(), Home.RU)

    assert await settle_claims(homes.transactions, store) == 0


async def test_expired_pending_registrations_are_purged(homes: DatabaseAccess) -> None:
    now = datetime.now(UTC)
    async with homes.transactions.begin(TenancyScope(Home.EU)) as session:
        for expires_at in (now - timedelta(minutes=1), now + timedelta(minutes=10)):
            session.add(
                PendingRegistration(
                    id=new_id(), email="b@example.com", email_hmac=ADDRESS,
                    password_hash="x", full_name="B", country="DE", language="de",
                    consent_cross_border=False, consent_marketing=False, code_hash=b"c",
                    last_sent_at=now, expires_at=expires_at,
                )
            )  # fmt: skip

    assert await purge_pending(homes.transactions, Home.EU) == 1
    assert await purge_pending(homes.transactions, Home.EU) == 0
