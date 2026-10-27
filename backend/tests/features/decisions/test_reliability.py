"""Reliability per band: a home's day counted into the EU home, idempotently (decisions step 8b;
ADR 0069 DL-D7)."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import insert, select

from shosai.core.config.roles import ProcessRole
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.decisions.application.reliability import ReliabilityPass
from shosai.features.decisions.domain.policies import policies_by_key
from shosai.features.decisions.domain.reliability import BandKey, DecisionGroup, Tally, tallied
from shosai.features.decisions.infrastructure.records import (
    DecisionOutcomeRow,
    DecisionRow,
    ReliabilityRow,
)
from tests.harness.database_access import (
    DatabaseAccess,
    ProcessShape,
    open_database_access,
    slot_urls,
)
from tests.harness.run_slot import RunSlot


def group(
    point: str, outcome: str, observation: dict[str, Any] | None, count: int = 1
) -> DecisionGroup:
    """Decisions of version 1, revision 1, in English, settled by Jev."""
    return DecisionGroup(
        point,
        1,
        1,
        shadow=False,
        outcome=outcome,
        language="en",
        source="jev",
        observation=observation,
        count=count,
    )


def key(point: str, band: str, version: int = 1) -> BandKey:
    """Their band's key."""
    return BandKey(point, version, 1, shadow=False, band=band, language="en", source="jev")


def test_each_point_counts_the_careful_case_its_own_way() -> None:
    groups = [
        group("action.friction", "warning", {"resolution": "rejected"}, 3),
        group("action.friction", "warning", {"resolution": "approved"}, 5),
        group("action.friction", "standard", None, 7),
        group("turn.route", "mail,calendar", {"called": ["mail"]}, 2),
        group("turn.route", "mail", {"called": ["notes"]}),
        group("turn.route", "-", {"called": ["mail"]}),
        group("content.injection", "suspicious", None, 4),
        DecisionGroup(
            "turn.route",
            9,
            1,
            shadow=False,
            outcome="mail",
            language="en",
            source="jev",
            observation={"called": ["mail"]},
            count=1,
        ),
    ]

    counts = tallied(groups, policies_by_key())

    assert counts == {
        key("action.friction", "warning"): Tally(8, 3),
        key("action.friction", "standard"): Tally(7, 0),
        key("turn.route", "ranked"): Tally(3, 2),
        key("turn.route", "none"): Tally(1, 0),
        key("content.injection", "suspicious"): Tally(4, 0),
        # Версии, которой нет в образе: полоса — сам исход, подтверждений не считаем.
        key("turn.route", "mail", version=9): Tally(1, 0),
    }


async def seed(homes: DatabaseAccess, now: datetime) -> None:
    """Three friction cards and a routed run in the Russian home, with what followed."""
    cards = [("warning", "rejected"), ("warning", "approved"), ("standard", None)]
    subjects = [(uuid.uuid4(), outcome, end) for outcome, end in cards]
    run = uuid.uuid4()
    async with homes.transactions.begin(TenancyScope(Home.RU)) as session:
        for subject, outcome, _ in subjects:
            await session.execute(
                insert(DecisionRow).values(
                    decision("action.friction", "action", subject, outcome, now)
                )
            )
        await session.execute(
            insert(DecisionRow).values(decision("turn.route", "run", run, "mail", now))
        )
        later = now + timedelta(minutes=5)
        for subject, _, end in subjects:
            if end is not None:
                await session.execute(
                    insert(DecisionOutcomeRow).values(
                        observed("action.friction", "action", subject, {"resolution": end}, later)
                    )
                )
        await session.execute(
            insert(DecisionOutcomeRow).values(
                observed("turn.route", "run", run, {"called": ["mail"]}, later)
            )
        )


def decision(
    point: str, kind: str, subject: uuid.UUID, outcome: str, at: datetime
) -> dict[str, Any]:
    """A recorded decision of version 1."""
    return {
        "id": uuid.uuid4(), "created_at": at, "point": point, "version": 1, "revision": 1,
        "shadow": False, "subject_kind": kind, "subject_id": subject, "language": "ru",
        "facts": {}, "rule_outcome": "-" if point == "turn.route" else "standard",
        "outcome": outcome, "reason": "judged", "source": "jev", "latency_ms": 120,
    }  # fmt: skip


def observed(
    point: str, kind: str, subject: uuid.UUID, seen: dict[str, Any], at: datetime
) -> dict[str, Any]:
    """What followed it."""
    return {
        "id": uuid.uuid4(), "created_at": at, "point": point, "subject_kind": kind,
        "subject_id": subject, "observation": seen,
    }  # fmt: skip


async def test_the_pass_counts_a_home_s_day_into_the_eu_home_and_twice_is_once(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    now = datetime.now(UTC)
    await seed(homes, now)
    tomorrow = now + timedelta(days=1)

    async with open_database_access(
        slot_urls(run_slot), ProcessShape(role=ProcessRole.WORKERS)
    ) as worker:
        await worker.gate.verify_at_start()
        counting = ReliabilityPass(worker.transactions, policies_by_key(), lambda: tomorrow)
        first = await counting.run(Home.RU)
        second = await counting.run(Home.RU)
        async with worker.transactions.begin(TenancyScope(Home.EU), read_only=True) as session:
            rows = (await session.scalars(select(ReliabilityRow))).all()

    counted = {(r.point, r.band, r.decisions, r.positives) for r in rows}
    assert (first, second) == (3, 3)
    assert counted == {
        ("action.friction", "warning", 2, 1),
        ("action.friction", "standard", 1, 0),
        ("turn.route", "ranked", 1, 1),
    }
    assert {(r.day, r.home, r.language, r.revision) for r in rows} == {(now.date(), "ru", "ru", 1)}
