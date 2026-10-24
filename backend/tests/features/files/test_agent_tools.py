"""Leo's `files` toolset (files step 9): reads return only what the person may read; a write
plans one target and executes on it alone, once per item key, with one audit event.
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from shosai.core.agent_tools.context import ToolContext
from shosai.core.agent_tools.provenance import Provenance
from shosai.core.agent_tools.results import PlannedEffect, ToolError, ToolErrorCode
from shosai.core.agent_tools.sources import SourceKind
from shosai.core.events.records import OutboxMessage
from shosai.core.kernel.homes import Home
from shosai.features.files.application.file_edits import FileChanges
from shosai.features.files.channels.agent_tools import (
    DeleteFile,
    ExcerptGap,
    MoveFile,
    ReadFile,
    SearchFiles,
    SetLeoUse,
)
from shosai.features.files.domain.leo import LeoVia
from shosai.features.identity.contracts import Principal
from tests.features.files.file_bench import FileBench
from tests.features.files.test_account_window import shared_file
from tests.features.files.upload_bench import person
from tests.harness.run_slot import RunSlot

AUDIT = "agent.action_item.executed"


def context(who: Principal) -> ToolContext:
    return ToolContext(who.scope(), uuid.uuid4(), datetime.now(UTC) + timedelta(minutes=1))


async def audited(bench: FileBench, who: Principal) -> int:
    """How many action items of the person took effect."""
    async with bench.uploads.transactions.begin(who.scope(), read_only=True) as session:
        count = await session.scalar(
            select(func.count())
            .select_from(OutboxMessage)
            .where(OutboxMessage.user_id == who.user_id, OutboxMessage.event_type == AUDIT)
        )
    return count or 0


async def test_the_search_finds_only_readable_files_by_part_of_their_name(
    file_bench: FileBench, run_slot: RunSlot
) -> None:
    owner, member = person(Home.RU, uuid.uuid4()), person(Home.RU, uuid.uuid4())
    shared = await shared_file(file_bench, run_slot, owner, member)
    stranger = person(Home.RU, uuid.uuid4())
    budget = await file_bench.file(owner, "Budget 2026.txt", b"q1 " * 10)
    await file_bench.file(owner, "Отчёт 100%.md", b"text")
    await file_bench.file(stranger, "Budget secret.txt", b"no")
    reads = file_bench.reads

    found = (await reads.search(SearchFiles(query="BUDGET"), context(owner))).output
    russian = (await reads.search(SearchFiles(query="Отчёт 100%"), context(owner))).output
    percent = (await reads.search(SearchFiles(query="%"), context(owner))).output
    by_member = (await reads.search(SearchFiles(query="plan"), context(member))).output
    first = (await reads.search(SearchFiles(query="t", limit=1), context(owner))).output

    assert found is not None
    assert [(f.file_id, f.owned) for f in found.files] == [(budget.id, True)]
    assert russian is not None
    assert [f.name for f in russian.files] == ["Отчёт 100%.md"]
    assert percent is not None
    assert [f.name for f in percent.files] == ["Отчёт 100%.md"]
    assert by_member is not None
    [hit] = by_member.files
    assert (hit.file_id, hit.owned, hit.folder_id, hit.leo) == (shared, False, None, None)
    assert first is not None
    assert (len(first.files), first.more) == (1, True)


async def test_the_digest_quotes_plain_text_only_and_never_a_stranger_s_file(
    file_bench: FileBench,
) -> None:
    who, stranger = person(Home.EU, uuid.uuid4()), person(Home.EU, uuid.uuid4())
    notes = await file_bench.file(who, "Notes.md", "Привет, Leo\n".encode() * 3)
    long = await file_bench.file(who, "Long.txt", b"x" * 20_000)
    report = await file_bench.file(who, "Report.pdf", b"%PDF-1.7")
    reads = file_bench.reads

    quoted = (await reads.read(ReadFile(file_id=notes.id), context(who))).output
    cut = (await reads.read(ReadFile(file_id=long.id), context(who))).output
    pdf = (await reads.read(ReadFile(file_id=report.id), context(who))).output
    foreign = await reads.read(ReadFile(file_id=notes.id), context(stranger))

    assert quoted is not None
    assert (quoted.excerpt, quoted.excerpt_truncated) == ("Привет, Leo\n" * 3, False)
    assert cut is not None
    assert (len(cut.excerpt or ""), cut.excerpt_truncated) == (6_000, True)
    assert pdf is not None
    assert (pdf.excerpt, pdf.no_excerpt) == (None, ExcerptGap.NOT_TEXT)
    assert foreign.error is not None
    assert foreign.error.code is ToolErrorCode.NOT_FOUND


async def test_a_move_executes_on_its_planned_file_alone_and_once_per_key(
    file_bench: FileBench,
) -> None:
    who = person(Home.RU, uuid.uuid4())
    planned_file = await file_bench.file(who, "A.txt", b"a")
    other = await file_bench.file(who, "B.txt", b"b")
    folder = await file_bench.folders.create(who, "Archive")
    writes, key = file_bench.writes, f"{uuid.uuid4()}:0"

    plan = await writes.plan_move(
        MoveFile(file_id=planned_file.id, folder_id=folder.id), context(who)
    )
    assert isinstance(plan, PlannedEffect)
    preview = await writes.preview_move(plan, context(who))
    first = await writes.execute_move(plan, context(who), key)
    again = await writes.execute_move(plan, context(who), key)
    _, files = await file_bench.manager.listing(who)

    assert (preview.key, dict(preview.params)) == (
        "agent.files.move", {"name": "A.txt", "folder": "Archive"},
    )  # fmt: skip
    assert first.output == again.output
    assert {f.id: f.folder_id for f in files} == {planned_file.id: folder.id, other.id: None}
    assert await audited(file_bench, who) == 1


async def test_leo_s_switch_and_a_deletion_go_through_plan_and_refusals_are_typed(
    file_bench: FileBench,
) -> None:
    who, stranger = person(Home.EU, uuid.uuid4()), person(Home.EU, uuid.uuid4())
    notes = await file_bench.file(who, "Notes.txt", b"n" * 100)
    picture = await file_bench.file(who, "Photo.png", b"p")
    writes = file_bench.writes

    foreign = await writes.plan_delete(DeleteFile(file_id=notes.id), context(stranger))
    unreadable = await writes.plan_leo_use(SetLeoUse(file_id=picture.id, use=True), context(who))
    switch = await writes.plan_leo_use(SetLeoUse(file_id=notes.id, use=True), context(who))
    assert isinstance(switch, PlannedEffect)
    file_bench.uploads.plan.knowledge_base_mb = 0
    refused = await writes.execute_leo_use(switch, context(who), f"{uuid.uuid4()}:0")
    file_bench.uploads.plan.knowledge_base_mb = 100
    switched = await writes.execute_leo_use(switch, context(who), f"{uuid.uuid4()}:0")
    deletion = await writes.plan_delete(DeleteFile(file_id=notes.id), context(who))
    assert isinstance(deletion, PlannedEffect)
    deleted = await writes.execute_delete(deletion, context(who), f"{uuid.uuid4()}:0")
    _, files = await file_bench.manager.listing(who)

    assert isinstance(foreign, ToolError)
    assert foreign.code is ToolErrorCode.NOT_FOUND
    assert isinstance(unreadable, ToolError)
    assert (unreadable.code, dict(unreadable.params)) == (
        ToolErrorCode.FAILED, {"reason": "leo_unreadable"},
    )  # fmt: skip
    assert refused.error is not None
    assert (refused.error.code, dict(refused.error.params)) == (
        ToolErrorCode.LIMIT_REACHED, {"limit_bytes": 0},
    )  # fmt: skip
    assert switched.output is not None
    assert switched.output.use is True
    assert deleted.output is not None
    assert [f.id for f in files] == [picture.id]
    assert await file_bench.leo_events(who) == [(notes.id, True)]
    assert await audited(file_bench, who) == 2


async def test_a_folder_switch_by_leo_makes_its_files_used(file_bench: FileBench) -> None:
    who = person(Home.RU, uuid.uuid4())
    folder = await file_bench.folders.create(who, "Research")
    notes = await file_bench.file(who, "Notes.md", b"r")
    await file_bench.manager.update(who, notes.id, FileChanges(move=True, folder_id=folder.id))
    writes = file_bench.writes

    plan = await writes.plan_leo_use(SetLeoUse(folder_id=folder.id, use=True), context(who))
    assert isinstance(plan, PlannedEffect)
    preview = await writes.preview_leo_use(plan, context(who))
    await writes.execute_leo_use(plan, context(who), f"{uuid.uuid4()}:0")
    _, [view] = await file_bench.manager.listing(who)

    assert dict(preview.params) == {"target": "folder", "use": True, "name": "Research"}
    assert view.leo is not None
    assert view.leo.via is LeoVia.FOLDER


async def test_a_read_names_its_file_in_its_space_and_labels_whose_text_it_is(
    file_bench: FileBench, run_slot: RunSlot
) -> None:
    owner, member = person(Home.RU, uuid.uuid4()), person(Home.RU, uuid.uuid4())
    shared = await shared_file(file_bench, run_slot, owner, member)
    own = await file_bench.file(member, "Mine.txt", b"my words")
    reads = file_bench.reads

    mine = await reads.read(ReadFile(file_id=own.id), context(member))
    found = await reads.search(SearchFiles(query="plan"), context(member))
    by_owner = await reads.search(SearchFiles(query="plan"), context(owner))

    assert [(s.kind, s.id, s.title, s.org_id, s.quote) for s in mine.sources] == [
        (SourceKind.FILE, str(own.id), "Mine.txt", None, "my words")
    ]
    assert mine.provenance is Provenance.FILE_OWN
    # Файл коллеги, поделённый в workspace, назван этим workspace, а его текст — чужим.
    [source] = found.sources
    assert (source.id, source.org_id is not None) == (str(shared), True)
    assert found.provenance is Provenance.FILE_FOREIGN
    assert [s.org_id for s in by_owner.sources] == [None]
    assert by_owner.provenance is Provenance.FILE_OWN
