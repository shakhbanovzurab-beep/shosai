"""Row-level security of workspaces' tables: the second line behind the access policy (ADR 0053).

A person reads the rows of every workspace they are an active member of and writes only
into the transaction's workspace; the sweep role reads every tenant's rows and only in a
workers or scheduler process; the audit log only grows; a workspace always keeps an owner.
"""

import uuid
from datetime import timedelta

import pytest
import sqlalchemy as sa
from sqlalchemy import exc

from shosai.core.config.roles import ProcessRole
from shosai.core.db.engines import DatabaseProfile
from shosai.core.db.transactions import SweepNotAllowedError
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from tests.features.workspaces.rls_world import World, build_world, slug_of
from tests.harness.connections import fetch_value
from tests.harness.database_access import (
    DatabaseAccess,
    ProcessShape,
    open_database_access,
    slot_urls,
)
from tests.harness.run_slot import RunSlot

TEAMS = sa.text("SELECT name FROM teams")
ORGANIZATIONS = sa.text("SELECT slug FROM organizations")
OWNER_RULE = "workspace_keeps_an_owner"


def violated_constraint(error: exc.IntegrityError) -> str | None:
    """The constraint PostgreSQL names in the error's diagnostics."""
    diagnostics = getattr(error.orig, "diag", None)
    return getattr(diagnostics, "constraint_name", None)


async def world_in(run_slot: RunSlot, home: Home) -> World:
    return await build_world(run_slot.claimed.connections[home])


async def names(access: DatabaseAccess, scope: TenancyScope, query: sa.TextClause) -> set[str]:
    async with access.transactions.begin(scope, read_only=True) as session:
        return set((await session.execute(query)).scalars())


@pytest.mark.parametrize("home", list(Home))
async def test_a_person_reads_every_workspace_they_belong_to_and_no_other(
    homes: DatabaseAccess, run_slot: RunSlot, home: Home
) -> None:
    world = await world_in(run_slot, home)
    mine = {slug_of(world.org_a), slug_of(world.org_b)}

    seen_teams = await names(homes, TenancyScope(home, world.person), TEAMS)
    seen_workspaces = await names(homes, TenancyScope(home, world.person), ORGANIZATIONS)
    seen_by_nobody = await names(homes, TenancyScope(home, uuid.uuid4()), TEAMS)

    assert seen_teams == mine
    assert seen_workspaces == mine
    assert seen_by_nobody == set()


async def test_a_removed_membership_hides_the_workspace_from_the_next_statement(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    connection = run_slot.claimed.connections[Home.RU]
    world = await build_world(connection)

    async with homes.transactions.begin(TenancyScope(Home.RU, world.person)) as session:
        before = set((await session.execute(TEAMS)).scalars())
        await connection.execute(
            "UPDATE memberships SET state = 'removed', removed_at = now(), "
            "removal_reason = 'removed_by_admin' WHERE id = %s",
            (world.membership_b,),
        )
        after = set((await session.execute(TEAMS)).scalars())

    assert slug_of(world.org_b) in before
    assert after == {slug_of(world.org_a)}


async def test_a_hidden_membership_reads_nothing_of_its_workspace(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    connection = run_slot.claimed.connections[Home.EU]
    world = await build_world(connection)
    await connection.execute(
        "UPDATE memberships SET state = 'hidden' WHERE id = %s", (world.membership_b,)
    )

    assert await names(homes, TenancyScope(Home.EU, world.person), TEAMS) == {slug_of(world.org_a)}


async def test_rows_are_written_only_into_the_transactions_workspace(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    world = await world_in(run_slot, Home.RU)
    insert = sa.text("INSERT INTO teams (id, org_id, name, color) VALUES (:id, :org, 'x', 'sky')")

    async with homes.transactions.begin(TenancyScope(Home.RU, world.person, world.org_a)) as tx:
        await tx.execute(insert, {"id": uuid.uuid4(), "org": world.org_a})
    for scope, org in (
        (TenancyScope(Home.RU, world.person, world.org_a), world.org_b),
        (TenancyScope(Home.RU, world.person), world.org_a),
    ):
        with pytest.raises(exc.ProgrammingError, match="row-level security"):
            async with homes.transactions.begin(scope) as session:
                await session.execute(insert, {"id": uuid.uuid4(), "org": org})


async def test_the_sweep_role_reads_every_tenant_and_writes_nothing(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    world = await world_in(run_slot, Home.EU)
    workers = ProcessShape(role=ProcessRole.WORKERS)

    async with open_database_access(slot_urls(run_slot), workers) as access:
        await access.gate.verify_at_start()
        async with access.transactions.begin(TenancyScope(Home.EU), sweep=True) as session:
            seen = set((await session.execute(TEAMS)).scalars())
        with pytest.raises(exc.ProgrammingError, match="permission denied"):
            async with access.transactions.begin(TenancyScope(Home.EU), sweep=True) as session:
                await session.execute(sa.text("DELETE FROM teams"))

    assert seen == {slug_of(world.org_a), slug_of(world.org_b), slug_of(world.org_c)}


async def test_a_request_process_cannot_open_a_sweep(homes: DatabaseAccess) -> None:
    with pytest.raises(SweepNotAllowedError):
        async with homes.transactions.begin(TenancyScope(Home.RU), sweep=True):
            pass


async def test_the_audit_log_only_grows(homes: DatabaseAccess, run_slot: RunSlot) -> None:
    world = await world_in(run_slot, Home.RU)
    scope = TenancyScope(Home.RU, world.person, world.org_a)

    async with homes.transactions.begin(scope) as session:
        await session.execute(
            sa.text(
                "INSERT INTO org_audit_events (id, created_at, org_id, action, target_kind) "
                "VALUES (:id, now(), :org, 'settings_changed', 'workspace')"
            ),
            {"id": uuid.uuid4(), "org": world.org_a},
        )
    for statement in ("UPDATE org_audit_events SET value = 'x'", "DELETE FROM org_audit_events"):
        with pytest.raises(exc.ProgrammingError, match="permission denied"):
            async with homes.transactions.begin(scope) as session:
                await session.execute(sa.text(statement))

    count = await fetch_value(
        run_slot.claimed.connections[Home.RU], "SELECT count(*) FROM org_audit_events"
    )
    assert count == 1


async def test_the_only_owner_cannot_step_down_but_may_be_hidden(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    world = await world_in(run_slot, Home.EU)
    scope = TenancyScope(Home.EU, world.person, world.org_a)
    set_role = sa.text("UPDATE memberships SET role = 'admin' WHERE id = :id")
    hide = sa.text("UPDATE memberships SET state = 'hidden' WHERE id = :id")

    with pytest.raises(exc.IntegrityError) as refused:
        async with homes.transactions.begin(scope) as session:
            await session.execute(set_role, {"id": world.membership_a})
    assert violated_constraint(refused.value) == OWNER_RULE
    async with homes.transactions.begin(scope) as session:
        await session.execute(hide, {"id": world.membership_a})

    state = await fetch_value(
        run_slot.claimed.connections[Home.EU],
        "SELECT state FROM memberships WHERE id = %s",
        (world.membership_a,),
    )
    assert state == "hidden"


async def test_a_workspace_cannot_be_created_without_its_owner(homes: DatabaseAccess) -> None:
    org = uuid.uuid4()
    scope = TenancyScope(Home.RU, uuid.uuid4(), org)

    with pytest.raises(exc.IntegrityError) as refused:
        async with homes.transactions.begin(scope) as session:
            await session.execute(
                sa.text(
                    "INSERT INTO organizations (id, slug, name, created_by) "
                    "VALUES (:id, 'lonely', 'Lonely', :by)"
                ),
                {"id": org, "by": scope.user_id},
            )
    assert violated_constraint(refused.value) == OWNER_RULE


async def test_the_domain_directory_exists_in_the_eu_home_only(run_slot: RunSlot) -> None:
    query = "SELECT to_regclass('public.directory_domains') IS NOT NULL"

    assert await fetch_value(run_slot.claimed.connections[Home.EU], query) is True
    assert await fetch_value(run_slot.claimed.connections[Home.RU], query) is False


async def test_the_sweep_role_ends_with_its_transaction_on_a_reused_connection(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    await world_in(run_slot, Home.RU)
    # Один пул на одно соединение: следующая транзакция идёт по тому же соединению PgBouncer.
    single = DatabaseProfile(pool_size=1, statement_timeout=timedelta(seconds=10), sweeps=True)
    shape = ProcessShape(role=ProcessRole.WORKERS, profile=single)

    async with open_database_access(slot_urls(run_slot), shape) as access:
        await access.gate.verify_at_start()
        async with access.transactions.begin(TenancyScope(Home.RU), sweep=True) as session:
            swept = set((await session.execute(TEAMS)).scalars())
        async with access.transactions.begin(TenancyScope(Home.RU)) as session:
            after = set((await session.execute(TEAMS)).scalars())
            role = (await session.execute(sa.text("SELECT current_user"))).scalar_one()

    assert len(swept) == 3
    assert after == set()
    assert role != "shosai_sweeper"
