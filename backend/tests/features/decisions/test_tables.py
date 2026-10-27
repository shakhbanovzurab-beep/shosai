"""The Decision Layer's tables: records only appended, one policy in force per point, the
database keeps the codes closed (decisions plan §3.6)."""

import uuid
from datetime import UTC, datetime

import psycopg
import pytest
from sqlalchemy import insert, select, text, update
from sqlalchemy.exc import DBAPIError

from shosai.core.config.roles import ProcessRole
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.decisions.infrastructure.records import (
    DecisionOutcomeRow,
    DecisionRow,
    PolicyStateRow,
    ThresholdRevisionRow,
)
from tests.harness.database_access import (
    DatabaseAccess,
    ProcessShape,
    open_database_access,
    slot_urls,
)
from tests.harness.run_slot import RunSlot

NOW = datetime.now(UTC)
DIGEST = "0123456789abcdef"
DECISION = (
    "INSERT INTO agent_decisions (id, created_at, point, version, subject_kind, subject_id,"
    " language, facts, rule_outcome, outcome, reason, source, latency_ms)"
    " VALUES (%s, now(), %s, 1, %s, %s, %s, '{}', %s, %s, %s, %s, 0)"
)


def decision(**fields: object) -> dict[str, object]:
    """A recorded decision's columns, a friction card by default."""
    return {
        "id": uuid.uuid4(), "created_at": NOW, "point": "action.friction", "version": 1,
        "subject_kind": "action", "subject_id": uuid.uuid4(), "language": "ru",
        "facts": {"tool": "tasks.create", "items": 2}, "rule_outcome": "standard",
        "outcome": "warning", "reason": "judged", "source": "jev", "latency_ms": 212,
    } | fields  # fmt: skip


async def test_the_application_appends_records_and_never_reads_or_changes_them(
    homes: DatabaseAccess,
) -> None:
    row = decision()
    async with homes.transactions.begin(TenancyScope(Home.RU)) as session:
        await session.execute(insert(DecisionRow).values(row))
        await session.execute(
            insert(DecisionOutcomeRow).values(
                id=uuid.uuid4(), created_at=NOW, point="action.friction", subject_kind="action",
                subject_id=row["subject_id"], observation={"resolution": "approved"},
            )
        )  # fmt: skip

    for statement in (
        select(DecisionRow.id),
        select(DecisionOutcomeRow.id),
        update(DecisionRow).values(outcome="standard"),
        text("DELETE FROM agent_decisions"),
    ):
        with pytest.raises(DBAPIError, match="permission denied"):
            async with homes.transactions.begin(TenancyScope(Home.RU)) as session:
                await session.execute(statement)


async def test_the_sweep_role_reads_the_records(homes: DatabaseAccess, run_slot: RunSlot) -> None:
    row = decision(source="late", reason="deadline", probabilities={"matches_request": 0.4})
    async with homes.transactions.begin(TenancyScope(Home.EU)) as session:
        await session.execute(insert(DecisionRow).values(row))

    shape = ProcessShape(role=ProcessRole.WORKERS)
    async with open_database_access(slot_urls(run_slot), shape) as workers:
        await workers.gate.verify_at_start()
        scope = TenancyScope(Home.EU)
        async with workers.transactions.begin(scope, read_only=True, sweep=True) as session:
            found = await session.execute(select(DecisionRow).where(DecisionRow.id == row["id"]))
            kept = found.scalar_one()
    assert (kept.source, kept.reason, kept.probabilities) == (
        "late",
        "deadline",
        row["probabilities"],
    )


# Точка, вид субъекта, язык, исход, причина, источник — в каждом случае один код вне формы.
BROKEN_CODES = [
    ("Action.Friction", "action", "ru", "warning", "judged", "jev"),
    ("action.friction", "person", "ru", "warning", "judged", "jev"),
    ("action.friction", "action", "russian", "warning", "judged", "jev"),
    ("action.friction", "action", "ru", "Warning!", "judged", "jev"),
    ("action.friction", "action", "ru", "warning", "guessed", "jev"),
    ("action.friction", "action", "ru", "warning", "judged", "model"),
]


@pytest.mark.parametrize("codes", BROKEN_CODES)
async def test_the_database_keeps_a_records_codes_closed(
    run_slot: RunSlot, codes: tuple[str, str, str, str, str, str]
) -> None:
    point, kind, language, outcome, reason, source = codes
    connection = run_slot.claimed.connections[Home.RU]
    values = (
        uuid.uuid4(),
        point,
        kind,
        uuid.uuid4(),
        language,
        "standard",
        outcome,
        reason,
        source,
    )

    with pytest.raises(psycopg.errors.CheckViolation):
        await connection.execute(DECISION, values)


async def test_a_record_keeps_only_a_short_state_hash(run_slot: RunSlot) -> None:
    connection = run_slot.claimed.connections[Home.EU]
    statement = (
        "INSERT INTO agent_decisions (id, created_at, point, version, subject_kind, subject_id,"
        " language, facts, state_hash, rule_outcome, outcome, reason, source, latency_ms)"
        " VALUES (%s, now(), 'turn.route', 1, 'run', %s, 'en', '{}', %s, '-', 'notes', 'judged',"
        " 'jev', 180)"
    )
    await connection.execute(statement, (uuid.uuid4(), uuid.uuid4(), b"0" * 16))

    with pytest.raises(psycopg.errors.CheckViolation):
        await connection.execute(statement, (uuid.uuid4(), uuid.uuid4(), b"0" * 32))


async def test_records_and_outcomes_are_partitioned_and_kept_four_months(
    run_slot: RunSlot,
) -> None:
    for home in Home:
        connection = run_slot.claimed.connections[home]
        cursor = await connection.execute(
            "SELECT table_name, keep_months FROM partition_policies"
            " WHERE table_name IN ('agent_decisions', 'agent_decision_outcomes')"
            " ORDER BY table_name"
        )
        rows = [(row["table_name"], row["keep_months"]) for row in await cursor.fetchall()]
        assert rows == [("agent_decision_outcomes", 4), ("agent_decisions", 4)]


async def test_one_version_of_a_point_is_active_and_one_in_shadow(homes: DatabaseAccess) -> None:
    async with homes.transactions.begin(TenancyScope(Home.EU)) as session:
        for version in (1, 2, 3):
            await session.execute(
                insert(ThresholdRevisionRow).values(
                    point="action.friction", version=version, revision=1, questions_digest=DIGEST,
                    cuts={"matches": {"lower": 0.6, "upper": 0.7}}, report={}, passed=True,
                )
            )  # fmt: skip
        for version, state in ((1, "active"), (2, "shadow")):
            await session.execute(
                insert(PolicyStateRow).values(
                    point="action.friction", version=version, state=state, revision=1,
                    questions_digest=DIGEST,
                )
            )  # fmt: skip

    for state in ("active", "shadow"):
        with pytest.raises(DBAPIError, match="uq_decision_policies"):
            async with homes.transactions.begin(TenancyScope(Home.EU)) as session:
                await session.execute(
                    insert(PolicyStateRow).values(
                        point="action.friction", version=3, state=state, revision=1,
                        questions_digest=DIGEST,
                    )
                )  # fmt: skip


async def test_a_policy_in_force_names_an_existing_revision(homes: DatabaseAccess) -> None:
    with pytest.raises(DBAPIError, match="fk_decision_policies"):
        async with homes.transactions.begin(TenancyScope(Home.EU)) as session:
            await session.execute(
                insert(PolicyStateRow).values(
                    point="turn.route", version=1, state="shadow", revision=7,
                    questions_digest=DIGEST,
                )
            )  # fmt: skip


async def test_policies_live_in_the_eu_home_only(run_slot: RunSlot) -> None:
    query = (
        "SELECT count(*) AS tables FROM information_schema.tables"
        " WHERE table_name IN ('decision_policies', 'decision_thresholds')"
    )
    counts: dict[Home, int | None] = {}
    for home in Home:
        cursor = await run_slot.claimed.connections[home].execute(query)
        row = await cursor.fetchone()
        counts[home] = row["tables"] if row else None
    assert counts == {Home.EU: 2, Home.RU: 0}
