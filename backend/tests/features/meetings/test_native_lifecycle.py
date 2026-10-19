"""The native start and end, §10's end and runs, and billing's count of meetings (step 3)."""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa

from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.billing.infrastructure.minutes_records import UsageEventRecord
from shosai.features.meetings.infrastructure.meeting_records import MeetingRecord
from shosai.features.meetings.infrastructure.notes_records import SettingsRecord
from shosai.features.meetings.infrastructure.run_records import RunRecord
from tests.composition.native_clients import decode_session_start
from tests.features.meetings.meeting_bench import MeetingBench, bearer

# Поля `SessionResponse` черновика; клиенты читают из них `id`.
SESSION_FIELDS = {
    "id", "title", "started_at", "ended_at", "status", "client_device_id", "created_at",
    "updated_at",
}  # fmt: skip


def stamp(moment: datetime) -> str:
    """The time as WhispererKit writes it: seconds, no fraction, `Z`."""
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


async def started(bench: MeetingBench, person: uuid.UUID, device: str = "MacBook Pro") -> str:
    """A live meeting started as the desktop starts it; its id."""
    made = await bench.http.post(
        "/v1/sessions",
        json={"title": "Созвон с клиентом", "client_device_id": device},
        headers=bearer(Home.RU, person),
    )
    assert made.status_code == 201, made.text
    body = made.json()
    assert set(body) == SESSION_FIELDS
    assert body["status"] == "active"
    return str(uuid.UUID(decode_session_start(body)))


async def test_concurrent_ends_with_fresh_times_end_the_meeting_once_with_one_run(
    meeting_bench: MeetingBench,
) -> None:
    person = uuid.uuid4()
    meeting = await started(meeting_bench, person)
    began = (await meeting_bench.http.patch(
        f"/v1/sessions/{meeting}", json={}, headers=bearer(Home.RU, person)
    )).json()["started_at"]  # fmt: skip
    await meeting_bench.spoke(Home.RU, uuid.UUID(meeting), datetime.fromisoformat(began), 3)
    meeting_bench.clock.advance(timedelta(minutes=30))
    path = f"/v1/sessions/{meeting.upper()}"

    answers = await asyncio.gather(
        *(
            meeting_bench.http.patch(
                path,
                json={
                    "status": "completed",
                    "ended_at": stamp(meeting_bench.clock() + timedelta(seconds=n)),
                    "audio_lead_ms": 120,
                },
                headers=bearer(Home.RU, person),
            )
            for n in range(4)
        )
    )
    ended = await meeting_bench.http.post(
        f"/v1/me/sessions/{meeting}/end", headers=bearer(Home.RU, person)
    )
    run = await meeting_bench.http.get(
        f"/v1/me/runs/{ended.json()['run_id']}", headers=bearer(Home.RU, person)
    )
    async with meeting_bench.homes.transactions.begin(TenancyScope(Home.RU, person)) as session:
        runs = (await session.scalars(sa.select(RunRecord))).all()
        record = await session.get(MeetingRecord, uuid.UUID(meeting))

    assert {answer.status_code for answer in answers} == {200}
    assert len({answer.json()["ended_at"] for answer in answers}) == 1
    assert {answer.json()["status"] for answer in answers} == {"completed"}
    assert len(runs) == 1
    assert ended.status_code == 202
    assert ended.json()["run_id"] == str(runs[0].id)
    assert run.status_code == 200
    assert (run.json()["state"], [s["stage"] for s in run.json()["stages"]]) == (
        "pending",
        ["findings", "write_up"],
    )
    assert record is not None
    # Время клиента без долей секунды: победивший запрос мог отрезать меньше секунды.
    assert record.line_count == 3
    assert 30 * 60 - 1 <= record.seconds <= 30 * 60
    assert len(await meeting_bench.events(Home.RU, "meetings.meeting.ended")) == 1


async def test_a_meeting_is_someone_elses_or_titled_empty_and_nothing_changes(
    meeting_bench: MeetingBench,
) -> None:
    owner, stranger = uuid.uuid4(), uuid.uuid4()
    meeting = await started(meeting_bench, owner)

    foreign = await meeting_bench.http.patch(
        f"/v1/sessions/{meeting}", json={"status": "completed"}, headers=bearer(Home.RU, stranger)
    )
    unnamed = await meeting_bench.http.patch(
        f"/v1/sessions/{meeting}", json={"title": " "}, headers=bearer(Home.RU, owner)
    )
    paused = await meeting_bench.http.patch(
        f"/v1/sessions/{meeting}", json={"status": "paused", "title": "Новое"},
        headers=bearer(Home.RU, owner),
    )  # fmt: skip
    silent = await meeting_bench.http.post(
        f"/v1/me/sessions/{meeting}/end", headers=bearer(Home.RU, owner)
    )

    assert (foreign.status_code, foreign.json()["detail"]) == (404, "meeting_not_found")
    assert (unnamed.status_code, unnamed.json()["error"]["code"]) == (422, "title_empty")
    assert (paused.json()["status"], paused.json()["title"]) == ("active", "Новое")
    assert (silent.status_code, silent.json()) == (202, {"run_id": None})


async def test_a_new_meeting_on_the_same_device_ends_the_previous_one(
    meeting_bench: MeetingBench,
) -> None:
    person = uuid.uuid4()
    first = await started(meeting_bench, person, "Office-PC")
    meeting_bench.clock.advance(timedelta(minutes=5))
    second = await started(meeting_bench, person, "Office-PC")
    other_device = await started(meeting_bench, person, "Laptop")

    async with meeting_bench.homes.transactions.begin(TenancyScope(Home.RU, person)) as session:
        states = {
            str(row.id): row.status for row in (await session.scalars(sa.select(MeetingRecord)))
        }

    assert states == {first: "completed", second: "active", other_device: "active"}


async def test_a_meeting_not_kept_leaves_only_its_minutes(meeting_bench: MeetingBench) -> None:
    person = uuid.uuid4()
    async with meeting_bench.homes.transactions.begin(TenancyScope(Home.RU, person)) as session:
        session.add(SettingsRecord(user_id=person, keep_meetings=False))
    meeting = await started(meeting_bench, person)
    meeting_bench.clock.advance(timedelta(minutes=12))

    ended = await meeting_bench.http.patch(
        f"/v1/sessions/{meeting}", json={"status": "completed"}, headers=bearer(Home.RU, person)
    )
    async with meeting_bench.homes.transactions.begin(TenancyScope(Home.RU, person)) as session:
        left = await session.get(MeetingRecord, uuid.UUID(meeting))
        tombstones = (await session.scalars(sa.select(UsageEventRecord.seconds))).all()

    assert ended.json()["status"] == "completed"
    assert left is None
    assert tombstones == [12 * 60]


async def test_billing_counts_a_live_an_ended_and_a_hidden_meeting_exactly(
    meeting_bench: MeetingBench,
) -> None:
    person, now = uuid.uuid4(), meeting_bench.clock()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    rows = [
        MeetingRecord(
            id=uuid.uuid4(), user_id=person, title="Идёт", started_at=now - timedelta(minutes=10)
        ),
        MeetingRecord(
            id=uuid.uuid4(),
            user_id=person,
            title="Была",
            started_at=month_start,
            status="completed",
            ended_at=month_start + timedelta(minutes=20),
            seconds=1200,
        ),
        MeetingRecord(
            id=uuid.uuid4(),
            user_id=person,
            title="Удалена",
            started_at=month_start,
            status="completed",
            ended_at=month_start + timedelta(minutes=5),
            seconds=300,
            deleted_at=now,
        ),
        MeetingRecord(
            id=uuid.uuid4(),
            user_id=person,
            title="Раньше",
            started_at=month_start - timedelta(days=3),
            status="completed",
            ended_at=month_start - timedelta(days=3) + timedelta(minutes=1),
            seconds=60,
        ),
    ]
    async with meeting_bench.homes.transactions.begin(TenancyScope(Home.RU, person)) as session:
        session.add_all(rows)

    used = await meeting_bench.meter.used_seconds(Home.RU, person, now)

    assert used == 10 * 60 + 1200 + 300


async def test_the_month_s_minutes_refuse_a_new_meeting(meeting_bench: MeetingBench) -> None:
    person, now = uuid.uuid4(), meeting_bench.clock()
    async with meeting_bench.homes.transactions.begin(TenancyScope(Home.RU, person)) as session:
        session.add(
            MeetingRecord(
                id=uuid.uuid4(),
                user_id=person,
                title="Длинная",
                started_at=now - timedelta(hours=3),
                status="completed",
                ended_at=now - timedelta(hours=1),
                seconds=7200,
            )
        )

    refused = await meeting_bench.http.post(
        "/v1/sessions",
        json={"title": "Ещё одна", "client_device_id": "MacBook"},
        headers=bearer(Home.RU, person),
    )

    assert (refused.status_code, refused.json()["detail"]) == (402, "minutes_exhausted")
