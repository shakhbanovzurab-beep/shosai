"""Records written in batches off the path, and the policies in force read from the EU home
(decisions plan §3.3, §3.6)."""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

from prometheus_client import CollectorRegistry
from sqlalchemy import insert

from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.decisions.domain.policies.action_friction import ACTION_FRICTION
from shosai.features.decisions.infrastructure.metrics import DecisionMetrics
from shosai.features.decisions.infrastructure.policy_store import PolicyStore, cuts_json
from shosai.features.decisions.infrastructure.record_writer import RecordWriter
from shosai.features.decisions.infrastructure.records import PolicyStateRow, ThresholdRevisionRow
from tests.features.decisions.engine_bench import FRICTION_CUTS
from tests.harness.connections import fetch_value
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot

NOW = datetime.now(UTC)


def decision() -> dict[str, object]:
    """A recorded decision's columns."""
    return {
        "id": uuid.uuid4(), "created_at": NOW, "point": "turn.route", "version": 1,
        "revision": 1, "shadow": False, "subject_kind": "run", "subject_id": uuid.uuid4(),
        "part": 0, "language": "en", "facts": {"candidates": 3}, "state_hash": None,
        "probabilities": {"needs_notes": 0.8}, "rule_outcome": "-", "outcome": "notes",
        "reason": "judged", "source": "jev", "latency_ms": 180, "jev_snapshot": None,
        "jev_request_id": None,
    }  # fmt: skip


COUNTS = {
    "agent_decisions": "SELECT count(*) FROM agent_decisions",
    "agent_decision_outcomes": "SELECT count(*) FROM agent_decision_outcomes",
}


async def count(run_slot: RunSlot, home: Home, table: str) -> object:
    """Rows of a table in a home, read as the migration role."""
    return await fetch_value(run_slot.claimed.connections[home], COUNTS[table])


async def test_rows_wait_for_their_batch_and_the_rest_is_written_on_close(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    registry = CollectorRegistry()
    writer = RecordWriter(homes.transactions, DecisionMetrics(registry), every=timedelta(hours=1))

    async with writer.running():
        for _ in range(3):
            writer.add_decision(Home.RU, decision())
        writer.add_outcome(
            Home.EU,
            {"id": uuid.uuid4(), "created_at": NOW, "point": "turn.route", "subject_kind": "run",
             "subject_id": uuid.uuid4(), "part": 0, "observation": {"called": ["notes"]}},
        )  # fmt: skip
        assert await count(run_slot, Home.RU, "agent_decisions") == 0

    assert await count(run_slot, Home.RU, "agent_decisions") == 3
    assert await count(run_slot, Home.EU, "agent_decision_outcomes") == 1
    assert writer.pending() == 0


async def test_a_full_batch_is_written_at_once(homes: DatabaseAccess, run_slot: RunSlot) -> None:
    writer = RecordWriter(
        homes.transactions, DecisionMetrics(CollectorRegistry()), every=timedelta(hours=1), batch=2
    )

    async with writer.running():
        writer.add_decision(Home.EU, decision())
        writer.add_decision(Home.EU, decision())
        # Полная пачка будит запись сразу, не дожидаясь часа.
        for _ in range(100):
            if await count(run_slot, Home.EU, "agent_decisions") == 2:
                break
            await asyncio.sleep(0.02)

        assert await count(run_slot, Home.EU, "agent_decisions") == 2


async def test_a_refused_batch_and_a_full_buffer_are_counted_lost(homes: DatabaseAccess) -> None:
    registry = CollectorRegistry()
    writer = RecordWriter(homes.transactions, DecisionMetrics(registry), cap=2)
    broken = decision() | {"point": "Not A Point"}

    writer.add_decision(Home.RU, broken)
    writer.add_decision(Home.RU, decision())
    writer.add_decision(Home.RU, decision())
    await writer.flush()

    lost = registry.get_sample_value(
        "shosai_decision_records_lost_total", {"table": "agent_decisions"}
    )
    assert lost == 3


async def test_the_store_reads_versions_in_force_with_their_cuts(homes: DatabaseAccess) -> None:
    async with homes.transactions.begin(TenancyScope(Home.EU)) as session:
        await session.execute(
            insert(ThresholdRevisionRow).values(
                point="action.friction", version=1, revision=2,
                questions_digest=ACTION_FRICTION.digest(), cuts=cuts_json(FRICTION_CUTS),
                report={"ece": 0.03}, passed=True,
            )
        )  # fmt: skip
        await session.execute(
            insert(PolicyStateRow).values(
                point="action.friction", version=1, state="active", revision=2,
                questions_digest=ACTION_FRICTION.digest(),
            )
        )  # fmt: skip

    [found] = await PolicyStore(homes.transactions).in_force()

    assert (found.point, found.version, found.state, found.revision) == (
        "action.friction", 1, "active", 2,
    )  # fmt: skip
    assert found.cuts == FRICTION_CUTS
