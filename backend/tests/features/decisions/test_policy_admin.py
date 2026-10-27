"""Revisions and version states in the EU home, the shadow counted in both homes (DL-D6)."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import insert

from shosai.core.config.roles import ProcessRole
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.decisions.infrastructure.policy_admin import PolicyAdmin
from shosai.features.decisions.infrastructure.records import DecisionRow
from tests.harness.database_access import (
    DatabaseAccess,
    ProcessShape,
    open_database_access,
    slot_urls,
)
from tests.harness.run_slot import RunSlot

DIGEST = "0123456789abcdef"
FITTED = ({"matches": {"lower": 0.5, "upper": 0.6}}, {"ece": 0.02}, True)


async def test_revisions_are_numbered_per_version(homes: DatabaseAccess) -> None:
    admin = PolicyAdmin(homes.transactions)

    first = await admin.add_revision("action.friction", 1, DIGEST, FITTED)
    second = await admin.add_revision("action.friction", 1, DIGEST, FITTED)
    other = await admin.add_revision("action.friction", 2, DIGEST, FITTED)

    stored = await admin.revision("action.friction", 1, 2)
    assert (first, second, other) == (1, 2, 1)
    assert stored is not None
    assert (stored.passed, stored.report) == (True, {"ece": 0.02})
    assert len(await admin.revisions("action.friction")) == 3


async def test_a_new_active_version_retires_the_one_before(homes: DatabaseAccess) -> None:
    admin = PolicyAdmin(homes.transactions)
    for version in (1, 2):
        await admin.add_revision("turn.route", version, DIGEST, FITTED)

    await admin.set_state(("turn.route", 1, 1, "active"), DIGEST, "first")
    await admin.set_state(("turn.route", 2, 1, "shadow"), DIGEST, None)
    await admin.set_state(("turn.route", 2, 1, "active"), DIGEST, "promoted")

    states = {state.version: state.state for state in await admin.states("turn.route")}
    assert states == {1: "retired", 2: "active"}


async def test_the_shadow_is_counted_in_both_homes(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    now = datetime.now(UTC)
    for home, shadow in ((Home.RU, True), (Home.EU, True), (Home.EU, False)):
        async with homes.transactions.begin(TenancyScope(home)) as session:
            await session.execute(
                insert(DecisionRow).values(
                    id=uuid.uuid4(), created_at=now, point="action.friction", version=2,
                    shadow=shadow, subject_kind="action", subject_id=uuid.uuid4(),
                    language="en", facts={}, rule_outcome="standard", outcome="warning",
                    reason="judged", source="jev", latency_ms=200,
                )
            )  # fmt: skip

    shape = ProcessShape(role=ProcessRole.DECISIONS)
    async with open_database_access(slot_urls(run_slot), shape) as operator:
        await operator.gate.verify_at_start()
        admin = PolicyAdmin(operator.transactions)
        counted = await admin.shadow_decisions("action.friction", 2, now - timedelta(minutes=1))
        later = await admin.shadow_decisions("action.friction", 2, now + timedelta(minutes=1))

    assert (counted, later) == (2, 0)
