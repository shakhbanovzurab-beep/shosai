"""An account's deletion window hides its memberships and a cancel restores them (ADR 0053 p. 4)."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import cast

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.events.subscriptions import ReceivedEvent
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.tasks.declaration import TaskDeclaration
from shosai.core.tasks.payloads import TaskPayload
from shosai.features.identity.contracts import AccountDeletionCancelled, AccountDeletionScheduled
from shosai.features.workspaces.application.account_visibility import (
    AccountEvent,
    apply_account_event,
)
from shosai.features.workspaces.channels.consumers import AccountWindow
from shosai.features.workspaces.channels.tasks import APPLY_ACCOUNT_EVENT, AccountVisibilityPayload
from shosai.features.workspaces.contracts import Viewer
from tests.features.workspaces.probe_resources import NOTES
from tests.features.workspaces.test_access_policy import policy
from tests.harness.connections import fetch_value
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot
from tests.support.isolation import canonical_world, write_world

NOW = datetime(2026, 10, 17, 12, tzinfo=UTC)


async def visible_to(homes: DatabaseAccess, home: Home, user: uuid.UUID) -> set[uuid.UUID]:
    async with homes.transactions.begin(TenancyScope(home, user), read_only=True) as session:
        query = sa.select(NOTES.table.c.id).where(policy().readable(NOTES, Viewer(user)))
        return set(await session.scalars(query))


async def test_a_hidden_owner_s_shares_disappear_and_return_on_cancel(
    homes: DatabaseAccess, probe_resources: None, run_slot: RunSlot
) -> None:
    canon = canonical_world("meeting")
    connection = run_slot.claimed.connections[Home.RU]
    await write_world(connection, NOTES, canon.world)
    alice, bob = canon.people["alice"], canon.people["bob"]
    before = await visible_to(homes, Home.RU, bob)

    await apply_account_event(
        homes.transactions, AccountEvent(Home.RU, alice, hidden=True, occurred_at=NOW)
    )
    hidden = await visible_to(homes, Home.RU, bob)
    await apply_account_event(
        homes.transactions,
        AccountEvent(Home.RU, alice, hidden=False, occurred_at=NOW + timedelta(days=1)),
    )

    assert hidden < before
    assert await visible_to(homes, Home.RU, bob) == before
    assert (
        await fetch_value(connection, "SELECT state FROM memberships WHERE user_id = %s", (alice,))
        == "active"
    )


async def test_an_older_event_delivered_late_changes_nothing(
    homes: DatabaseAccess, probe_resources: None, run_slot: RunSlot
) -> None:
    canon = canonical_world("file")
    connection = run_slot.claimed.connections[Home.EU]
    await write_world(connection, NOTES, canon.world)
    bob = canon.people["bob"]

    await apply_account_event(
        homes.transactions, AccountEvent(Home.EU, bob, hidden=False, occurred_at=NOW)
    )
    await apply_account_event(
        homes.transactions,
        AccountEvent(Home.EU, bob, hidden=True, occurred_at=NOW - timedelta(hours=1)),
    )
    await apply_account_event(
        homes.transactions, AccountEvent(Home.EU, bob, hidden=True, occurred_at=NOW)
    )

    assert (
        await fetch_value(connection, "SELECT state FROM memberships WHERE user_id = %s", (bob,))
        == "active"
    )


class Queued:
    def __init__(self) -> None:
        self.sent: list[tuple[str, TaskPayload]] = []

    async def send[P: TaskPayload](self, task: TaskDeclaration[P], payload: P) -> str:
        self.sent.append((task.name, payload))
        return "task"


async def test_identity_s_events_queue_the_task_with_their_time() -> None:
    queued, user = Queued(), uuid.uuid4()
    window = AccountWindow(queued)
    scope = TenancyScope(Home.RU, user)
    erase_at = NOW + timedelta(days=7)

    scheduled = AccountDeletionScheduled(user_id=user, erase_at=erase_at)
    cancelled = AccountDeletionCancelled(user_id=user)
    # Сессия доставки обработчику не нужна: он только ставит задачу.
    session = cast("AsyncSession", None)

    await window.scheduled(session, ReceivedEvent(scheduled, uuid.uuid4(), 1, NOW, scope))
    await window.cancelled(session, ReceivedEvent(cancelled, uuid.uuid4(), 1, NOW, scope))

    expected = [
        AccountVisibilityPayload(home=Home.RU, user_id=user, hidden=True, occurred_at=NOW),
        AccountVisibilityPayload(home=Home.RU, user_id=user, hidden=False, occurred_at=NOW),
    ]
    assert queued.sent == [(APPLY_ACCOUNT_EVENT.name, payload) for payload in expected]
    assert {s.consumer for s in window.subscriptions()} == {
        "workspaces.hide_memberships",
        "workspaces.restore_memberships",
    }
