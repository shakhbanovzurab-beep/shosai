"""Calls from LiveKit's webhooks and the sweep of a home (meetings A5, §3.6)."""

import json
import uuid
from collections.abc import AsyncIterator, Collection
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, cast

import pytest
from prometheus_client import CollectorRegistry
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.config.roles import ProcessRole
from shosai.core.events.catalog import EventTypes
from shosai.core.events.outbox import EventOutbox
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.core.tasks.declaration import TaskDeclaration
from shosai.core.tasks.sender import TaskSender
from shosai.features.meetings.application.calls import Calls
from shosai.features.meetings.application.handover import CallTask
from shosai.features.meetings.application.recording import RecordingLimits, Recordings
from shosai.features.meetings.application.sweep import Sweep
from shosai.features.meetings.application.video_server import RoomSpec, SfuWebhook, WebhookKind
from shosai.features.meetings.channels.http.webhook import build_webhook_router
from shosai.features.meetings.contracts import PENDING_EVENTS
from shosai.features.meetings.contracts.events import CallEnded, CallStarted, RecordingReady
from shosai.features.meetings.infrastructure.call_records import RoomChatMessageRecord
from shosai.features.meetings.infrastructure.meetings_metrics import MeetingsMetrics
from shosai.features.meetings.infrastructure.room_records import RoomCallRecord, RoomRecord
from tests.core.web.probe_app import build_probe_app, client_of
from tests.features.meetings.room_bench import NOW, SfuDouble
from tests.features.meetings.room_kit import add_room, room_row
from tests.features.meetings.test_livekit_adapter import server as adapter_server
from tests.features.meetings.test_livekit_adapter import signed
from tests.harness.connections import fetch_rows
from tests.harness.database_access import (
    DatabaseAccess,
    ProcessShape,
    open_database_access,
    slot_urls,
)
from tests.harness.run_slot import RunSlot

SID = "RM_live000001"


@dataclass
class SentTasks:
    """The handovers the calls queued."""

    sent: list[CallTask] = field(default_factory=list)

    async def send(self, task: TaskDeclaration[Any], payload: CallTask) -> str:
        """Keep the payload."""
        del task
        self.sent.append(payload)
        return str(uuid.uuid4())


@dataclass
class Calendar:
    """Rooms whose event is still to come."""

    rooms: set[uuid.UUID] = field(default_factory=set)

    async def pending(
        self, session: AsyncSession, room_ids: Collection[uuid.UUID], now: datetime
    ) -> frozenset[uuid.UUID]:
        """The pending ones among the rooms."""
        del session, now
        return frozenset(self.rooms & set(room_ids))


def webhook(
    kind: WebhookKind, room: RoomRecord, minute: int, participants: int | None = None
) -> SfuWebhook:
    """A verified webhook of the room's SFU instance at a minute past noon."""
    return SfuWebhook(
        id=f"EV_{uuid.uuid4().hex[:8]}", kind=kind, created_at=NOW + timedelta(minutes=minute),
        room_name=room.lk_room_name, room_sid=SID, ceiling=4, participants=participants,
    )  # fmt: skip


@pytest.fixture
async def workers(run_slot: RunSlot) -> AsyncIterator[DatabaseAccess]:
    async with open_database_access(
        slot_urls(run_slot), ProcessShape(ProcessRole.WORKERS)
    ) as access:
        await access.gate.verify_at_start()
        yield access


LIMITS = RecordingLimits(concurrent=1, length=timedelta(minutes=30), buckets={}, endpoints={})


def outbox_of() -> EventOutbox:
    """An outbox that knows meetings' events."""
    return EventOutbox(EventTypes([CallStarted, CallEnded, RecordingReady]))


def calls_of(access: DatabaseAccess, sent: SentTasks) -> Calls:
    """The calls service writing its events and handovers."""
    return Calls(access.transactions, (outbox_of(), cast("TaskSender", sent)), lambda: NOW)


async def events(run_slot: RunSlot, room: RoomRecord) -> list[str]:
    """The room's call events in the outbox, oldest first."""
    rows = await fetch_rows(
        run_slot.claimed.connections[Home.RU],
        "SELECT event_type, payload->>'room_id' AS room_id FROM outbox_messages "
        "WHERE event_type LIKE 'meetings.%' ORDER BY occurred_at",
    )
    return [str(row["event_type"]) for row in rows if row["room_id"] == str(room.id)]


async def the_call(access: DatabaseAccess, owner: uuid.UUID) -> RoomCallRecord:
    """The owner's only call."""
    async with access.transactions.begin(TenancyScope(Home.RU, owner), read_only=True) as session:
        found = (await session.scalars(select(RoomCallRecord))).all()
    assert len(found) == 1
    return found[0]


async def test_webhooks_in_any_order_and_repeated_make_one_call_and_each_event_once(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    owner = uuid.uuid4()
    room = await add_room(homes, room_row(owner), with_kept=False)
    sent = SentTasks()
    calls = calls_of(homes, sent)
    finish = webhook(WebhookKind.ROOM_FINISHED, room, 45, participants=0)

    assert await calls.on_webhook(finish)
    assert await calls.on_webhook(webhook(WebhookKind.PARTICIPANT_JOINED, room, 5, participants=3))
    assert await calls.on_webhook(webhook(WebhookKind.ROOM_STARTED, room, 0, participants=0))
    assert await calls.on_webhook(finish)
    assert not await calls.on_webhook(
        SfuWebhook("EV_x", WebhookKind.ROOM_STARTED, NOW, "r-00000000deadbeef", "RM_other")
    )

    call = await the_call(homes, owner)
    assert (call.state, call.started_at, call.emptied_at) == (
        "ending",
        NOW,
        NOW + timedelta(minutes=45),
    )
    assert (call.peak_participants, call.ceiling) == (3, 4)
    assert await events(run_slot, room) == ["meetings.call.started", "meetings.call.ended"]
    assert [task.call_id for task in sent.sent] == [call.id]

    await calls.ended(sent.sent[0])
    await calls.ended(sent.sent[0])
    ended = await the_call(homes, owner)
    assert (ended.state, ended.ended_at) == ("ended", NOW)


async def sweep_of(workers: DatabaseAccess, sfu: SfuDouble, calendar: Calendar) -> Sweep:
    """The sweep with the SFU double and the calendar's pending events."""
    ports = PortDirectory()
    ports.install([PENDING_EVENTS.bind(calendar)])
    calls = calls_of(workers, SentTasks())
    recordings = Recordings(workers.transactions, (sfu, ports, outbox_of()), LIMITS, lambda: NOW)
    metrics = MeetingsMetrics(CollectorRegistry())
    return Sweep(workers.transactions, (sfu, calls, ports, metrics, recordings), lambda: NOW)


async def test_the_sweep_closes_idle_rooms_finishes_lost_calls_and_ends_closed_rooms_in_the_sfu(
    homes: DatabaseAccess, workers: DatabaseAccess
) -> None:
    owner = uuid.uuid4()
    hour_ago = NOW - timedelta(minutes=61)
    idle = await add_room(homes, room_row(owner, None, created_at=hour_ago), with_kept=False)
    planned = await add_room(homes, room_row(owner, None, created_at=hour_ago), with_kept=False)
    in_use = await add_room(homes, room_row(owner, None, created_at=hour_ago), with_kept=False)
    lost = await add_room(homes, room_row(owner, None, created_at=hour_ago))
    ended = await add_room(
        homes,
        room_row(owner, None, state="closed", closed_at=NOW, closed_by="owner"),
        with_kept=False,
    )
    sfu, calendar = SfuDouble(), Calendar({planned.id})
    for name in (in_use.lk_room_name, ended.lk_room_name):
        await sfu.create_room(RoomSpec(name, 4, "{}"))
    sweep = await sweep_of(workers, sfu, calendar)

    sfu.up = False
    await sweep.run(Home.RU)
    async with homes.transactions.begin(TenancyScope(Home.RU, owner), read_only=True) as session:
        still_open = await session.scalar(
            select(func.count()).select_from(RoomRecord).where(RoomRecord.state == "open")
        )
    assert still_open == 4

    sfu.up = True
    await sweep.run(Home.RU)
    async with homes.transactions.begin(TenancyScope(Home.RU, owner), read_only=True) as session:
        states = dict((await session.execute(select(RoomRecord.id, RoomRecord.closed_by))).all())
        call_state = await session.scalar(
            select(RoomCallRecord.state).where(RoomCallRecord.room_id == lost.id)
        )
    assert states[idle.id] == "idle"
    assert states[planned.id] is None
    assert states[in_use.id] is None
    assert call_state == "ending"
    assert ended.lk_room_name in sfu.deleted
    assert in_use.lk_room_name not in sfu.deleted

    async with homes.transactions.begin(TenancyScope(Home.RU, owner)) as session:
        await session.execute(update(RoomCallRecord).values(emptied_at=hour_ago))
    await sweep.run(Home.RU)
    async with homes.transactions.begin(TenancyScope(Home.RU, owner), read_only=True) as session:
        lost_state = await session.scalar(
            select(RoomRecord.closed_by).where(RoomRecord.id == lost.id)
        )
    assert lost_state == "idle"


async def test_the_webhook_route_folds_a_signed_body_and_refuses_a_forged_one(
    homes: DatabaseAccess,
) -> None:
    owner = uuid.uuid4()
    room = await add_room(homes, room_row(owner), with_kept=False)
    server = adapter_server()
    metrics = MeetingsMetrics(CollectorRegistry())
    recordings = Recordings(homes.transactions, (server, PortDirectory(), outbox_of()), LIMITS)
    router = build_webhook_router(server, (calls_of(homes, SentTasks()), recordings), metrics)
    body = json.dumps(
        {
            "event": "room_started",
            "id": "EV_1",
            "createdAt": str(int(NOW.timestamp())),
            "room": {"name": room.lk_room_name, "sid": SID, "maxParticipants": 4},
        }
    ).encode()
    async with client_of(build_probe_app(extra=(router,)).app) as http:
        forged = await http.post(
            "/v1/livekit/webhook", content=body, headers={"Authorization": signed(b"{}")}
        )
        accepted = await http.post(
            "/v1/livekit/webhook", content=body, headers={"Authorization": signed(body)}
        )

    assert (forged.status_code, forged.json()["error"]["code"]) == (401, "webhook_rejected")
    assert (accepted.status_code, accepted.json()) == (200, {"ok": True})
    assert (await the_call(homes, owner)).lk_room_sid == SID


async def test_a_calls_chat_goes_with_its_handover(homes: DatabaseAccess) -> None:
    owner = uuid.uuid4()
    room = await add_room(homes, room_row(owner))
    call = await the_call(homes, owner)
    async with homes.transactions.begin(TenancyScope(Home.RU, owner)) as session:
        await session.execute(update(RoomCallRecord).values(state="ending", emptied_at=NOW))

    await calls_of(homes, SentTasks()).ended(CallTask(home=Home.RU, user_id=owner, call_id=call.id))

    async with homes.transactions.begin(TenancyScope(Home.RU, owner), read_only=True) as session:
        kept = await session.scalar(select(func.count()).select_from(RoomChatMessageRecord))
    assert kept == 0
    assert room.id == call.room_id
