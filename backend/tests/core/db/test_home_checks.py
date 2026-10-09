"""The check of every home at start and before the first transaction (ADR 0010, F1-D7, F1-D8)."""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

import pytest
import sqlalchemy as sa
from pydantic import SecretStr

from shosai.core.db.errors import RETRY_AFTER_SECONDS, HomeUnavailableError
from shosai.core.db.home_checks import HomeMisconfiguredError, HomeState
from shosai.core.db.migrations import MigrationHistory
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from tests.core.db.tcp_proxy import CountingProxy, Upstream, through
from tests.core.observability.capture import captured_logs
from tests.harness.database_access import (
    DatabaseAccess,
    ProcessShape,
    open_database_access,
    slot_urls,
)
from tests.harness.run_slot import RunSlot, prepare_run_slot
from tests.harness.settings import HarnessSettings
from tests.harness.slots import claim_slot

FUTURE_REVISION = "f0f0f0f0f0f0"
WRONG_PASSWORD = "not-the-application-password"
HOME_STATE = "shosai_db_home_state"


class ManualClock:
    """Monotonic time the test moves by hand."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        """The current reading."""
        return self.now


@asynccontextmanager
async def ru_behind_proxy(
    run_slot: RunSlot, clock: ManualClock
) -> AsyncIterator[tuple[CountingProxy, DatabaseAccess]]:
    """Access whose RU address leads to a proxy that drops connections until given an upstream."""
    proxy = CountingProxy(None)
    port = await proxy.start()
    urls = slot_urls(run_slot)
    urls[Home.RU] = through(urls[Home.RU], port)
    try:
        async with open_database_access(urls, ProcessShape(clock=clock)) as access:
            yield proxy, access
    finally:
        await proxy.stop()


def upstream_of(run_slot: RunSlot, home: Home) -> Upstream:
    target = run_slot.claimed.targets(home).application
    return Upstream(target.host, target.port)


async def test_both_homes_are_verified_at_the_head(run_slot: RunSlot) -> None:
    history = MigrationHistory.load()
    async with open_database_access(slot_urls(run_slot)) as access:
        checks = await access.gate.verify_at_start()

    assert {(check.home, check.state, check.revision) for check in checks} == {
        (home, HomeState.VERIFIED, history.head) for home in Home
    }


async def test_swapped_addresses_stop_the_start_and_name_both_variables(run_slot: RunSlot) -> None:
    urls = slot_urls(run_slot)
    swapped: dict[Home, SecretStr] = {Home.RU: urls[Home.EU], Home.EU: urls[Home.RU]}

    async with open_database_access(swapped) as access:
        with pytest.raises(HomeMisconfiguredError) as raised:
            await access.gate.verify_at_start()

    message = str(raised.value)
    assert "HOME_RU_DATABASE_URL: ведёт в базу дома eu" in message
    assert "HOME_EU_DATABASE_URL: ведёт в базу дома ru" in message
    assert "local-app" not in message


async def test_a_schema_behind_the_code_stops_the_start(run_slot: RunSlot) -> None:
    applied = MigrationHistory.load()
    ahead_of_database = MigrationHistory(
        head=FUTURE_REVISION, revisions=applied.revisions | {FUTURE_REVISION}
    )

    async with open_database_access(
        slot_urls(run_slot), ProcessShape(history=ahead_of_database)
    ) as access:
        with pytest.raises(HomeMisconfiguredError, match="схема отстаёт от кода"):
            await access.gate.verify_at_start()


async def test_a_schema_newer_than_the_code_lets_the_previous_image_start(
    run_slot: RunSlot,
) -> None:
    older_code = MigrationHistory(head="0a0a0a0a0a0a", revisions=frozenset({"0a0a0a0a0a0a"}))

    with captured_logs() as captured:
        async with open_database_access(
            slot_urls(run_slot), ProcessShape(history=older_code)
        ) as access:
            checks = await access.gate.verify_at_start()

    assert {check.state for check in checks} == {HomeState.VERIFIED}
    assert "Схема дома новее кода" in captured.text()


async def test_an_unmigrated_database_stops_the_start(harness_settings: HarnessSettings) -> None:
    claimed = await claim_slot(harness_settings, range(1, harness_settings.database_slots + 1))
    try:
        fresh = await prepare_run_slot(claimed)
        async with open_database_access(slot_urls(fresh)) as access:
            with pytest.raises(HomeMisconfiguredError) as raised:
                await access.gate.verify_at_start()
    finally:
        await claimed.release()

    assert {check.state for check in raised.value.checks} == {HomeState.BEHIND}
    assert "нет ревизии" in str(raised.value)


async def test_a_home_out_of_reach_does_not_stop_the_start_or_the_other_home(
    run_slot: RunSlot,
) -> None:
    async with ru_behind_proxy(run_slot, ManualClock()) as (proxy, access):
        checks = {check.home: check.state for check in await access.gate.verify_at_start()}

        with pytest.raises(HomeUnavailableError) as refused:
            async with access.transactions.begin(TenancyScope(Home.RU)):
                pytest.fail("транзакция в непроверенном доме не должна открыться")
        async with access.transactions.begin(TenancyScope(Home.EU), read_only=True) as session:
            eu_home = (await session.execute(sa.text("SELECT home FROM home_identity"))).scalar()

    assert checks == {Home.RU: HomeState.UNREACHABLE, Home.EU: HomeState.VERIFIED}
    assert refused.value.status == 503
    assert refused.value.code == "home_unavailable"
    assert eu_home == "eu"
    assert proxy.turns == 0


async def test_a_home_that_comes_back_is_verified_before_its_first_transaction(
    run_slot: RunSlot,
) -> None:
    clock = ManualClock()
    async with ru_behind_proxy(run_slot, clock) as (proxy, access):
        await access.gate.verify_at_start()
        proxy.upstream = upstream_of(run_slot, Home.RU)
        clock.now += RETRY_AFTER_SECONDS - 0.1
        with pytest.raises(HomeUnavailableError):
            # Повторная проверка — не раньше, чем через RETRY_AFTER_SECONDS после неудачной.
            await access.gate.ensure_open(Home.RU)
        checks_before_retry = proxy.turns

        clock.now += 0.1
        scope = TenancyScope(Home.RU, user_id=uuid.uuid4())
        async with access.transactions.begin(scope, read_only=True) as session:
            ru_home = (await session.execute(sa.text("SELECT home FROM home_identity"))).scalar()
        state = access.registry.get_sample_value(HOME_STATE, {"home": "ru", HOME_STATE: "verified"})

    assert checks_before_retry == 0
    assert ru_home == "ru"
    assert state == 1.0


async def test_another_home_found_later_closes_the_home_and_pages(run_slot: RunSlot) -> None:
    clock = ManualClock()
    async with ru_behind_proxy(run_slot, clock) as (proxy, access):
        await access.gate.verify_at_start()
        proxy.upstream = upstream_of(run_slot, Home.EU)
        clock.now += RETRY_AFTER_SECONDS

        with captured_logs() as captured, pytest.raises(HomeUnavailableError):
            await access.gate.ensure_open(Home.RU)
        checks_when_closed = proxy.turns
        clock.now += RETRY_AFTER_SECONDS
        with pytest.raises(HomeUnavailableError):
            await access.gate.ensure_open(Home.RU)
        state = access.registry.get_sample_value(
            HOME_STATE, {"home": "ru", HOME_STATE: "wrong_home"}
        )

    # Закрытый дом больше не проверяется: до перезапуска процесса в него не ходят.
    assert proxy.turns == checks_when_closed
    assert state == 1.0
    assert '"level": "critical"' in captured.text()
    assert "База дома закрыта" in captured.text()


async def test_a_refused_password_is_named_in_the_check_without_the_password(
    run_slot: RunSlot,
) -> None:
    urls = slot_urls(run_slot)
    parts = urlsplit(urls[Home.RU].get_secret_value())
    user = parts.netloc.split(":", 1)[0]
    host = parts.netloc.rsplit("@", 1)[1]
    urls[Home.RU] = SecretStr(parts._replace(netloc=f"{user}:{WRONG_PASSWORD}@{host}").geturl())

    async with open_database_access(urls) as access:
        checks = {check.home: check for check in await access.gate.verify_at_start()}

    ru = checks[Home.RU]
    assert ru.state is HomeState.UNREACHABLE
    assert ru.failure is not None
    assert "authentication failed" in ru.failure
    assert "authentication failed" in ru.describe()
    assert WRONG_PASSWORD not in ru.describe()
