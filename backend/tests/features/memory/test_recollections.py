"""A meeting's recollection: candidates with their evidence, the meeting's label and space, a
participant's words never taken as the owner's, nothing with memory off, without consent or
for a meeting the owner cannot read, nothing twice, and only the first notes recollected
(memory step 9, MM-D5)."""

import uuid
from datetime import UTC, datetime

from shosai.core.events.subscriptions import ReceivedEvent
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.tasks.declaration import TaskDeclaration
from shosai.core.tasks.payloads import TaskPayload
from shosai.features.identity.contracts import Principal
from shosai.features.memory.application.switch import MemorySwitch
from shosai.features.memory.channels.subscriptions import subscriptions
from shosai.features.memory.domain.admission import Admission
from shosai.features.notes.contracts.events import NotesReady
from tests.features.memory.recall_bench import axis
from tests.features.memory.recollection_bench import RecollectionBench
from tests.harness.database_access import DatabaseAccess

POINTS = [
    "Anna Petrova will own the launch checklist",
    "Mara leads design for the launch",
    "Mara said she prefers async reviews",
]


def said(
    statement: str, evidence: str, *, about_person: bool, kind: str = "relationship"
) -> dict[str, object]:
    """One statement as the recollections model answers it."""
    return {
        "statement": statement, "kind": kind, "sensitive": False,
        "about_person": about_person, "evidence": evidence,
    }  # fmt: skip


async def test_a_meeting_gives_candidates_with_evidence_and_never_a_participant_s_words(
    recollection_bench: RecollectionBench,
) -> None:
    owner, org = uuid.uuid4(), uuid.uuid4()
    recollection_bench.consents.given.add(owner)
    meeting, points = recollection_bench.notes.held(owner, POINTS, org)
    recollection_bench.vectors.known |= {
        "Owns the launch checklist": axis(1), "Mara leads design": axis(0, 1),
        "Prefers async reviews": axis(0, 0, 0, 1),
    }  # fmt: skip
    recollection_bench.writer.answers["memory.recollect"] = [
        {"statements": [
            said("Owns the launch checklist", "K1", about_person=True, kind="fact"),
            said("Mara leads design", "K2", about_person=False),
            said("Prefers async reviews", "K3", about_person=True, kind="preference"),
            said("Invented", "K9", about_person=False),
        ]}
    ]  # fmt: skip

    outcomes = await recollection_bench.recollection.recollect(Home.RU, owner, meeting)
    again = await recollection_bench.recollection.recollect(Home.RU, owner, meeting)
    facts = await recollection_bench.facts(owner)

    assert outcomes == again == [Admission.CANDIDATE, Admission.CANDIDATE]
    assert len(recollection_bench.writer.asked) == 1
    assert {fact.statement: fact.source_ref["finding_id"] for fact in facts} == {
        "Owns the launch checklist": str(points[0]), "Mara leads design": str(points[1]),
    }  # fmt: skip
    assert {(f.status, f.source_kind, f.source_taint, f.confirmed, f.org_id) for f in facts} == {
        ("candidate", "meeting", "external", False, org)
    }
    assert {fact.source_ref["meeting_id"] for fact in facts} == {str(meeting)}
    _, read = recollection_bench.writer.asked[0]
    assert "K2 Mara leads design for the launch" in read
    assert "anna@example.com" not in read


async def test_nothing_is_recollected_with_memory_off_without_consent_or_unreadable(
    recollection_bench: RecollectionBench,
) -> None:
    off, refusing, stranger = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    recollection_bench.consents.given |= {off, stranger}
    await MemorySwitch(recollection_bench.homes.transactions).turn(
        Principal(off, Home.RU, 0), enabled=False
    )
    held = {person: recollection_bench.notes.held(person, POINTS)[0] for person in (off, refusing)}
    theirs, _ = recollection_bench.notes.held(uuid.uuid4(), POINTS)

    outcomes = [
        await recollection_bench.recollection.recollect(Home.RU, off, held[off]),
        await recollection_bench.recollection.recollect(Home.RU, refusing, held[refusing]),
        await recollection_bench.recollection.recollect(Home.RU, stranger, theirs),
    ]

    assert outcomes == [[], [], []]
    assert recollection_bench.writer.asked == []


class Queue:
    """The task queue: what was sent."""

    def __init__(self) -> None:
        self.sent: list[TaskPayload] = []

    async def send[P: TaskPayload](self, task: TaskDeclaration[P], payload: P) -> str:
        """Note the payload."""
        del task
        self.sent.append(payload)
        return "task"


async def test_only_a_meeting_s_first_notes_are_recollected(homes: DatabaseAccess) -> None:
    queue, owner, meeting = Queue(), uuid.uuid4(), uuid.uuid4()
    [recollect] = [
        item for item in subscriptions(queue) if item.consumer == "memory.recollect_meeting"
    ]
    scope = TenancyScope(Home.RU, owner)
    for revision in (1, 2):
        event = NotesReady(
            meeting_id=meeting, run_id=uuid.uuid4(), user_id=owner, revision=revision
        )
        received = ReceivedEvent(event, uuid.uuid4(), 1, datetime.now(UTC), scope)
        async with homes.transactions.begin(scope, read_only=True) as session:
            await recollect.handle(session, received)

    assert [getattr(payload, "meeting_id", None) for payload in queue.sent] == [meeting]
