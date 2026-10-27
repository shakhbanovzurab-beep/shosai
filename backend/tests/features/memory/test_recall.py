"""Recall and the profile core: the nearest current facts within the budget, their trust, and
nothing — counted — when there is nothing to give (memory step 4, MM-D6, MM-D7)."""

import uuid
from datetime import timedelta

from shosai.core.agent_tools.context import Taint
from shosai.core.agent_tools.provenance import Provenance
from shosai.core.ai.errors import AiFailure
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.identity.contracts import Principal
from shosai.features.memory.application.switch import MemorySwitch
from shosai.features.memory.infrastructure.presence import has_memories_key
from tests.features.memory.recall_bench import MODEL, RecallBench, axis


async def test_the_nearest_current_facts_come_with_their_label_and_taint(
    recall_bench: RecallBench,
) -> None:
    person, org = uuid.uuid4(), uuid.uuid4()
    recall_bench.model.known["Where do I live?"] = axis(1)
    near: dict[str, object] = {"embedding": axis(1, 0.1), "embedding_model": MODEL}
    await recall_bench.add(
        person,
        [
            {"statement": "Lives in Berlin"} | near,
            {"statement": "Mara leads design", "source_kind": "meeting", "confirmed": False,
             "source_taint": "external"} | near,
            {"statement": "Guessed", "confirmed": False} | near,
            {"statement": "Unrelated", "embedding": axis(0, 1), "embedding_model": MODEL},
            {"statement": "Waits", "status": "candidate"} | near,
            {"statement": "Old model", "embedding": axis(1), "embedding_model": "other/model"},
            {"statement": "Workspace's", "org_id": org} | near,
        ],
    )  # fmt: skip

    facts = await recall_bench.recall.recall(recall_bench.ask(person, "Where do I live?"))
    recall_bench.spaces.of[person] = {org}
    member = await recall_bench.recall.recall(recall_bench.ask(person, "Where do I live?"))

    found = {fact.statement: (fact.label, fact.taint) for fact in facts}
    assert found == {
        "Lives in Berlin": (Provenance.MEMORY, Taint.NONE),
        "Mara leads design": (Provenance.MEETING_SPEECH, Taint.EXTERNAL),
        "Guessed": (Provenance.MEMORY, Taint.EXTERNAL),
    }
    assert "Workspace's" in {fact.statement for fact in member}
    context, texts, later = recall_bench.model.calls[0]
    assert texts == ("task: search result | query: Where do I live?",)
    assert later
    assert context.scope == TenancyScope(Home.RU, person)


async def test_nothing_without_consent_with_memory_off_or_when_nothing_is_held(
    recall_bench: RecallBench,
) -> None:
    person, empty, off = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    await recall_bench.add(
        person, [{"statement": "Held", "embedding": axis(1), "embedding_model": MODEL}]
    )
    await recall_bench.add(
        off, [{"statement": "Held", "embedding": axis(1), "embedding_model": MODEL}]
    )
    await MemorySwitch(recall_bench.homes.transactions).turn(
        Principal(off, Home.RU, 0), enabled=False
    )

    refused = await recall_bench.recall.recall(recall_bench.ask(person, "q", consent=False))
    calls_before = len(recall_bench.model.calls)
    nothing = await recall_bench.recall.recall(recall_bench.ask(empty, "q"))
    again = await recall_bench.recall.recall(recall_bench.ask(empty, "q"))
    switched_off = await recall_bench.recall.recall(recall_bench.ask(off, "q"))

    assert refused == nothing == again == switched_off == ()
    # Вызов модели — только для того, кто ещё не отмечен «пустым»: второй раз пустой не платит.
    assert len(recall_bench.model.calls) == calls_before + 2
    assert await recall_bench.valkey.get(has_memories_key(empty)) == b"0"


async def test_a_late_or_failed_call_gives_the_turn_nothing(recall_bench: RecallBench) -> None:
    person = uuid.uuid4()
    await recall_bench.add(
        person, [{"statement": "Held", "embedding": axis(1), "embedding_model": MODEL}]
    )

    recall_bench.model.delay = timedelta(seconds=1)
    late = await recall_bench.recall.recall(recall_bench.ask(person, "q"))
    recall_bench.model.delay, recall_bench.model.failure = timedelta(0), AiFailure.PROVIDER_ERROR
    failed = await recall_bench.recall.recall(recall_bench.ask(person, "q"))

    assert late == failed == ()


async def test_the_profile_core_is_pinned_facts_then_preferences_or_memory_off(
    recall_bench: RecallBench,
) -> None:
    person = uuid.uuid4()
    await recall_bench.add(
        person,
        [
            {"statement": "Pinned goal", "kind": "goal", "pinned": True},
            {"statement": "Prefers short answers", "kind": "preference"},
            {"statement": "Plain fact"},
            {"statement": "Waiting preference", "kind": "preference", "status": "candidate"},
        ],
    )
    scope = TenancyScope(Home.RU, person)

    async with recall_bench.homes.transactions.begin(scope, read_only=True) as session:
        core = await recall_bench.recall.profile(session, person, 400)
    await MemorySwitch(recall_bench.homes.transactions).turn(
        Principal(person, Home.RU, 0), enabled=False
    )
    async with recall_bench.homes.transactions.begin(scope, read_only=True) as session:
        off = await recall_bench.recall.profile(session, person, 400)

    assert core.enabled
    assert sorted(fact.statement for fact in core.facts) == ["Pinned goal", "Prefers short answers"]
    assert (off.enabled, off.facts) == (False, ())
