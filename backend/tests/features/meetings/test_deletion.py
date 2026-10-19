"""A meeting's deletion (MT-D8, step 8): hidden at once, restorable, purged after 7 days."""

import uuid
from datetime import UTC, datetime, timedelta
from http import HTTPStatus

from sqlalchemy import select, update

from shosai.core.events.records import OutboxMessage
from shosai.core.events.subscriptions import ReceivedEvent
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.pagination.page import PageRequest
from shosai.features.identity.contracts import AccountDeletionCancelled, AccountDeletionScheduled
from shosai.features.meetings.application.minutes import MeetingMinutesCount
from shosai.features.meetings.channels.subscriptions import hide_with_account, show_with_account
from shosai.features.meetings.infrastructure.meeting_records import MeetingRecord
from shosai.features.meetings.infrastructure.run_records import RunRecord
from shosai.features.meetings.infrastructure.share_records import (
    ShareCommentRecord,
    ShareLinkRecord,
)
from tests.features.meetings.deletion_bench import ADMIN, DeletionBench
from tests.features.meetings.library_bench import MeetingSeed, Seeded, bearer, seed_meeting
from tests.harness.connections import fetch_value

PAGE = PageRequest(limit=50)


async def shared(bench: DeletionBench, owner: uuid.UUID) -> Seeded:
    """A spoken meeting with a share link and a comment on it."""
    meeting = await seed_meeting(
        bench.homes, MeetingSeed(owner, lines=[(0, 0, "Начнём."), (1, 4, "Да.")])
    )
    async with bench.homes.transactions.begin(TenancyScope(Home.EU, owner)) as session:
        session.add(
            ShareLinkRecord(session_id=meeting.meeting_id, user_id=owner, token=uuid.uuid4().hex)
        )
        await session.flush()
        session.add(
            ShareCommentRecord(
                id=uuid.uuid4(), session_id=meeting.meeting_id, user_id=owner, text="Ок"
            )
        )
    return meeting


async def events(bench: DeletionBench, owner: uuid.UUID, kind: str) -> int:
    async with bench.homes.transactions.begin(
        TenancyScope(Home.EU, owner), read_only=True
    ) as session:
        rows = await session.scalars(
            select(OutboxMessage.id).where(OutboxMessage.event_type == kind)
        )
        return len(rows.all())


async def test_a_deleted_meeting_leaves_every_read_and_its_link_at_once_and_still_counts(
    deletion_bench: DeletionBench,
) -> None:
    owner, stranger = uuid.uuid4(), uuid.uuid4()
    meeting = await shared(deletion_bench, owner)
    live = await seed_meeting(deletion_bench.homes, MeetingSeed(owner, title="Идёт"))
    async with deletion_bench.homes.transactions.begin(TenancyScope(Home.EU, owner)) as session:
        await session.execute(
            update(MeetingRecord)
            .where(MeetingRecord.id == live.meeting_id)
            .values(status="active", ended_at=None)
        )
    path, http = f"/v1/meetings/{meeting.meeting_id}", deletion_bench.http

    foreign = await http.delete(path, headers=bearer(stranger))
    active = await http.delete(f"/v1/meetings/{live.meeting_id}", headers=bearer(owner))
    deleted = await http.delete(path, headers=bearer(owner))
    after = await http.get(path, headers=bearer(owner))
    again = await http.delete(path, headers=bearer(owner))
    async with deletion_bench.homes.transactions.begin(
        TenancyScope(Home.EU, owner), read_only=True
    ) as session:
        link = await session.get(ShareLinkRecord, meeting.meeting_id)
        window = (datetime.now(UTC) - timedelta(days=1), datetime.now(UTC) + timedelta(days=1))
        counted = await MeetingMinutesCount().recorded_seconds(session, owner, window)

    assert (foreign.status_code, foreign.json()["error"]["code"]) == (404, "meeting_not_found")
    assert (active.status_code, active.json()["error"]["code"]) == (409, "meeting_active")
    assert deleted.status_code == HTTPStatus.NO_CONTENT
    assert after.status_code == HTTPStatus.NOT_FOUND
    assert again.status_code == HTTPStatus.NOT_FOUND
    assert link is None
    assert counted >= 1800
    assert await events(deletion_bench, owner, "meetings.meeting.deleted") == 1


async def test_support_restores_within_seven_days_unshared_and_every_action_is_audited(
    deletion_bench: DeletionBench,
) -> None:
    owner = uuid.uuid4()
    meeting = await shared(deletion_bench, owner)
    await deletion_bench.http.delete(f"/v1/meetings/{meeting.meeting_id}", headers=bearer(owner))
    admin = deletion_bench.http
    base = f"/v1/admin/users/{owner}/meetings"

    unsigned = await admin.get(base, params={"home": "eu"})
    listed = await admin.get(base, params={"home": "eu"}, headers=ADMIN)
    restored = await admin.post(
        f"{base}/{meeting.meeting_id}/restore", json={"home": "eu"}, headers=ADMIN
    )
    twice = await admin.post(
        f"{base}/{meeting.meeting_id}/restore", json={"home": "eu"}, headers=ADMIN
    )
    back = await admin.get(f"/v1/meetings/{meeting.meeting_id}", headers=bearer(owner))
    async with deletion_bench.homes.transactions.begin(
        TenancyScope(Home.EU, owner), read_only=True
    ) as session:
        link = await session.get(ShareLinkRecord, meeting.meeting_id)

    assert unsigned.status_code == HTTPStatus.UNAUTHORIZED
    assert [item["id"] for item in listed.json()["items"]] == [str(meeting.meeting_id)]
    assert restored.status_code == HTTPStatus.NO_CONTENT
    assert (twice.status_code, twice.json()["error"]["code"]) == (404, "hidden_meeting_not_found")
    assert back.status_code == HTTPStatus.OK
    assert link is None
    assert await events(deletion_bench, owner, "meetings.meeting.restored") == 1
    assert await deletion_bench.audit(Home.EU, owner) == [
        ("meetings_listed", None), ("meeting_restored", meeting.meeting_id),
    ]  # fmt: skip


async def test_support_neither_lists_nor_restores_an_account_in_its_deletion_window(
    deletion_bench: DeletionBench,
) -> None:
    owner = uuid.uuid4()
    meeting = await shared(deletion_bench, owner)
    await deletion_bench.http.delete(f"/v1/meetings/{meeting.meeting_id}", headers=bearer(owner))
    start, scope = datetime.now(UTC), TenancyScope(Home.EU, owner)
    scheduled = AccountDeletionScheduled(user_id=owner, erase_at=start + timedelta(days=7))
    cancelled = AccountDeletionCancelled(user_id=owner)

    async def hide(at: datetime) -> None:
        async with deletion_bench.homes.transactions.begin(scope) as session:
            await hide_with_account(session, ReceivedEvent(scheduled, uuid.uuid4(), 1, at, scope))

    async def show(at: datetime) -> None:
        async with deletion_bench.homes.transactions.begin(scope) as session:
            await show_with_account(session, ReceivedEvent(cancelled, uuid.uuid4(), 1, at, scope))

    await hide(start)
    hidden_list = await deletion_bench.http.get(
        f"/v1/admin/users/{owner}/meetings", params={"home": "eu"}, headers=ADMIN
    )
    hidden_restore = await deletion_bench.http.post(
        f"/v1/admin/users/{owner}/meetings/{meeting.meeting_id}/restore",
        json={"home": "eu"},
        headers=ADMIN,
    )
    await show(start + timedelta(minutes=2))
    await hide(start + timedelta(minutes=1))
    open_again = await deletion_bench.support.of_person(Home.EU, owner, PAGE)

    assert (hidden_list.status_code, hidden_list.json()["error"]["code"]) == (
        409, "account_deletion_scheduled",
    )  # fmt: skip
    assert hidden_restore.json()["error"]["code"] == "account_deletion_scheduled"
    assert [m.meeting_id for m in open_again.items] == [meeting.meeting_id]
    assert await deletion_bench.audit(Home.EU, owner) == [("meetings_listed", None)]


async def test_after_seven_days_the_purge_takes_rows_and_objects_and_keeps_minutes_once(
    deletion_bench: DeletionBench,
) -> None:
    owner = uuid.uuid4()
    old = await shared(deletion_bench, owner)
    recent = await shared(deletion_bench, owner)
    key = f"transient/recording/{uuid.uuid4()}"
    await deletion_bench.storage[Home.EU].put(key, b"audio", content_type="audio/mp4")
    now = deletion_bench.clock()
    async with deletion_bench.homes.transactions.begin(TenancyScope(Home.EU, owner)) as session:
        await session.execute(
            update(RunRecord).where(RunRecord.id == old.run_id).values(audio_key=key)
        )
        for seeded, ago in ((old, timedelta(days=8)), (recent, timedelta(days=6))):
            await session.execute(
                update(MeetingRecord)
                .where(MeetingRecord.id == seeded.meeting_id)
                .values(deleted_at=now - ago)
            )

    async with deletion_bench.purge() as purge:
        first = await purge.purge(Home.EU)
        second = await purge.purge(Home.EU)
    connection = deletion_bench.run_slot.claimed.connections[Home.EU]
    left = await fetch_value(
        connection, "SELECT count(*) FROM sessions WHERE user_id = %s", (owner,)
    )
    lines = await fetch_value(
        connection,
        "SELECT count(*) FROM transcript_segments WHERE session_id = %s",
        (old.meeting_id,),
    )
    tombstones = await fetch_value(
        connection, "SELECT count(*) FROM usage_events WHERE meeting_id = %s", (old.meeting_id,)
    )

    assert (first, second) == (1, 0)
    assert (left, lines, tombstones) == (1, 0, 1)
    assert await deletion_bench.storage[Home.EU].head(key) is None


async def test_the_native_rename_and_deletion_keep_the_draft_s_shapes(
    deletion_bench: DeletionBench,
) -> None:
    owner = uuid.uuid4()
    meeting = await seed_meeting(deletion_bench.homes, MeetingSeed(owner))
    path, headers = f"/v1/me/sessions/{meeting.meeting_id}", bearer(owner)

    renamed = await deletion_bench.http.patch(path, json={"title": "  Итоги  "}, headers=headers)
    blank = await deletion_bench.http.patch(path, json={"title": " "}, headers=headers)
    deleted = await deletion_bench.http.delete(path, headers=headers)
    gone = await deletion_bench.http.patch(path, json={"title": "Снова"}, headers=headers)

    assert renamed.json() == {"id": str(meeting.meeting_id), "title": "Итоги"}
    assert (blank.status_code, blank.json()["detail"]) == (422, "title_empty")
    assert deleted.status_code == HTTPStatus.NO_CONTENT
    assert gone.status_code == HTTPStatus.NOT_FOUND
