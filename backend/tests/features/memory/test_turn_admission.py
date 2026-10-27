"""A turn's admission: explicit requests saved, guesses asked within the day's three, the same
words confirming, the same subject proposing a replacement, the switches on this writer, and a
redelivery writing nothing twice (memory step 5, MM-D1)."""

import uuid

from shosai.core.agent_tools.context import Taint
from shosai.core.kernel.homes import Home
from shosai.features.identity.contracts import Principal
from shosai.features.memory.application.switch import MemorySwitch
from shosai.features.memory.domain.admission import Admission
from tests.features.memory.admission_bench import AdmissionBench
from tests.features.memory.recall_bench import axis


def said(statement: str, *, explicit: bool = False, kind: str = "fact") -> dict[str, object]:
    """One statement as the extraction model answers it."""
    return {
        "statement": statement, "kind": kind, "explicit": explicit, "sensitive": False,
        "about_person": True,
    }  # fmt: skip


async def test_an_explicit_request_is_saved_and_a_guess_is_asked(
    admission_bench: AdmissionBench,
) -> None:
    person, org = uuid.uuid4(), uuid.uuid4()
    admission_bench.consents.given.add(person)
    admission_bench.vectors.known |= {"Is vegetarian": axis(1), "Works late": axis(0, 1)}
    admission_bench.statements.found = [said("Is vegetarian", explicit=True), said("Works late")]
    run = admission_bench.turns.said("Remember I'm vegetarian. I work late a lot.", org_id=org)

    outcomes = await admission_bench.admission.admit(Home.RU, person, run)
    again = await admission_bench.admission.admit(Home.RU, person, run)
    facts = await admission_bench.facts(person)

    assert outcomes == again == [Admission.ACTIVE, Admission.CANDIDATE]
    assert [(f.statement, f.status, f.confirmed, f.explicit) for f in facts] == [
        ("Is vegetarian", "active", True, True),
        ("Works late", "candidate", False, False),
    ]
    words = admission_bench.turns.words[run]
    assert facts[0].source_ref == {
        "thread_id": str(words.thread_id),
        "message_id": str(words.message_id),
    }
    assert {fact.org_id for fact in facts} == {org}
    assert all(fact.embedding is not None for fact in facts)


async def test_no_more_than_three_new_candidates_a_day(admission_bench: AdmissionBench) -> None:
    person = uuid.uuid4()
    admission_bench.consents.given.add(person)
    for number in range(5):
        admission_bench.vectors.known[f"Guess {number}"] = axis(*([0.0] * number), 1)
        admission_bench.statements.found = [said(f"Guess {number}")]
        await admission_bench.admission.admit(Home.RU, person, admission_bench.turns.said("..."))

    statuses = [fact.status for fact in await admission_bench.facts(person)]
    assert statuses == ["candidate"] * 3


async def test_the_same_words_confirm_and_the_same_subject_proposes_a_replacement(
    admission_bench: AdmissionBench,
) -> None:
    person = uuid.uuid4()
    admission_bench.consents.given.add(person)
    admission_bench.vectors.known |= {"Lives in Moscow": axis(1), "Lives in Berlin": axis(1, 0.2)}
    admission_bench.statements.found = [said("Lives in Moscow", explicit=True)]
    await admission_bench.admission.admit(Home.RU, person, admission_bench.turns.said("a"))
    held = await admission_bench.admission.admit(Home.RU, person, admission_bench.turns.said("b"))
    admission_bench.statements.found = [said("Lives in Berlin")]
    moved = await admission_bench.admission.admit(Home.RU, person, admission_bench.turns.said("c"))
    moscow, berlin = await admission_bench.facts(person)

    assert held == [Admission.CONFIRMED]
    assert moscow.confirmations == 2
    assert moved == [Admission.CANDIDATE]
    assert (berlin.status, berlin.replaces) == ("candidate", moscow.id)


async def test_nothing_is_taken_with_memory_off_without_consent_or_from_a_suspicious_run(
    admission_bench: AdmissionBench,
) -> None:
    off, refusing, steered = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    admission_bench.consents.given |= {off, steered}
    admission_bench.statements.found = [said("Is vegetarian", explicit=True)]
    await MemorySwitch(admission_bench.homes.transactions).turn(
        Principal(off, Home.RU, 0), enabled=False
    )

    outcomes = [
        await admission_bench.admission.admit(Home.RU, off, admission_bench.turns.said("x")),
        await admission_bench.admission.admit(Home.RU, refusing, admission_bench.turns.said("x")),
        await admission_bench.admission.admit(
            Home.RU, steered, admission_bench.turns.said("x", taint=Taint.SUSPICIOUS)
        ),
        await admission_bench.admission.admit(Home.RU, off, uuid.uuid4()),
    ]

    assert outcomes == [[], [], [], []]
    assert admission_bench.statements.calls == []
    for person in (off, refusing, steered):
        assert await admission_bench.facts(person) == []
