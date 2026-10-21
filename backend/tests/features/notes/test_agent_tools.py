"""Leo's read tools over meetings (step 14): only what the person may read, within budget."""

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from shosai.core.agent_tools.context import ToolContext
from shosai.core.agent_tools.results import ToolErrorCode
from shosai.core.agent_tools.spec import Provenance
from shosai.core.ai.spend.estimates import tokens_of
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.notes.channels.agent_tool_reads import MeetingReads
from shosai.features.notes.channels.agent_tools import (
    READ_TOOLS,
    TRANSCRIPT_BUDGET,
    ListFindings,
    MeetingId,
    ReadTranscript,
    SearchMeetings,
)
from shosai.features.notes.domain.findings import FindingKind
from shosai.features.notes.infrastructure.meeting_records import MEETING_RESOURCE
from tests.features.notes.library_bench import library_ports
from tests.features.notes.native_bench import Written, meeting
from tests.features.notes.no_archive import NO_ARCHIVE
from tests.features.notes.test_library_isolation import meetings, world
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot
from tests.support.access_model import readable

START = datetime.now(UTC).replace(day=1, hour=1, minute=0, second=0, microsecond=0)
SECTIONS: list[dict[str, Any]] = [
    {"kind": "summary", "heading_code": "summary", "text": "We agreed the budget."},
    {"kind": "action_items", "heading_code": "action_items", "finding_ids": [0]},
]


def context(person: uuid.UUID) -> ToolContext:
    """A call acting for the person, in the EU home."""
    return ToolContext(
        TenancyScope(Home.EU, person), uuid.uuid4(), datetime.now(UTC) + timedelta(minutes=1)
    )


def test_every_meetings_tool_labels_its_result_as_meeting_speech() -> None:
    assert {spec.name: spec.provenance for spec in READ_TOOLS} == {
        "notes.search": Provenance.MEETING_SPEECH, "notes.get": Provenance.MEETING_SPEECH,
        "notes.read_transcript": Provenance.MEETING_SPEECH,
        "notes.list_findings": Provenance.MEETING_SPEECH,
    }  # fmt: skip
    assert {spec.toolset for spec in READ_TOOLS} == {"notes"}


@pytest.mark.isolation(resource="meeting")
async def test_a_tool_never_returns_a_meeting_the_person_may_not_read(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    canon = await world(run_slot)
    reads = MeetingReads(homes.transactions, library_ports(), NO_ARCHIVE)
    kind = MEETING_RESOURCE.kind

    for name, person in canon.people.items():
        allowed = readable(canon.world, kind, person)
        found = await reads.search(SearchMeetings(limit=20), context(person))
        assert found.output is not None
        assert {m.meeting_id for m in found.output.meetings} == allowed, name
        for meeting_id in meetings(canon):
            answers = [
                await reads.get(MeetingId(meeting_id=meeting_id), context(person)),
                await reads.read_transcript(ReadTranscript(meeting_id=meeting_id), context(person)),
                await reads.list_findings(ListFindings(meeting_id=meeting_id), context(person)),
            ]
            refused = [
                a.error is not None and a.error.code is ToolErrorCode.NOT_FOUND for a in answers
            ]
            assert refused == [meeting_id not in allowed] * 3, (name, meeting_id)


async def test_a_transcript_reads_page_by_page_within_its_budget(homes: DatabaseAccess) -> None:
    owner = uuid.uuid4()
    lines = [(n * 10_000, n % 3, f"Line {n}: " + "word " * 90) for n in range(400)]
    meeting_id = await meeting(homes, owner, ("Long", START), Written(lines))
    reads = MeetingReads(homes.transactions, library_ports(), NO_ARCHIVE)

    seen: list[str] = []
    pages, start = 0, 0
    while True:
        page = await reads.read_transcript(
            ReadTranscript(meeting_id=meeting_id, from_ms=start), context(owner)
        )
        assert page.output is not None
        pages += 1
        assert tokens_of(json.dumps(page.output.model_dump(mode="json"))) <= TRANSCRIPT_BUDGET
        seen += [line.text for line in page.output.lines]
        if page.output.next_from_ms is None:
            break
        start = page.output.next_from_ms

    assert seen == [text for _, _, text in lines]
    assert pages > 1


async def test_the_digest_and_findings_of_a_meeting_and_the_search_filters(
    homes: DatabaseAccess,
) -> None:
    owner = uuid.uuid4()
    findings = [("action_item", "Send the estimate.", 13_000)]
    written = Written(
        [(0, 0, "Hello."), (5_000, 1, "Hi.")], write_up=("enhanced", SECTIONS, findings)
    )
    budget = await meeting(homes, owner, ("Budget Q4", START), written)
    await meeting(homes, owner, ("Hiring", START + timedelta(days=2)))
    reads = MeetingReads(homes.transactions, library_ports(), NO_ARCHIVE)

    digest = await reads.get(MeetingId(meeting_id=budget), context(owner))
    listed = await reads.list_findings(
        ListFindings(meeting_id=budget, kind=FindingKind.ACTION_ITEM), context(owner)
    )
    none = await reads.list_findings(
        ListFindings(meeting_id=budget, kind=FindingKind.RISK), context(owner)
    )
    by_title = await reads.search(SearchMeetings(query="budget"), context(owner))
    by_day = await reads.search(
        SearchMeetings(started_from=(START + timedelta(days=1)).date()), context(owner)
    )
    transcript = await reads.read_transcript(ReadTranscript(meeting_id=budget), context(owner))

    assert digest.output is not None
    assert (digest.output.summary, digest.output.findings.action_items) == (
        "We agreed the budget.",
        1,
    )
    assert digest.output.transcript_lines == 2
    assert listed.output is not None
    assert [(f.text, f.at_ms) for f in listed.output.findings] == [("Send the estimate.", 13_000)]
    assert none.output is not None
    assert none.output.findings == []
    assert by_title.output is not None
    assert [m.title for m in by_title.output.meetings] == ["Budget Q4"]
    assert by_day.output is not None
    assert [m.title for m in by_day.output.meetings] == ["Hiring"]
    assert transcript.output is not None
    assert [(line.speaker, line.owner_voice) for line in transcript.output.lines] == [
        (1, True),
        (2, False),
    ]
