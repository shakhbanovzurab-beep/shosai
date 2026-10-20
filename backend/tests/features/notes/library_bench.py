"""The cabinet's library over the slot's homes: its routes, a person's token, seeded meetings.

`seed` writes a meeting the way the pipeline leaves it: its lines, participants and
speakers, and — when it has notes — the write-up, the map and the findings of its run;
`run_state` sets its latest run's state. Rows go in the owner's scope, or the company's
for a meeting of a workspace.
"""

import uuid
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest_asyncio
from prometheus_client import CollectorRegistry

from shosai.core.events.catalog import EventTypes
from shosai.core.events.outbox import EventOutbox
from shosai.core.idempotency.ledger import EffectLedger
from shosai.core.idempotency.metrics import EffectKeyMetrics
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import AUTHENTICATOR
from shosai.features.notes.application.deletion import MeetingDeletion
from shosai.features.notes.application.folders import Folders
from shosai.features.notes.application.library import MeetingLibrary
from shosai.features.notes.application.library_counts import MeetingCounts
from shosai.features.notes.application.meeting_content import MeetingContent
from shosai.features.notes.application.my_notes import MyNotes
from shosai.features.notes.application.participants import Participants
from shosai.features.notes.application.run_rows import stage_state
from shosai.features.notes.application.templates import Templates
from shosai.features.notes.channels.http.counts import build_counts_router
from shosai.features.notes.channels.http.folders import build_folders_router
from shosai.features.notes.channels.http.meeting_content import build_meeting_content_router
from shosai.features.notes.channels.http.meetings import build_meetings_router
from shosai.features.notes.channels.http.my_notes import build_my_notes_router
from shosai.features.notes.channels.http.templates import build_templates_router
from shosai.features.notes.domain.runs import RunSource, initial_progress
from shosai.features.notes.infrastructure.meeting_records import (
    MeetingRecord,
    ParticipantRecord,
    SpeakerRecord,
    TranscriptLineRecord,
)
from shosai.features.notes.infrastructure.notes_records import (
    FindingRecord,
    FolderRecord,
    NotesRecord,
)
from shosai.features.notes.infrastructure.run_records import RunRecord
from shosai.features.notes.module import NOTES
from shosai.features.workspaces.application.access_policy import WorkspaceAccessPolicy
from shosai.features.workspaces.contracts import ACCESS_POLICY
from shosai.features.workspaces.infrastructure.audit_log import WorkspaceAuditLog
from shosai.features.workspaces.module import WORKSPACES
from tests.core.web.probe_app import build_probe_app, client_of
from tests.features.billing.people_bench import BearerOfTheTest
from tests.harness.database_access import DatabaseAccess

type Json = dict[str, Any]
LEO_SECTIONS = ("summary", "key_points", "decisions", "action_items")
KIND_OF = {"key_points": "key_point", "decisions": "decision", "action_items": "action_item"}


@dataclass(frozen=True, slots=True)
class Seeded:
    """A seeded meeting: its owner's home and id, the meeting and its run."""

    home: Home
    owner: uuid.UUID
    meeting_id: uuid.UUID
    run_id: uuid.UUID


@dataclass
class Notes:
    """What a seeded meeting's notes hold: a summary and findings by kind in their order."""

    summary: str | None = "Обсудили запуск."
    findings: Sequence[tuple[str, str]] = ()
    map_topics: Sequence[tuple[str, Sequence[str]]] = ()


@dataclass
class MeetingSeed:
    """A meeting to seed; everything but the owner has a default."""

    owner: uuid.UUID
    title: str = "Планёрка"
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC) - timedelta(hours=2))
    seconds: int = 1800
    folder_id: uuid.UUID | None = None
    lines: Sequence[tuple[int | None, int, str]] = ()
    participants: Sequence[tuple[str | None, str | None]] = ()
    speakers: Sequence[tuple[int, str, int]] = ()
    notes: Notes | None = None
    run_state: str = "succeeded"


def notes_rows(seed: MeetingSeed, meeting_id: uuid.UUID, run_id: uuid.UUID) -> list[Any]:
    """The notes, findings and map rows of a seed's write-up."""
    notes = seed.notes
    if notes is None:
        return []
    findings = [
        FindingRecord(
            id=uuid.uuid4(), session_id=meeting_id, user_id=seed.owner, run_id=run_id,
            revision=1, position=n, kind=kind, text=text, start_ms=n * 1000,
            end_ms=n * 1000 + 500, quote=text[:20], topic=None,
        )
        for n, (kind, text) in enumerate(notes.findings)
    ]  # fmt: skip
    sections: list[Json] = [{"kind": "summary", "heading_code": "summary", "text": notes.summary}]
    for section in LEO_SECTIONS[1:]:
        ids = [str(f.id) for f in findings if f.kind == KIND_OF[section]]
        sections.append({"kind": section, "heading_code": section, "finding_ids": ids})
    tree = {
        "label": seed.title,
        "children": [
            {"label": t, "children": [{"label": c, "children": []} for c in cs]}
            for t, cs in notes.map_topics
        ],
    }
    note = NotesRecord(
        session_id=meeting_id, user_id=seed.owner, findings_run_id=run_id, write_up_run_id=run_id,
        write_up={"version": 1, "template_id": "enhanced", "sections": sections},
        write_up_template="enhanced", write_up_written_at=seed.started_at, map=tree,
    )  # fmt: skip
    return [note, *findings]


async def seed_meeting(homes: DatabaseAccess, seed: MeetingSeed, home: Home = Home.EU) -> Seeded:
    """Write a meeting with its lines, people, notes and latest run."""
    meeting_id, run_id = uuid.uuid4(), uuid.uuid4()
    ended = seed.started_at + timedelta(seconds=seed.seconds)
    async with homes.transactions.begin(TenancyScope(home, seed.owner)) as session:
        session.add(
            MeetingRecord(
                id=meeting_id, user_id=seed.owner, title=seed.title, status="completed",
                started_at=seed.started_at, ended_at=ended, seconds=seed.seconds,
                folder_id=seed.folder_id, line_count=len(seed.lines), notes_revision=1,
                latest_run_id=run_id,
            )
        )  # fmt: skip
        await session.flush()
        session.add(
            RunRecord(
                id=run_id, session_id=meeting_id, user_id=seed.owner, source="live",
                idempotency_key="live", state=seed.run_state,
                stage_state=stage_state(initial_progress(RunSource.LIVE)),
            )
        )  # fmt: skip
        session.add_all(meeting_children(seed, meeting_id, run_id))
    return Seeded(home, seed.owner, meeting_id, run_id)


def meeting_children(seed: MeetingSeed, meeting_id: uuid.UUID, run_id: uuid.UUID) -> list[Any]:
    lines = [
        TranscriptLineRecord(
            session_id=meeting_id, seq=seq, meeting_started_at=seed.started_at,
            started_at=seed.started_at + timedelta(seconds=second), start_ms=second * 1000,
            duration_ms=900, speaker_idx=speaker, text=text,
        )
        for seq, (speaker, second, text) in enumerate(seed.lines, 1)
    ]  # fmt: skip
    people = [
        ParticipantRecord(
            id=uuid.uuid4(), session_id=meeting_id, user_id=seed.owner, name=name,
            email=email, created_at=seed.started_at + timedelta(seconds=n),
        )
        for n, (name, email) in enumerate(seed.participants)
    ]  # fmt: skip
    speakers = [
        SpeakerRecord(
            id=uuid.uuid4(), session_id=meeting_id, user_id=seed.owner, idx=idx, role=role,
            talk_ms=talk,
        )
        for idx, role, talk in seed.speakers
    ]  # fmt: skip
    return [*lines, *people, *speakers, *notes_rows(seed, meeting_id, run_id)]


@dataclass
class LibraryBench:
    """The library's client and the slot's homes."""

    http: httpx.AsyncClient
    homes: DatabaseAccess

    async def seed(self, seed: MeetingSeed, home: Home = Home.EU) -> Seeded:
        """Write a meeting with its lines, people, notes and latest run."""
        return await seed_meeting(self.homes, seed, home)

    async def folder(
        self, owner: uuid.UUID, name: str = "Клиенты", home: Home = Home.EU
    ) -> uuid.UUID:
        """A folder of the person's."""
        folder_id = uuid.uuid4()
        async with self.homes.transactions.begin(TenancyScope(home, owner)) as session:
            session.add(FolderRecord(id=folder_id, user_id=owner, name=name, color="green"))
        return folder_id

    async def get(self, who: uuid.UUID, path: str, **params: str | int) -> httpx.Response:
        """A GET as the person, in the EU home."""
        return await self.http.get(path, params=params, headers=bearer(who))

    async def every(self, who: uuid.UUID, path: str, **params: str | int) -> list[Json]:
        """Every item of a collection, page after page."""
        items: list[Json] = []
        cursor = None
        while True:
            query = {**params, **({"cursor": cursor} if cursor else {})}
            answer = await self.get(who, path, **query)
            assert answer.status_code == 200, answer.text
            body = answer.json()
            items += body["items"]
            cursor = body["next_cursor"]
            if cursor is None:
                return items


def bearer(who: uuid.UUID, home: Home = Home.EU) -> dict[str, str]:
    """The person's Authorization header."""
    return {"Authorization": f"Bearer person:{who}:{home.value}"}


OUTBOX = EventOutbox(EventTypes([*NOTES.events, *WORKSPACES.events]))


def library_ports() -> PortDirectory:
    """The test's bearer and workspaces' access policy."""
    ports = PortDirectory()
    outbox = OUTBOX
    ports.install(
        [
            AUTHENTICATOR.bind(BearerOfTheTest()),
            ACCESS_POLICY.bind(WorkspaceAccessPolicy(outbox, WorkspaceAuditLog())),
        ]
    )
    return ports


@pytest_asyncio.fixture
async def library_bench(homes: DatabaseAccess) -> AsyncIterator[LibraryBench]:
    """The library and a meeting's content over the slot's homes."""
    ports, transactions = library_ports(), homes.transactions
    effects = EffectLedger(EffectKeyMetrics(CollectorRegistry()))
    # Порядок как в модуле: папки, счётчики и шаблоны раньше /v1/notes/{meeting_id}.
    routers = (
        build_folders_router(Folders(transactions, effects), ports),
        build_counts_router(MeetingCounts(transactions, ports), ports),
        build_templates_router(Templates(transactions, effects), ports),
        build_meetings_router(
            (MeetingLibrary(transactions, ports), MeetingDeletion(transactions, (ports, OUTBOX))),
            ports,
        ),
        build_meeting_content_router(MeetingContent(transactions, ports), ports),
        build_my_notes_router(
            (MyNotes(transactions, ports), Participants(transactions, ports)), ports
        ),
    )
    async with client_of(build_probe_app(extra=routers).app) as http:
        yield LibraryBench(http, homes)
