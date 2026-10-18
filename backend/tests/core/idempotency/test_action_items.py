"""A Leo action's item takes effect once per key with one audit event (Leo §8.4 rules 2, 6)."""

import uuid

import pytest
from prometheus_client import CollectorRegistry
from pydantic import BaseModel

from shosai.core.agent_tools.events import ActionItemExecuted
from shosai.core.events.catalog import EventTypes
from shosai.core.events.outbox import EventOutbox
from shosai.core.idempotency.action_items import ActionItems
from shosai.core.idempotency.ledger import EffectLedger
from shosai.core.idempotency.metrics import EffectKeyMetrics
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from tests.harness.connections import fetch_rows
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot

USER_ID = uuid.UUID("0190f0f0-0000-7000-8000-0000000000a1")
TOOL = "probe.archive"


class Archived(BaseModel):
    """The probe item's outcome."""

    runs: int


class RefusedError(Exception):
    """The probe effect refused the item."""


def items() -> ActionItems:
    outbox = EventOutbox(EventTypes([ActionItemExecuted]))
    return ActionItems(EffectLedger(EffectKeyMetrics(CollectorRegistry())), outbox)


async def test_an_item_runs_once_per_key_and_is_audited_once(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    applier, runs = items(), [0]
    key = f"{uuid.uuid4()}:0"

    async def effect() -> Archived:
        runs[0] += 1
        return Archived(runs=runs[0])

    outcomes = []
    for _ in range(2):
        async with homes.transactions.begin(TenancyScope(Home.EU, USER_ID)) as session:
            outcomes.append(await applier.once(session, (key, TOOL, 2), Archived, effect))

    rows = await fetch_rows(
        run_slot.claimed.connections[Home.EU],
        "SELECT event_type, payload FROM outbox_messages ORDER BY id",
    )
    assert outcomes == [Archived(runs=1), Archived(runs=1)]
    assert runs == [1]
    assert [(r["event_type"], r["payload"]) for r in rows] == [
        ("agent.action_item.executed", {"item_key": key, "tool": TOOL, "targets": 2})
    ]


async def test_a_refused_item_leaves_no_key_and_no_event(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    applier = items()
    key = f"{uuid.uuid4()}:1"

    async def refused() -> Archived:
        raise RefusedError

    with pytest.raises(RefusedError):
        async with homes.transactions.begin(TenancyScope(Home.RU, USER_ID)) as session:
            await applier.once(session, (key, TOOL, 1), Archived, refused)

    connection = run_slot.claimed.connections[Home.RU]
    assert await fetch_rows(connection, "SELECT key FROM effect_keys") == []
    assert await fetch_rows(connection, "SELECT id FROM outbox_messages") == []
