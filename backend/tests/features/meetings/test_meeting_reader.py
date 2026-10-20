"""Other slices' readers of meetings (step 15): `MeetingReader` and `MeetingFindings` give a
viewer exactly what §7 allows, and nobody a deleted meeting, a meeting not kept or a meeting
of an account in identity's deletion window, which a cancellation brings back unchanged.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, update

from shosai.core.events.subscriptions import ReceivedEvent
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.pagination.cursor import InvalidCursorError
from shosai.features.identity.contracts import AccountDeletionCancelled, AccountDeletionScheduled
from shosai.features.meetings.application.import_rows import RecordingObject, open_import
from shosai.features.meetings.application.meeting_reader import MeetingsFindings, MeetingsReader
from shosai.features.meetings.channels.agent_tool_reads import MeetingReads
from shosai.features.meetings.channels.agent_tools import MeetingId, SearchMeetings
from shosai.features.meetings.channels.subscriptions import hide_with_account, show_with_account
from shosai.features.meetings.contracts import MeetingNotFoundError
from shosai.features.meetings.domain.findings import FindingKind
from shosai.features.meetings.infrastructure.meeting_records import (
    MEETING_RESOURCE,
    MeetingRecord,
)
from shosai.features.meetings.infrastructure.notes_records import SettingsRecord
from shosai.features.workspaces.contracts import Viewer
from shosai.features.workspaces.infrastructure.share_records import SHARE_RECORDS
from tests.features.meetings.library_bench import MeetingSeed, Notes, library_ports, seed_meeting
from tests.features.meetings.meeting_bench import MeetingBench
from tests.features.meetings.test_agent_tools import context
from tests.features.meetings.test_library_isolation import meetings, world
from tests.features.meetings.test_native_lifecycle import started
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot
from tests.support.access_model import MemberRow, ShareRow, WorkspaceRow, World, readable
from tests.support.isolation import write_world

HOME = Home.EU
START = datetime.now(UTC).replace(day=1, hour=1, minute=0, second=0, microsecond=0)
LINES = [(0, 0, "Hello."), (1, 4, "Budget first."), (0, 9, "Agreed."), (1, 15, "Thanks.")]
NOTES = Notes(summary="We agreed the budget.", findings=[("decision", "Budget agreed.")])


def scope(user_id: uuid.UUID) -> TenancyScope:
    return TenancyScope(HOME, user_id)


async def read_by(
    homes: DatabaseAccess, person: uuid.UUID, meeting_ids: list[uuid.UUID]
) -> set[uuid.UUID]:
    """The meetings the reader names for the person, after checking the batch agrees."""
    reader, viewer = MeetingsReader(library_ports()), Viewer(person)
    async with homes.transactions.begin(scope(person), read_only=True) as session:
        facts = await reader.facts(session, viewer, meeting_ids)
        checked = await reader.readable(session, viewer, meeting_ids)
    assert set(facts) == checked
    return set(checked)


async def opened_by(homes: DatabaseAccess, person: uuid.UUID, meeting_id: uuid.UUID) -> bool:
    """Whether the person reads the meeting's transcript and findings; both or neither."""
    ports = library_ports()
    reader, findings, viewer = MeetingsReader(ports), MeetingsFindings(ports), Viewer(person)
    answers = []
    async with homes.transactions.begin(scope(person), read_only=True) as session:
        for read in (
            reader.transcript(session, viewer, meeting_id, None, 10),
            findings.of(session, viewer, meeting_id),
        ):
            try:
                await read
                answers.append(True)
            except MeetingNotFoundError:
                answers.append(False)
    assert answers[0] == answers[1]
    return answers[0]


@pytest.mark.isolation(resource="meeting")
async def test_the_readers_give_each_person_exactly_what_they_may_read(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    canon = await world(run_slot)
    every = meetings(canon)

    for name, person in canon.people.items():
        allowed = readable(canon.world, MEETING_RESOURCE.kind, person)
        assert await read_by(homes, person, every) == allowed, name
        opened = {m for m in every if await opened_by(homes, person, m)}
        assert opened == allowed, name


async def shared_into_a_workspace(
    homes: DatabaseAccess, run_slot: RunSlot, owner: uuid.UUID, member: uuid.UUID
) -> uuid.UUID:
    """The owner's spoken meeting with notes, shared with the whole workspace both belong to."""
    seeded = await seed_meeting(
        homes, MeetingSeed(owner, started_at=START, lines=LINES, notes=NOTES), HOME
    )
    org_id, owner_seat, member_seat = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    shared = World(
        workspaces=[WorkspaceRow(org_id, "active")],
        members=[
            MemberRow(owner_seat, org_id, owner, "owner", "active"),
            MemberRow(member_seat, org_id, member, "member", "active"),
        ],
        rows=[],
        shares=[
            ShareRow(
                "meeting", seeded.meeting_id, org_id, "organization", owner_seat,
                SHARE_RECORDS["meeting"].grant_kind, uuid.uuid4(),
            )
        ],
    )  # fmt: skip
    await write_world(run_slot.claimed.connections[HOME], MEETING_RESOURCE, shared)
    return seeded.meeting_id


async def deliver(
    homes: DatabaseAccess,
    owner: uuid.UUID,
    event: AccountDeletionScheduled | AccountDeletionCancelled,
    at: datetime,
) -> None:
    """One delivery of identity's event, in the person's scope as identity writes it."""
    async with homes.transactions.begin(scope(owner)) as session:
        if isinstance(event, AccountDeletionScheduled):
            await hide_with_account(
                session, ReceivedEvent(event, uuid.uuid4(), 1, at, scope(owner))
            )
        else:
            await show_with_account(
                session, ReceivedEvent(event, uuid.uuid4(), 1, at, scope(owner))
            )


async def test_an_account_in_its_window_is_read_by_nobody_and_a_cancellation_restores_it(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    owner, member = uuid.uuid4(), uuid.uuid4()
    meeting_id = await shared_into_a_workspace(homes, run_slot, owner, member)
    leo = MeetingReads(homes.transactions, library_ports())
    start = datetime.now(UTC)
    scheduled = AccountDeletionScheduled(user_id=owner, erase_at=start + timedelta(days=7))

    async def seen() -> list[bool]:
        """Owner and member: the reader, the transcript and findings, Leo's search and get."""
        found = []
        for person in (owner, member):
            searched = await leo.search(SearchMeetings(), context(person))
            got = await leo.get(MeetingId(meeting_id=meeting_id), context(person))
            assert searched.output is not None
            found += [
                meeting_id in await read_by(homes, person, [meeting_id]),
                await opened_by(homes, person, meeting_id),
                [m.meeting_id for m in searched.output.meetings] == [meeting_id],
                got.error is None,
            ]
        return found

    before = await seen()
    await deliver(homes, owner, scheduled, start)
    hidden = await seen()
    await deliver(
        homes, owner, AccountDeletionCancelled(user_id=owner), start + timedelta(minutes=2)
    )
    await deliver(homes, owner, scheduled, start + timedelta(minutes=1))
    after = await seen()

    assert before == [True] * 8
    assert hidden == [False] * 8
    assert after == [True] * 8
    async with homes.transactions.begin(scope(member), read_only=True) as session:
        page = await MeetingsReader(library_ports()).transcript(
            session, Viewer(member), meeting_id, None, 10
        )
    assert [line.text for line in page.lines] == [text for _, _, text in LINES]


async def test_a_deleted_meeting_and_one_not_kept_are_read_by_nobody(
    homes: DatabaseAccess,
) -> None:
    owner = uuid.uuid4()
    ids = [
        (
            await seed_meeting(homes, MeetingSeed(owner, started_at=START, lines=LINES), HOME)
        ).meeting_id
        for _ in range(3)
    ]
    kept, unkept, deleted = ids
    async with homes.transactions.begin(scope(owner)) as session:
        await session.execute(
            update(MeetingRecord).where(MeetingRecord.id == unkept).values(kept=False)
        )
        await session.execute(
            update(MeetingRecord).where(MeetingRecord.id == deleted).values(deleted_at=START)
        )

    assert await read_by(homes, owner, ids) == {kept}
    assert [await opened_by(homes, owner, m) for m in ids] == [True, False, False]


async def test_facts_findings_and_transcript_pages_of_a_meeting(homes: DatabaseAccess) -> None:
    owner = uuid.uuid4()
    notes = Notes(
        summary="We agreed the budget.",
        findings=[("decision", "Budget agreed."), ("action_item", "Send the estimate.")],
    )
    people = [("Anna Smith", "anna@example.com"), (None, "bob@corp.com")]
    seed = MeetingSeed(
        owner, title="Budget", started_at=START, lines=LINES, participants=people, notes=notes
    )
    meeting_id = (await seed_meeting(homes, seed, HOME)).meeting_id
    ports, viewer = library_ports(), Viewer(owner)
    reader = MeetingsReader(ports)

    async with homes.transactions.begin(scope(owner), read_only=True) as session:
        facts = (await reader.facts(session, viewer, [meeting_id, uuid.uuid4()]))[meeting_id]
        listed = await MeetingsFindings(ports).of(session, viewer, meeting_id)
        pages, texts = 0, list[str]()
        cursor: str | None = None
        while True:
            page = await reader.transcript(session, viewer, meeting_id, cursor, 3)
            pages, texts = pages + 1, texts + [line.text for line in page.lines]
            if page.next_cursor is None:
                break
            cursor = page.next_cursor
        with pytest.raises(InvalidCursorError):
            await reader.transcript(session, viewer, meeting_id, "not-a-cursor", 3)
        with pytest.raises(ValueError, match="страница"):
            await reader.transcript(session, viewer, meeting_id, None, 501)
        assert await reader.facts(session, viewer, []) == {}
        assert await reader.readable(session, viewer, []) == frozenset()

    assert (facts.title, facts.user_id, facts.org_id, facts.seconds) == (
        "Budget",
        owner,
        None,
        1800,
    )
    assert facts.summary == "We agreed the budget."
    assert [(p.name, p.email) for p in facts.participants] == people
    assert [(f.kind, f.text) for f in listed] == [
        (FindingKind.DECISION, "Budget agreed."), (FindingKind.ACTION_ITEM, "Send the estimate."),
    ]  # fmt: skip
    assert (pages, texts) == (2, [text for _, _, text in LINES])


async def test_a_meeting_made_while_the_window_runs_is_hidden_with_the_account(
    meeting_bench: MeetingBench,
) -> None:
    person = uuid.uuid4()
    own = TenancyScope(Home.RU, person)
    async with meeting_bench.homes.transactions.begin(own) as session:
        session.add(SettingsRecord(user_id=person, account_hidden=True))
    # Запросы, начатые до окна удаления, ещё могут создать встречу.
    live = uuid.UUID(await started(meeting_bench, person))
    recording = RecordingObject(uuid.uuid4(), "transient/import/x", "audio/mpeg", 10, "call.mp3")
    async with meeting_bench.homes.transactions.begin(own) as session:
        imported = await open_import(session, person, recording, datetime.now(UTC))
        marks = await session.execute(
            select(MeetingRecord.id, MeetingRecord.account_hidden).where(
                MeetingRecord.user_id == person
            )
        )
        hidden = dict(marks.all())

    assert hidden == {live: True, imported.meeting_id: True}
