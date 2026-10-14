"""How many database round trips a sign-in costs in each home (identity plan §3.6).

The Russian home is 45 ms from the plane, so the count of round trips is the sign-in's
latency there. A change that adds one fails this test and has to say why.
"""

from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager

from redis.asyncio import Redis
from sqlalchemy import event
from sqlalchemy.engine import Connection

from shosai.core.kernel.homes import Home
from tests.features.identity.registration_bench import registration_bench
from tests.features.identity.test_sign_in import EMAIL, PASSWORD, account
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot

# Чтение аккаунта (BEGIN, SET LOCAL, SELECT, COMMIT) и запись входа (BEGIN, SET LOCAL,
# SELECT … FOR UPDATE, вставки сессии и журнала, UPDATE, COMMIT).
RUSSIAN_ROUND_TRIPS = 11


@contextmanager
def round_trips(homes: DatabaseAccess) -> Iterator[Counter[Home]]:
    """Count statements, BEGINs and COMMITs per home while the block runs."""
    counts: Counter[Home] = Counter()
    listeners = []
    for home in Home:
        engine = homes.databases.engine(home).sync_engine

        def statement(*_args: object, home: Home = home) -> None:
            counts[home] += 1

        def boundary(_connection: Connection, home: Home = home) -> None:
            counts[home] += 1

        for name, listener in (
            ("before_cursor_execute", statement),
            ("begin", boundary),
            ("commit", boundary),
        ):
            event.listen(engine, name, listener)
            listeners.append((engine, name, listener))
    try:
        yield counts
    finally:
        for engine, name, listener in listeners:
            event.remove(engine, name, listener)


async def test_a_russian_sign_in_takes_a_fixed_number_of_round_trips(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        await account(bench, run_slot)
        # Первый вход прогревает кеш каталога, как у живого процесса.
        await bench.http.post("/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})
        with round_trips(homes) as counts:
            answer = await bench.http.post(
                "/v1/auth/login", json={"email": EMAIL, "password": PASSWORD}
            )

    assert answer.status_code == 200
    assert counts[Home.EU] == 0
    assert counts[Home.RU] == RUSSIAN_ROUND_TRIPS
