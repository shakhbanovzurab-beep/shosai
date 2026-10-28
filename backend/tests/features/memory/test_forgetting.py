"""Forgetting for good (ADR 0071 MM-D9): an ended fact stays its day, while it can be taken back,
then goes; what the person forgot or turned down leaves only a trace — no text — and a statement
close to a trace is not asked again for 90 days unless the person asks for it."""

import uuid
from datetime import timedelta

from sqlalchemy import insert

from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.memory.domain.admission import Admission
from shosai.features.memory.infrastructure.records import MemoryRefusalRecord
from tests.features.memory.admission_bench import AdmissionBench, said
from tests.features.memory.recall_bench import MODEL, ROUTE, axis
from tests.features.memory.upkeep_bench import NOW, UpkeepBench

YESTERDAY = NOW - timedelta(hours=25)


async def test_an_ended_fact_stays_its_day_then_goes_and_a_refusal_leaves_only_a_trace(
    upkeep_bench: UpkeepBench,
) -> None:
    person = uuid.uuid4()
    vector = {"embedding": axis(1), "embedding_model": MODEL}
    ids = await upkeep_bench.add(
        person,
        [{"statement": "Forgot an hour ago", "status": "forgotten", "ended_reason": "forgot",
          "ended_at": NOW - timedelta(hours=1)} | vector,
         {"statement": "Forgot yesterday", "status": "forgotten", "ended_reason": "forgot",
          "ended_at": YESTERDAY} | vector,
         {"statement": "Declined yesterday", "status": "forgotten",
          "ended_reason": "turned_down", "ended_at": YESTERDAY} | vector,
         {"statement": "Faded yesterday", "status": "forgotten", "ended_reason": "expired",
          "ended_at": YESTERDAY} | vector,
         {"statement": "Replaced yesterday", "valid_to": YESTERDAY,
          "superseded_by": uuid.uuid4()},
         {"statement": "Forgot without a vector", "status": "forgotten",
          "ended_reason": "forgot", "ended_at": YESTERDAY}],
    )  # fmt: skip

    deleted = await upkeep_bench.forgetting.tidy(Home.RU)
    again = await upkeep_bench.forgetting.tidy(Home.RU)

    assert deleted >= 5
    assert again == 0
    assert set(await upkeep_bench.rows(person)) == {"Forgot an hour ago"}
    assert await upkeep_bench.traces(person) == {ids[1], ids[2]}
    assert set(MemoryRefusalRecord.__table__.columns.keys()) == {
        "id", "user_id", "embedding", "embedding_model", "refused_at",
    }  # fmt: skip


async def test_a_statement_close_to_a_refusal_is_not_asked_again_unless_asked_for(
    admission_bench: AdmissionBench,
) -> None:
    person = uuid.uuid4()
    admission_bench.consents.given.add(person)
    admission_bench.vectors.known |= {"Works late": axis(1), "Runs at dawn": axis(0, 1)}
    model = ROUTE.primary.model
    async with admission_bench.homes.transactions.begin(TenancyScope(Home.RU, person)) as s:
        await s.execute(
            insert(MemoryRefusalRecord),
            [{"id": uuid.uuid4(), "user_id": person, "embedding": axis(1),
              "embedding_model": model, "refused_at": NOW - timedelta(days=10)},
             {"id": uuid.uuid4(), "user_id": person, "embedding": axis(0, 1),
              "embedding_model": model, "refused_at": NOW - timedelta(days=91)}],
        )  # fmt: skip

    outcomes = []
    for statement in (said("Works late"), said("Runs at dawn"), said("Works late", explicit=True)):
        admission_bench.statements.found = [statement]
        run = admission_bench.turns.said("...")
        outcomes += await admission_bench.admission.admit(Home.RU, person, run)

    assert outcomes == [Admission.SKIPPED_FORGOTTEN, Admission.CANDIDATE, Admission.ACTIVE]
