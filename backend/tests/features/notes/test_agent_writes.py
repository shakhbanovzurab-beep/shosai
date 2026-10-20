"""Leo's write tools of `notes` (step 16): planned, previewed, executed once per item key."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update

from shosai.core.agent_tools.results import PlannedEffect, ToolError, ToolErrorCode
from shosai.core.agent_tools.spec import CostClass, Reversibility
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.notes.channels.agent_write_tools import (
    WRITE_TOOLS,
    MoveToFolder,
    RegenerateNotes,
    RevokeShareLink,
    SetShareLink,
    TemplateCode,
)
from shosai.features.notes.domain.sharing import ShareExpiry
from shosai.features.notes.domain.templates import BUILTIN_BY_ID
from shosai.features.notes.infrastructure.meeting_records import MeetingRecord
from shosai.features.notes.infrastructure.run_records import RunRecord
from shosai.features.notes.infrastructure.share_records import (
    ShareCommentRecord,
    ShareLinkRecord,
)
from tests.features.notes.library_bench import MeetingSeed, Notes, seed_meeting
from tests.features.notes.write_bench import HOME, WriteBench

START = datetime.now(UTC).replace(day=1, hour=1, minute=0, second=0, microsecond=0)
NOTES = Notes(summary="We agreed the budget.", findings=[("decision", "Budget agreed.")])


async def owned(bench: WriteBench, owner: uuid.UUID, title: str = "Budget") -> uuid.UUID:
    """One of the owner's meetings with its notes written."""
    seed = MeetingSeed(owner, title=title, started_at=START, notes=NOTES)
    return (await seed_meeting(bench.homes, seed, HOME)).meeting_id


def planned(plan: PlannedEffect | ToolError) -> PlannedEffect:
    assert isinstance(plan, PlannedEffect), plan
    return plan


def test_the_writes_declare_their_gates_and_offer_every_shipped_template() -> None:
    assert {s.name: (s.reversibility, s.cost_class) for s in WRITE_TOOLS} == {
        "notes.move_to_folder": (Reversibility.REVERSIBLE, CostClass.FREE),
        "notes.regenerate_notes": (Reversibility.IRREVERSIBLE, CostClass.METERED),
        "notes.set_share_link": (Reversibility.COMPENSABLE, CostClass.FREE),
        "notes.revoke_share_link": (Reversibility.IRREVERSIBLE, CostClass.FREE),
    }
    assert {spec.provenance for spec in WRITE_TOOLS} == {None}
    assert {code.value for code in TemplateCode} == set(BUILTIN_BY_ID)


async def test_a_move_files_the_planned_meeting_by_its_folder_s_name_once_per_key(
    write_bench: WriteBench,
) -> None:
    owner = uuid.uuid4()
    meeting_id, other = await owned(write_bench, owner), await owned(write_bench, owner, "Other")
    folder = await write_bench.folder(owner, "Клиенты")
    await write_bench.folder(owner, "Twice")
    await write_bench.folder(owner, "twice ")
    writes, who, key = write_bench.notes, write_bench.context(owner), f"{uuid.uuid4()}:0"

    plan = planned(
        await writes.plan_move(MoveToFolder(meeting_id=meeting_id, folder="КЛИЕНТЫ"), who)
    )
    preview = await writes.preview_move(plan, who)
    first = await writes.execute_move(plan, who, key)
    again = await writes.execute_move(plan, who, key)
    missing = await writes.plan_move(MoveToFolder(meeting_id=meeting_id, folder="Nowhere"), who)
    ambiguous = await writes.plan_move(MoveToFolder(meeting_id=meeting_id, folder="TWICE"), who)
    stranger = await writes.plan_move(
        MoveToFolder(meeting_id=meeting_id, folder=None), write_bench.context(uuid.uuid4())
    )

    async with write_bench.homes.transactions.begin(TenancyScope(HOME, owner)) as session:
        rows = await session.execute(select(MeetingRecord.id, MeetingRecord.folder_id))
        filed = dict(rows.all())
    assert (preview.key, dict(preview.params)) == (
        "agent.notes.move_to_folder", {"title": "Budget", "folder": "Клиенты"},
    )  # fmt: skip
    assert first.output is not None
    assert first.output == again.output
    assert first.output.folder == "Клиенты"
    assert filed == {meeting_id: folder, other: None}
    assert await write_bench.audited(owner) == 1
    assert missing == ToolError(ToolErrorCode.NOT_FOUND)
    assert ambiguous == ToolError(ToolErrorCode.FAILED, {"reason": "folder_ambiguous"})
    assert stranger == ToolError(ToolErrorCode.NOT_FOUND)


async def test_a_rewrite_starts_one_run_by_the_planned_template_and_needs_written_notes(
    write_bench: WriteBench,
) -> None:
    owner = uuid.uuid4()
    meeting_id = await owned(write_bench, owner)
    bare = (
        await seed_meeting(write_bench.homes, MeetingSeed(owner, started_at=START), HOME)
    ).meeting_id
    writes, who, key = write_bench.notes, write_bench.context(owner), f"{uuid.uuid4()}:0"

    kept = planned(await writes.plan_regenerate(RegenerateNotes(meeting_id=meeting_id), who))
    chosen = planned(
        await writes.plan_regenerate(
            RegenerateNotes(meeting_id=meeting_id, template=TemplateCode.ONE_ON_ONE), who
        )
    )
    preview = await writes.preview_regenerate(chosen, who)
    first = await writes.execute_regenerate(chosen, who, key)
    again = await writes.execute_regenerate(chosen, who, key)
    not_ready = await writes.plan_regenerate(RegenerateNotes(meeting_id=bare), who)

    async with write_bench.homes.transactions.begin(TenancyScope(HOME, owner)) as session:
        runs = (
            await session.execute(
                select(RunRecord.source, RunRecord.layout).where(RunRecord.session_id == meeting_id)
            )
        ).all()
        template = await session.scalar(
            select(MeetingRecord.template_id).where(MeetingRecord.id == meeting_id)
        )
    assert dict(kept.data) == {"template_id": "enhanced"}
    assert preview.key == "agent.notes.regenerate_notes"
    assert dict(preview.params) == {"title": "Budget", "template": "oneOnOne", "shipped": True}
    assert first.output is not None
    assert first.output == again.output
    assert sorted(source for source, _ in runs) == ["live", "regenerate"]
    assert [layout["template_id"] for source, layout in runs if source == "regenerate"] == [
        "oneOnOne"
    ]
    assert template == "oneOnOne"
    assert {run for run, _ in write_bench.started.kicked} == {first.output.run_id}
    assert await write_bench.audited(owner) == 1
    assert not_ready == ToolError(ToolErrorCode.FAILED, {"reason": "notes_not_ready"})


async def test_a_link_goes_on_changes_and_goes_off_with_its_comments(
    write_bench: WriteBench,
) -> None:
    owner = uuid.uuid4()
    meeting_id = await owned(write_bench, owner)
    links, who = write_bench.links, write_bench.context(owner)
    arguments = SetShareLink(meeting_id=meeting_id, show_names=True, expiry=ShareExpiry.DAYS_7)

    on = planned(await links.plan_set(arguments, who))
    new_card = await links.preview_set(on, who)
    first = await links.execute_set(on, who, f"{uuid.uuid4()}:0")
    changed = planned(
        await links.plan_set(SetShareLink(meeting_id=meeting_id, allow_comments=True), who)
    )
    change_card = await links.preview_set(changed, who)
    second = await links.execute_set(changed, who, f"{uuid.uuid4()}:0")
    async with write_bench.homes.transactions.begin(TenancyScope(HOME, owner)) as session:
        session.add(
            ShareCommentRecord(id=uuid.uuid4(), session_id=meeting_id, user_id=owner, text="Ok")
        )
    off = planned(await links.plan_revoke(RevokeShareLink(meeting_id=meeting_id), who))
    off_card = await links.preview_revoke(off, who)
    revoked = await links.execute_revoke(off, who, f"{uuid.uuid4()}:0")
    again = await links.plan_revoke(RevokeShareLink(meeting_id=meeting_id), who)

    async with write_bench.homes.transactions.begin(TenancyScope(HOME, owner)) as session:
        left = await session.scalar(select(ShareLinkRecord.session_id))
        comments = await session.scalar(select(ShareCommentRecord.id))
    assert first.output is not None
    assert second.output is not None
    assert first.output.path == second.output.path
    assert first.output.path.startswith("/s/")
    assert first.output.expires_at is not None
    assert second.output.expires_at is None
    assert (new_card.params["new"], change_card.params["new"]) == (True, False)
    assert dict(off_card.params) == {"title": "Budget", "comments": 1}
    assert revoked.output is not None
    assert (left, comments) == (None, None)
    assert again == ToolError(ToolErrorCode.NOT_FOUND)
    assert await write_bench.audited(owner) == 3


async def test_a_meeting_gone_since_the_plan_and_one_not_kept_are_refused_without_effect(
    write_bench: WriteBench,
) -> None:
    owner = uuid.uuid4()
    meeting_id = await owned(write_bench, owner)
    folder = await write_bench.folder(owner, "Archive")
    unkept = await owned(write_bench, owner, "Private")
    writes, links, who = write_bench.notes, write_bench.links, write_bench.context(owner)
    plan = planned(
        await writes.plan_move(MoveToFolder(meeting_id=meeting_id, folder="Archive"), who)
    )
    async with write_bench.homes.transactions.begin(TenancyScope(HOME, owner)) as session:
        await session.execute(
            update(MeetingRecord).where(MeetingRecord.id == meeting_id).values(deleted_at=START)
        )
        await session.execute(
            update(MeetingRecord).where(MeetingRecord.id == unkept).values(kept=False)
        )

    late = await writes.execute_move(plan, who, f"{uuid.uuid4()}:0")
    private = await links.plan_set(SetShareLink(meeting_id=unkept), who)

    async with write_bench.homes.transactions.begin(TenancyScope(HOME, owner)) as session:
        filed = await session.scalar(
            select(MeetingRecord.folder_id).where(MeetingRecord.id == meeting_id)
        )
    assert late.error == ToolError(ToolErrorCode.NOT_FOUND)
    assert filed is None
    assert folder is not None
    assert private == ToolError(ToolErrorCode.FAILED, {"reason": "private_meeting"})
    assert await write_bench.audited(owner) == 0
