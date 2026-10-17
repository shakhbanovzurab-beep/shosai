"""The inv-1 check: directory entries without an account in their home (§16.4, step 14)."""

from prometheus_client import CollectorRegistry

from shosai.core.kernel.homes import Home
from shosai.core.kernel.ids import new_id
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.identity.application.directory_check import DirectoryCheck
from shosai.features.identity.domain.registration import DirectoryState
from shosai.features.identity.infrastructure.records import DirectoryEntry, User
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot

GAUGE = "shosai_identity_directory_orphans"


def orphans(registry: CollectorRegistry, home: Home) -> float | None:
    return registry.get_sample_value(GAUGE, {"home": home.value})


async def test_an_old_entry_without_its_account_is_counted_in_its_home(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    lost, fresh, written, freed = new_id(), new_id(), new_id(), new_id()
    async with homes.transactions.begin(TenancyScope(Home.EU)) as session:
        for marker, user_id, state in (
            (1, lost, DirectoryState.ACTIVE),
            (2, fresh, DirectoryState.CLAIMED),
            (3, written, DirectoryState.ACTIVE),
            (4, freed, DirectoryState.DELETED),
        ):
            session.add(
                DirectoryEntry(
                    email_hmac=bytes([marker]) * 32, user_id=user_id, home=Home.RU.value,
                    state=state.value,
                )
            )  # fmt: skip
    async with homes.transactions.begin(TenancyScope(Home.RU, written)) as session:
        session.add(User(id=written, email="w@example.com", full_name="W", language="en"))
    await run_slot.claimed.connections[Home.EU].execute(
        "UPDATE directory_entries SET updated_at = now() - interval '11 minutes' "
        "WHERE user_id <> %s",
        (fresh,),
    )
    registry = CollectorRegistry()

    counts = await DirectoryCheck(homes.transactions, registry).run()

    assert counts == {Home.RU: 1, Home.EU: 0}
    assert orphans(registry, Home.RU) == 1
    assert orphans(registry, Home.EU) == 0


async def test_a_fresh_entry_is_not_an_orphan_yet(homes: DatabaseAccess) -> None:
    async with homes.transactions.begin(TenancyScope(Home.EU)) as session:
        session.add(
            DirectoryEntry(
                email_hmac=bytes(32), user_id=new_id(), home=Home.EU.value,
                state=DirectoryState.ACTIVE.value,
            )
        )  # fmt: skip
    registry = CollectorRegistry()

    counts = await DirectoryCheck(homes.transactions, registry).run()

    assert counts == {Home.RU: 0, Home.EU: 0}
    assert orphans(registry, Home.EU) == 0
