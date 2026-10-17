"""Creating, suspending and resuming a workspace (§3.6; ADR 0053 point 7)."""

import uuid

import pytest

from shosai.core.kernel.errors import AppError
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.workspaces.contracts.events import SuspensionSource
from tests.features.workspaces.services import (
    FixedSeats,
    audit_actions,
    created,
    event_types,
    services,
)
from tests.harness.connections import fetch_rows, fetch_value
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot


@pytest.mark.parametrize("home", list(Home))
async def test_a_person_creates_a_workspace_they_own_with_billings_trial(
    homes: DatabaseAccess, run_slot: RunSlot, home: Home
) -> None:
    seats = FixedSeats(paid=0)
    owner = uuid.uuid4()
    connection = run_slot.claimed.connections[home]

    workspace = await created(services(homes, seats), home, owner, "Моя Компания")

    members = await fetch_rows(connection, "SELECT user_id, role, state FROM memberships")
    assert workspace.slug == "моя-компания"
    assert [dict(m) for m in members] == [{"user_id": owner, "role": "owner", "state": "active"}]
    assert seats.trials == [(workspace.org_id, 5)]
    assert await audit_actions(connection) == ["workspace_created"]
    assert await event_types(connection) == [
        "workspaces.workspace.created",
        "workspaces.member.joined",
    ]


async def test_no_workspace_is_created_before_billing_sells_seats(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    with pytest.raises(AppError, match="seats_unavailable"):
        await created(services(homes, None), Home.RU, uuid.uuid4())

    assert (
        await fetch_value(
            run_slot.claimed.connections[Home.RU], "SELECT count(*) FROM organizations"
        )
        == 0
    )


@pytest.mark.parametrize("seats", [1, 101])
async def test_a_new_workspace_starts_with_2_to_100_seats(
    homes: DatabaseAccess, seats: int
) -> None:
    found = services(homes, FixedSeats(paid=0))

    with pytest.raises(AppError, match="seats_invalid"):
        await found.lifecycle.create(TenancyScope(Home.EU, uuid.uuid4()), "Acme", seats)


async def test_a_taken_slug_gets_the_next_number(homes: DatabaseAccess) -> None:
    found = services(homes, FixedSeats(paid=0))

    first = await created(found, Home.RU, uuid.uuid4(), "Acme")
    second = await created(found, Home.RU, uuid.uuid4(), "ACME")

    assert (first.slug, second.slug) == ("acme", "acme-2")


async def test_a_suspended_workspace_closes_to_its_members_until_resumed(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    found, owner = services(homes, FixedSeats(paid=0)), uuid.uuid4()
    workspace = await created(found, Home.EU, owner)
    platform = TenancyScope(Home.EU, org_id=workspace.org_id)
    as_owner = TenancyScope(Home.EU, owner, workspace.org_id)

    await found.lifecycle.suspend(platform, SuspensionSource.PLATFORM, "Unpaid invoice")
    with pytest.raises(AppError, match="workspace_not_active"):
        await found.lifecycle.suspend(platform, SuspensionSource.BILLING, "Again")
    with pytest.raises(AppError, match="workspace_suspended"):
        await found.members.leave(as_owner)
    await found.lifecycle.resume(platform)
    with pytest.raises(AppError, match="workspace_not_suspended"):
        await found.lifecycle.resume(platform)

    connection = run_slot.claimed.connections[Home.EU]
    assert await fetch_value(connection, "SELECT state FROM organizations") == "active"
    assert await audit_actions(connection) == ["workspace_created", "suspended", "resumed"]
