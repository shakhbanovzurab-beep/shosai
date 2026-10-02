"""The catalog fingerprint notices any schema change; a claim restores the prepared state."""

import pytest

from tests.harness.catalog import CatalogFingerprint, restore_prepared_state
from tests.harness.connections import Connection
from tests.harness.run_slot import RunSlot, prepare_run_slot
from tests.harness.settings import HarnessSettings
from tests.harness.slots import claim_slot
from whisperer.core.kernel.homes import Home

PROBE_TABLE = "CREATE TABLE harness_probe (id integer PRIMARY KEY);"
LEFTOVERS_OF_A_CRASHED_RUN = """
CREATE SCHEMA harness_extra;
CREATE EXTENSION citext;
CREATE TYPE harness_mood AS ENUM ('calm', 'busy');
CREATE TABLE harness_leftover (id bigint GENERATED ALWAYS AS IDENTITY, mood harness_mood);
CREATE VIEW harness_view AS SELECT id FROM harness_leftover;
CREATE FUNCTION harness_answer() RETURNS integer LANGUAGE sql AS 'SELECT 42';
CREATE TYPE harness_span AS RANGE (subtype = bigint);
ALTER DEFAULT PRIVILEGES GRANT SELECT ON TABLES TO whisperer_app;
ALTER DEFAULT PRIVILEGES REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
GRANT CREATE ON SCHEMA public TO whisperer_app, PUBLIC;
DO $$
BEGIN
    EXECUTE format('GRANT CREATE ON DATABASE %I TO whisperer_app', current_database());
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO PUBLIC', current_database());
    EXECUTE format('ALTER DATABASE %I SET work_mem = ''8MB''', current_database());
END
$$;
"""
EXPECTED_RESTORATION = (
    "- schema harness_extra",
    "- extension citext",
    "- type harness_mood",
    "- relation harness_leftover",
    "- relation harness_view",
    "- routine harness_answer()",
    "- type harness_span",
    "- default privileges whisperer_migrator * r",
    "- default privileges whisperer_migrator * f",
    "+ schema public",
    "+ database current",
)


async def changes_inside_rolled_back(connection: Connection, ddl: str) -> list[str]:
    """Catalog changes made by DDL inside a transaction that is then rolled back."""
    before = await CatalogFingerprint.take(connection)
    transaction = connection.transaction()
    await transaction.start()
    try:
        await connection.execute(ddl)
        changes = (await CatalogFingerprint.take(connection)).changes_since(before)
    finally:
        await transaction.rollback()
    assert await CatalogFingerprint.take(connection) == before
    return changes


@pytest.mark.parametrize(
    ("ddl", "expected"),
    [
        (PROBE_TABLE, "+ relation harness_probe: kind=r"),
        (PROBE_TABLE, "+ column harness_probe.id: integer not_null=true"),
        (PROBE_TABLE, "+ constraint harness_probe_pkey on harness_probe: PRIMARY KEY (id)"),
        ("CREATE TYPE harness_mood AS ENUM ('calm')", "+ type harness_mood: kind=e"),
        (
            "CREATE FUNCTION harness_answer() RETURNS integer LANGUAGE sql AS 'SELECT 42'",
            "+ routine harness_answer()",
        ),
        (
            PROBE_TABLE + "ALTER TABLE harness_probe ENABLE ROW LEVEL SECURITY;"
            "CREATE POLICY harness_own ON harness_probe USING (id > 0);",
            "+ policy harness_own on harness_probe",
        ),
        (
            PROBE_TABLE + "CREATE FUNCTION harness_touch() RETURNS trigger LANGUAGE plpgsql "
            "AS 'BEGIN RETURN NEW; END';"
            "CREATE TRIGGER harness_touched BEFORE UPDATE ON harness_probe "
            "FOR EACH ROW EXECUTE FUNCTION harness_touch();",
            "+ trigger harness_touched on harness_probe",
        ),
        (PROBE_TABLE + "GRANT SELECT ON harness_probe TO whisperer_app;", "whisperer_app=r/"),
        ("GRANT CREATE ON SCHEMA public TO whisperer_app", "+ schema public: owner="),
        (
            "ALTER DEFAULT PRIVILEGES GRANT SELECT ON TABLES TO whisperer_app",
            "+ default privileges whisperer_migrator * r",
        ),
        ("CREATE SCHEMA harness_extra", "+ schema harness_extra"),
        ("CREATE TEXT SEARCH CONFIGURATION harness_ts (COPY = simple)", "+ object text search"),
    ],
)
async def test_fingerprint_names_each_kind_of_schema_change(
    run_slot: RunSlot, ddl: str, expected: str
) -> None:
    changes = await changes_inside_rolled_back(run_slot.claimed.connections[Home.RU], ddl)

    assert any(expected in change for change in changes), changes


async def test_extension_objects_are_not_part_of_the_fingerprint(run_slot: RunSlot) -> None:
    for home, reference in run_slot.references.items():
        identities = {entry.identity for entry in reference.entries}

        assert "vector" in identities, home
        assert not any(identity.startswith("vector(") for identity in identities), home


async def test_a_prepared_slot_is_left_as_it_is(run_slot: RunSlot) -> None:
    for home, connection in run_slot.claimed.connections.items():
        application_role = run_slot.claimed.settings.homes[home].application.user

        assert await restore_prepared_state(connection, application_role) == [], home


async def test_a_claim_restores_what_a_crashed_run_left(
    run_slot: RunSlot, harness_settings: HarnessSettings
) -> None:
    # Слот держится весь тест, чтобы параллельный прогон не захватил его между шагами.
    claimed = await claim_slot(harness_settings, range(1, harness_settings.database_slots + 1))
    try:
        await prepare_run_slot(claimed)
        for connection in claimed.connections.values():
            await connection.execute(LEFTOVERS_OF_A_CRASHED_RUN)

        next_run = await prepare_run_slot(claimed)

        for home in Home:
            restored = next_run.restored[home]
            missing = [
                change
                for change in EXPECTED_RESTORATION
                if not any(line.startswith(f"{change}:") for line in restored)
            ]
            assert missing == [], (home, restored)
            assert next_run.references[home] == run_slot.references[home], home
        assert await next_run.catalog_changes() == []
        assert any("восстановлено после упавшего прогона" in line for line in next_run.summary())
    finally:
        await claimed.release()
