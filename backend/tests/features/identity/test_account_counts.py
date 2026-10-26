"""Accounts counted for the platform operator's Leo (agent AG-D5): each home's accounts by
state, and those registered in the last days; counts only, read as the admin's search reads."""

import uuid
from datetime import UTC, datetime, timedelta

from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.identity.application.account_counts import AccountCountsReader
from shosai.features.identity.contracts.accounts import HomeAccounts
from shosai.features.identity.infrastructure.records import User
from tests.harness.database_access import DatabaseAccess


def by_home(found: list[HomeAccounts]) -> dict[Home, HomeAccounts]:
    return {home.home: home for home in found}


async def test_each_home_s_accounts_are_counted_by_state_and_by_registration(
    homes: DatabaseAccess,
) -> None:
    reader = AccountCountsReader(homes.transactions)
    before = by_home(list(await reader.counts(30)))
    now = datetime.now(UTC)
    accounts = [
        (Home.RU, "active", now), (Home.RU, "frozen", now - timedelta(days=60)),
        (Home.EU, "active", now - timedelta(days=60)),
    ]  # fmt: skip
    for home, state, created in accounts:
        user_id = uuid.uuid4()
        async with homes.transactions.begin(TenancyScope(home, user_id)) as session:
            session.add(
                User(id=user_id, email=f"{user_id.hex[:12]}@example.com", full_name="A",
                     language="en", state=state, created_at=created)
            )  # fmt: skip

    after = by_home(list(await reader.counts(30)))

    def grew(home: Home, state: str) -> int:
        return after[home].by_state.get(state, 0) - before[home].by_state.get(state, 0)

    assert (grew(Home.RU, "active"), grew(Home.RU, "frozen"), grew(Home.EU, "active")) == (1, 1, 1)
    assert after[Home.RU].registered - before[Home.RU].registered == 1
    assert after[Home.EU].registered == before[Home.EU].registered
