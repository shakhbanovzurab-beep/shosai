"""One Alembic history applied to both homes (ADR 0010).

The run's slot is already at the head: the harness upgraded it with the production
runner and will downgrade it to the base at the end.
"""

import asyncio
from types import ModuleType

import pytest
import sqlalchemy as sa
from alembic import op
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext, RevisionStep
from alembic.script import ScriptDirectory
from sqlalchemy import Connection, NullPool, make_url
from sqlalchemy.ext.asyncio import create_async_engine

from shosai.composition.metadata import application_metadata
from shosai.core.db.engines import DRIVER
from shosai.core.db.migration_scope import MigrationScope, ScopedStep, runs_in
from shosai.core.db.migrations import (
    MIGRATION_LOCK_KEY,
    MigrationHistory,
    RevisionState,
    alembic_config,
    current_revision,
    upgrade,
)
from shosai.core.db.model_base import metadata_for_home
from shosai.core.db.partitions.policy import is_model_table
from shosai.core.kernel.homes import Home
from tests.core.db.operations import run_step
from tests.harness.connections import fetch_value
from tests.harness.migrations import migration_targets
from tests.harness.run_slot import RunSlot

EU_ONLY_TABLE = "probe_eu_only"
TABLE_EXISTS_SQL = "SELECT to_regclass(%s) IS NOT NULL"
LOCK_WAIT_SECONDS = 0.5


def revision_modules() -> list[ModuleType]:
    """The module of every revision in the history shipped with the package."""
    script = ScriptDirectory.from_config(alembic_config())
    return [revision.module for revision in script.walk_revisions()]


async def test_every_home_is_at_the_head_with_its_identity(run_slot: RunSlot) -> None:
    head = MigrationHistory.load().head

    for target in migration_targets(run_slot.claimed):
        connection = run_slot.claimed.connections[target.home]

        assert await current_revision(target) == head
        assert await fetch_value(connection, "SELECT home FROM home_identity") == target.home.value


@pytest.mark.parametrize("home", list(Home))
async def test_the_models_match_the_migrated_schema_of_each_home(
    run_slot: RunSlot, home: Home
) -> None:
    url = run_slot.claimed.targets(home).migration.url().get_secret_value()
    engine = create_async_engine(make_url(url).set(drivername=DRIVER), poolclass=NullPool)
    expected = metadata_for_home(application_metadata(), home)

    def differences(connection: Connection) -> list[object]:
        opts = {"compare_server_default": True, "include_name": is_model_table}
        context = MigrationContext.configure(connection, opts=opts)
        return list(compare_metadata(context, expected))

    try:
        async with engine.connect() as connection:
            found = await connection.run_sync(differences)
    finally:
        await engine.dispose()

    assert found == []


def test_every_revision_declares_its_homes_on_both_steps() -> None:
    modules = revision_modules()

    assert modules
    for module in modules:
        applies_to = module.applies_to
        assert applies_to, module.__name__
        assert set(applies_to) <= set(Home), module.__name__
        for step in (module.upgrade, module.downgrade):
            assert isinstance(step, ScopedStep), module.__name__
            assert step.applies_to == applies_to, module.__name__


def test_a_scoped_step_runs_only_in_its_homes() -> None:
    ran_in: list[Home] = []

    @runs_in((Home.EU,))
    def step(scope: MigrationScope) -> None:
        ran_in.append(scope.home)

    for home in Home:
        step(MigrationScope(home=home, application_role="shosai_app"))

    assert ran_in == [Home.EU]


def test_a_step_without_homes_is_refused() -> None:
    with pytest.raises(ValueError, match="хотя бы к одному дому"):
        runs_in(())(lambda _scope: None)


@runs_in((Home.EU,))
def create_eu_only_table(_scope: MigrationScope) -> None:
    """An EU-only table, as the directory or a platform table is."""
    op.create_table(EU_ONLY_TABLE, sa.Column("id", sa.Integer(), primary_key=True))


@runs_in((Home.EU,))
def drop_eu_only_table(_scope: MigrationScope) -> None:
    """Undo `create_eu_only_table`."""
    op.drop_table(EU_ONLY_TABLE)


async def test_an_eu_only_revision_leaves_the_russian_home_untouched(run_slot: RunSlot) -> None:
    async def exists() -> dict[Home, object]:
        return {
            home: await fetch_value(connection, TABLE_EXISTS_SQL, (EU_ONLY_TABLE,))
            for home, connection in run_slot.claimed.connections.items()
        }

    for home in Home:
        await run_step(run_slot, home, create_eu_only_table)
    try:
        created = await exists()
    finally:
        for home in Home:
            await run_step(run_slot, home, drop_eu_only_table)

    assert created == {Home.RU: False, Home.EU: True}
    assert await exists() == {Home.RU: False, Home.EU: False}


async def test_a_second_run_waits_for_the_first(run_slot: RunSlot) -> None:
    holder = run_slot.claimed.connections[Home.RU]
    [ru_target, _] = migration_targets(run_slot.claimed)
    await holder.execute("SELECT pg_advisory_lock(%s)", (MIGRATION_LOCK_KEY,))
    try:
        second = asyncio.create_task(upgrade([ru_target], application_metadata()))
        await asyncio.sleep(LOCK_WAIT_SECONDS)
        waited = not second.done()
    finally:
        await holder.execute("SELECT pg_advisory_unlock(%s)", (MIGRATION_LOCK_KEY,))
    await asyncio.wait_for(second, timeout=10)

    assert waited


def test_a_revision_is_at_the_head_newer_or_behind() -> None:
    history = MigrationHistory(head="b2", revisions=frozenset({"a1", "b2"}))

    assert history.state_of("b2") is RevisionState.AT_HEAD
    assert history.state_of("a1") is RevisionState.BEHIND
    assert history.state_of(None) is RevisionState.BEHIND
    assert history.state_of("c3") is RevisionState.NEWER


def test_alembic_names_every_scoped_step_in_its_log_line() -> None:
    script = ScriptDirectory.from_config(alembic_config())

    for revision in script.walk_revisions():
        for is_upgrade, name in ((True, "upgrade"), (False, "downgrade")):
            step = RevisionStep(script.revision_map, revision, is_upgrade)
            assert str(step).startswith(f"{name} ")
