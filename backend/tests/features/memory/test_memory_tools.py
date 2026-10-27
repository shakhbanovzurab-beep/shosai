"""Leo's `memory` toolset: recall reads only the person's current facts in their spaces, the
nearest or the pinned and the latest, labelled by where they came from; forget is planned
whole, its card shows the statements as stored, and it forgets exactly the planned facts once
(memory step 6)."""

import uuid

from sqlalchemy import update

from shosai.core.agent_tools.context import ToolContext
from shosai.core.agent_tools.previews import render_preview
from shosai.core.agent_tools.provenance import Provenance
from shosai.core.agent_tools.results import PlannedEffect, ToolError, ToolErrorCode
from shosai.core.agent_tools.sources import SourceKind
from shosai.core.kernel.homes import Home
from shosai.features.identity.contracts import Principal
from shosai.features.memory.application.switch import MemorySwitch
from shosai.features.memory.channels.agent_previews import FORGET
from shosai.features.memory.channels.agent_tools import ForgetMemory, RecallMemory
from shosai.features.memory.infrastructure.records import MemoryFactRecord
from tests.features.memory.recall_bench import axis
from tests.features.memory.tools_bench import ToolsBench


def planned(result: PlannedEffect | ToolError) -> PlannedEffect:
    """The plan, which the test expects to be one."""
    assert isinstance(result, PlannedEffect), result
    return result


async def recalled(bench: ToolsBench, context: ToolContext, query: str | None = None) -> list[str]:
    """The statements a recall gives, in its order."""
    result = await bench.tools.recall(RecallMemory(query=query), context)
    assert result.output is not None, result.error
    return [fact.statement for fact in result.output.facts]


async def test_recall_reads_the_nearest_or_the_pinned_and_the_latest_of_the_persons_own(
    tools_bench: ToolsBench,
) -> None:
    person, stranger, left = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    tools_bench.consents.given.add(person)
    tools_bench.model.known["food"] = axis(1)
    await tools_bench.add(
        person,
        [
            {"statement": "Is vegetarian"},
            {"statement": "Works late", "embedding": axis(0, 1)},
            {"statement": "Prefers short answers", "pinned": True, "kind": "preference",
             "embedding": axis(0, 1)},
            {"statement": "Waits", "status": "candidate"},
            {"statement": "Left workspace's", "org_id": left},
            {"statement": "Not embedded yet", "embedding": None, "embedding_model": None},
        ],
    )  # fmt: skip
    await tools_bench.add(stranger, [{"statement": "A stranger's"}])

    near = await recalled(tools_bench, tools_bench.context(person), "food")
    listed = await recalled(tools_bench, tools_bench.context(person))

    assert near == ["Is vegetarian"]
    assert listed == ["Prefers short answers", "Not embedded yet", "Works late", "Is vegetarian"]
    assert tools_bench.model.calls[-1][2]


async def test_a_meetings_fact_is_labelled_its_speech_and_cites_the_meeting(
    tools_bench: ToolsBench,
) -> None:
    person, meeting, gone = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    tools_bench.meetings.titles[meeting] = "Design review"
    await tools_bench.add(
        person,
        [
            {"statement": "Mara leads design", "source_kind": "meeting", "confirmed": False,
             "source_taint": "external", "source_ref": {"meeting_id": str(meeting)}},
            {"statement": "Heard elsewhere", "source_kind": "meeting", "confirmed": False,
             "source_taint": "external", "source_ref": {"meeting_id": str(gone)}},
        ],
    )  # fmt: skip
    own = uuid.uuid4()
    await tools_bench.add(own, [{"statement": "Is vegetarian"}])

    heard = await tools_bench.tools.recall(RecallMemory(), tools_bench.context(person))
    mine = await tools_bench.tools.recall(RecallMemory(), tools_bench.context(own))

    assert heard.output is not None
    assert heard.provenance is Provenance.MEETING_SPEECH
    assert [(fact.meeting, fact.confirmed) for fact in heard.output.facts] == [
        (None, False),
        ("Design review", False),
    ]
    assert [(source.kind, source.id, source.title) for source in heard.sources] == [
        (SourceKind.MEETING, str(meeting), "Design review")
    ]
    assert mine.provenance is Provenance.MEMORY
    assert mine.sources == ()


async def test_recall_says_why_it_gives_nothing(tools_bench: ToolsBench) -> None:
    off, refusing = uuid.uuid4(), uuid.uuid4()
    await tools_bench.add(off, [{"statement": "Held"}])
    await tools_bench.add(refusing, [{"statement": "Held"}])
    await MemorySwitch(tools_bench.homes.transactions).turn(
        Principal(off, Home.RU, 0), enabled=False
    )

    switched_off = await tools_bench.tools.recall(RecallMemory(), tools_bench.context(off))
    no_consent = await tools_bench.tools.recall(
        RecallMemory(query="anything"), tools_bench.context(refusing)
    )

    assert switched_off.error is not None
    assert switched_off.error.code is ToolErrorCode.SWITCHED_OFF
    assert no_consent.error is not None
    assert no_consent.error.code is ToolErrorCode.FORBIDDEN
    assert tools_bench.model.calls == []


async def test_forget_is_planned_whole_and_its_card_shows_the_statements_as_stored(
    tools_bench: ToolsBench,
) -> None:
    person, stranger = uuid.uuid4(), uuid.uuid4()
    first, second = await tools_bench.add(
        person, [{"statement": "Is vegetarian"}, {"statement": "Works late"}]
    )
    [theirs] = await tools_bench.add(stranger, [{"statement": "A stranger's"}])
    context = tools_bench.context(person)

    refused = await tools_bench.tools.plan_forget(ForgetMemory(fact_ids=[first, theirs]), context)
    plan = planned(
        await tools_bench.tools.plan_forget(ForgetMemory(fact_ids=[second, first, first]), context)
    )
    card = render_preview(FORGET, await tools_bench.tools.preview_forget(plan, context), "ru")

    assert isinstance(refused, ToolError)
    assert refused.code is ToolErrorCode.NOT_FOUND
    assert set(plan.targets) == {str(first), str(second)}
    assert card.title == "Забыть то, что помнит Leo"
    assert card.fields == (("Факты", "2"),)
    assert card.body == "Is vegetarian\nWorks late"


async def test_forget_forgets_exactly_the_planned_facts_once(tools_bench: ToolsBench) -> None:
    person = uuid.uuid4()
    first, edited, kept = await tools_bench.add(
        person, [{"statement": "Is vegetarian"}, {"statement": "Works late"}, {"statement": "Kept"}]
    )
    context = tools_bench.context(person)
    plan = planned(
        await tools_bench.tools.plan_forget(ForgetMemory(fact_ids=[first, edited]), context)
    )
    await MemorySwitch(tools_bench.homes.transactions).turn(
        Principal(person, Home.RU, 0), enabled=False
    )
    async with tools_bench.homes.transactions.begin(context.scope) as session:
        await session.execute(
            update(MemoryFactRecord)
            .where(MemoryFactRecord.id == edited)
            .values(valid_to=MemoryFactRecord.created_at, superseded_by=kept)
        )

    done = await tools_bench.tools.execute_forget(plan, context, "action:0")
    again = await tools_bench.tools.execute_forget(plan, context, "action:0")

    assert done.output is not None
    assert done.output.fact_ids == [first]
    assert again.output == done.output
    assert await tools_bench.statuses(person) == {
        "Is vegetarian": "forgotten", "Works late": "active", "Kept": "active",
    }  # fmt: skip
