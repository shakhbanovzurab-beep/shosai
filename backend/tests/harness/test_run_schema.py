"""The run's schema and data: the slot is migrated, and tests leave the tables empty."""

from urllib.parse import unquote, urlsplit

from shosai.core.kernel.homes import Home
from tests.harness.connections import fetch_value
from tests.harness.migrations import clear_tables, cleared_tables
from tests.harness.run_slot import RunSlot
from tests.harness.sample_environ import sample_environ
from tests.harness.settings import HarnessSettings, parse_database_url

PROBE_TABLE = "harness_rows"
CREATE_PROBE = "CREATE TABLE harness_rows (id integer)"
FILL_PROBE = "INSERT INTO harness_rows VALUES (1), (2)"
COUNT_PROBE = "SELECT count(*) FROM harness_rows"
DROP_PROBE = "DROP TABLE harness_rows"


def test_a_slot_address_round_trips_in_the_application_format() -> None:
    url = "postgresql://who%40ever:p%2Fss%3A@[::1]:16432/shosai_test"
    target = (
        HarnessSettings.from_environ(sample_environ(TEST_HOME_RU_DATABASE_URL=url))
        .homes[Home.RU]
        .application.for_slot(4)
    )

    address = target.url().get_secret_value()
    parsed = parse_database_url(target.variable, address)

    assert (parsed.user, parsed.password, parsed.host, parsed.port) == (
        "who@ever",
        "p/ss:",
        "::1",
        16432,
    )
    assert unquote(urlsplit(address).path) == "/shosai_test_4"


def test_tests_clear_every_application_table_but_the_seeded_ones() -> None:
    for home in Home:
        assert "home_identity" not in cleared_tables(home)


async def test_clearing_empties_the_tables_and_keeps_them(run_slot: RunSlot) -> None:
    connection = run_slot.claimed.connections[Home.EU]
    await connection.execute(CREATE_PROBE)
    try:
        await connection.execute(FILL_PROBE)
        await clear_tables(connection, [PROBE_TABLE])
        remaining = await fetch_value(connection, COUNT_PROBE)
    finally:
        await connection.execute(DROP_PROBE)

    assert remaining == 0


async def test_clearing_no_tables_sends_nothing(run_slot: RunSlot) -> None:
    await clear_tables(run_slot.claimed.connections[Home.RU], [])
