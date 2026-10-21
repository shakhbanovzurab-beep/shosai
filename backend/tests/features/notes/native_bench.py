"""The native library, the person's notes and settings over the slot's homes (step 12).

`meeting` writes a person's meeting as the pipeline leaves it — lines, speakers, Leo's
write-up with its findings and map — so the native answers are read from real rows.
`people` gives each person a name and a language, as identity's profile does.
"""

import uuid
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import (
    ACCOUNT_PROFILE_READER,
    AUTHENTICATOR,
    AccountProfile,
)
from shosai.features.notes.application.meeting_settings import MeetingSettings
from shosai.features.notes.application.my_notes import MyNotes
from shosai.features.notes.application.native_library import NativeLibrary
from shosai.features.notes.application.participants import Participants
from shosai.features.notes.channels.http.my_notes import build_my_notes_router
from shosai.features.notes.channels.http.native_library import build_native_library_router
from shosai.features.notes.channels.http.native_words import load_native_words
from shosai.features.notes.channels.http.settings import build_settings_router
from shosai.features.notes.infrastructure.meeting_records import (
    MeetingRecord,
    SpeakerRecord,
    TranscriptLineRecord,
)
from shosai.features.notes.infrastructure.notes_records import FindingRecord, NotesRecord
from shosai.features.workspaces.application.access_policy import WorkspaceAccessPolicy
from shosai.features.workspaces.contracts import ACCESS_POLICY
from shosai.features.workspaces.infrastructure.audit_log import WorkspaceAuditLog
from tests.core.web.probe_app import build_probe_app, client_of
from tests.features.billing.people_bench import BearerOfTheTest
from tests.features.notes.library_bench import OUTBOX
from tests.features.notes.no_archive import NO_ARCHIVE
from tests.harness.database_access import DatabaseAccess

type Json = dict[str, Any]


@dataclass
class People:
    """Each person's name and language, as identity's profile reader gives them."""

    by_person: dict[uuid.UUID, tuple[str, str]] = field(default_factory=dict)

    async def profile(self, session: AsyncSession, user_id: uuid.UUID) -> AccountProfile | None:
        """The person's profile."""
        del session
        name, language = self.by_person.get(user_id, ("Anna", "en"))
        return AccountProfile(name, language, None)


@dataclass(frozen=True, slots=True)
class NativeBench:
    """The routes, the homes and the people behind them."""

    http: httpx.AsyncClient
    homes: DatabaseAccess
    people: People
    settings: MeetingSettings


@dataclass(frozen=True, slots=True)
class Written:
    """What a meeting has: lines `(start, speaker, text)`, speaker roles, the write-up."""

    lines: Sequence[tuple[int, int | None, str]] = ()
    roles: Sequence[str] = ()
    write_up: tuple[str, list[Json], list[tuple[str, str, int]]] | None = None


async def meeting(
    homes: DatabaseAccess,
    owner: uuid.UUID,
    named: tuple[str, datetime],
    written: Written | None = None,
    state: tuple[str, bool] = ("completed", True),
) -> uuid.UUID:
    """The person's meeting `(title, start)` with its lines, speakers and write-up."""
    title, started = named
    written = written or Written()
    status, kept = state
    async with homes.transactions.begin(TenancyScope(Home.EU, owner)) as session:
        record = MeetingRecord(
            id=uuid.uuid4(), user_id=owner, title=title, status=status, source="live",
            started_at=started, kept=kept, line_count=len(written.lines), seconds=1800,
            ended_at=None if status == "active" else started + timedelta(minutes=30),
        )  # fmt: skip
        session.add(record)
        await session.flush()
        session.add_all(
            TranscriptLineRecord(
                session_id=record.id, seq=seq, meeting_started_at=started,
                started_at=started + timedelta(milliseconds=start), start_ms=start,
                duration_ms=4_000, speaker_idx=speaker, text=text, origin="live",
            )
            for seq, (start, speaker, text) in enumerate(written.lines, 1)
        )  # fmt: skip
        session.add_all(
            SpeakerRecord(id=uuid.uuid4(), session_id=record.id, user_id=owner, idx=idx, role=role)
            for idx, role in enumerate(written.roles)
        )
        if written.write_up is not None:
            await write_up(session, record, written.write_up)
    return record.id


async def write_up(
    session: AsyncSession,
    record: MeetingRecord,
    notes: tuple[str, list[Json], list[tuple[str, str, int]]],
) -> None:
    """Leo's write-up of the template, its sections listing findings `(kind, text, start)`."""
    template, sections, findings = notes
    run_id = uuid.uuid4()
    ids = [uuid.uuid4() for _ in findings]
    session.add_all(
        FindingRecord(
            id=finding_id, session_id=record.id, user_id=record.user_id, run_id=run_id,
            revision=1, position=n, kind=kind, text=text, start_ms=start, end_ms=start + 1_000,
        )
        for n, (finding_id, (kind, text, start)) in enumerate(zip(ids, findings, strict=True))
    )  # fmt: skip
    listed = [
        {**s, "finding_ids": [str(ids[i]) for i in s["finding_ids"]]} if "finding_ids" in s else s
        for s in sections
    ]
    session.add(
        NotesRecord(
            session_id=record.id, user_id=record.user_id, findings_run_id=run_id,
            write_up={"version": 1, "template_id": template, "sections": listed},
            write_up_template=template, write_up_run_id=run_id,
            map={"label": record.title, "children": [{"label": "Budget", "children": []}]},
        )
    )  # fmt: skip


@pytest_asyncio.fixture
async def native_bench(homes: DatabaseAccess) -> AsyncIterator[NativeBench]:
    """The native routes and the settings over the slot's homes."""
    ports, people = PortDirectory(), People()
    ports.install(
        [
            AUTHENTICATOR.bind(BearerOfTheTest()),
            ACCESS_POLICY.bind(WorkspaceAccessPolicy(OUTBOX, WorkspaceAuditLog())),
            ACCOUNT_PROFILE_READER.bind(people),
        ]
    )
    notes = MyNotes(homes.transactions, ports, lambda: datetime.now(UTC))
    settings = MeetingSettings(homes.transactions)
    routers = (
        build_settings_router(settings, ports),
        build_native_library_router(
            (NativeLibrary(homes.transactions, ports, NO_ARCHIVE), notes, load_native_words()),
            ports,
        ),
        build_my_notes_router((notes, Participants(homes.transactions, ports)), ports),
    )
    async with client_of(build_probe_app(extra=routers).app) as http:
        yield NativeBench(http, homes, people, settings)
