"""The admin's LiveKit screen: what it reads, and ending rooms and removing people, each audited
in the EU log (meetings A8, MR-D10)."""

import uuid
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, cast

import httpx
import pytest_asyncio
from redis.asyncio import Redis
from sqlalchemy import select

from shosai.core.events.catalog import EventTypes
from shosai.core.events.outbox import EventOutbox
from shosai.core.events.records import OutboxMessage
from shosai.core.events.subscriptions import ReceivedEvent
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.core.tasks.sender import TaskSender
from shosai.features.identity.application.operator_journal import OperatorJournal
from shosai.features.identity.channels.subscriptions import audit_operator_action
from shosai.features.identity.contracts import (
    ADMIN_COOKIE,
    ADMIN_GATE,
    IDENTITY_EVENTS,
    OPERATOR_AUDIT,
    OperatorActed,
)
from shosai.features.meetings.application.admin_actions import AdminRoomActions
from shosai.features.meetings.application.admin_views import ServerFacts
from shosai.features.meetings.application.admin_watch import LiveKitWatch
from shosai.features.meetings.application.calls import Calls
from shosai.features.meetings.application.sfu_metrics import LoadNow, LoadSample, NodeLoad
from shosai.features.meetings.application.video_server import (
    EgressReport,
    SfuParticipant,
    SfuTrack,
    TrackKind,
)
from shosai.features.meetings.channels.http.admin_livekit import build_admin_livekit_router
from shosai.features.meetings.contracts.events import CallEnded, CallStarted, RecordingReady
from shosai.features.meetings.infrastructure.room_passes import RoomPasses
from shosai.features.meetings.infrastructure.room_records import RoomBanRecord, RoomRecord
from tests.core.web.probe_app import build_probe_app, client_of
from tests.features.billing.catalogue_bench import ADMIN_SESSION, BenchGate
from tests.features.meetings.room_bench import NOW, RoomsBench
from tests.features.meetings.test_removals import code_of, open_room
from tests.harness.connections import fetch_rows
from tests.harness.run_slot import RunSlot

MIB = 1024 * 1024
FACTS = ServerFacts("wss://rtc.shosai.tech", configured=True, memory_limit_mb=384)


@dataclass
class LoadDouble:
    """Prometheus as the test sets it: the load now and the day's samples."""

    load: LoadNow | None = None
    samples: list[LoadSample] = field(default_factory=list)

    async def now(self) -> LoadNow | None:
        """The test's load."""
        return self.load

    async def history(self, until: datetime) -> Sequence[LoadSample]:
        """The test's samples."""
        del until
        return self.samples


@dataclass(frozen=True, slots=True)
class AdminBench:
    """The admin's and an anonymous client over the rooms bench, and the load double."""

    admin: httpx.AsyncClient
    anonymous: httpx.AsyncClient
    rooms: RoomsBench
    load: LoadDouble
    run_slot: RunSlot

    async def audit(self, owner: uuid.UUID) -> list[tuple[str, uuid.UUID | None]]:
        """The owner's audit events, delivered to identity's EU log as its consumer does."""
        homes, scope = self.rooms.homes, TenancyScope(Home.RU, owner)
        async with homes.transactions.begin(scope, read_only=True) as session:
            found = list(
                await session.execute(
                    select(OutboxMessage.id, OutboxMessage.occurred_at, OutboxMessage.payload)
                    .where(OutboxMessage.event_type == OperatorActed.event_type)
                    .order_by(OutboxMessage.id)
                )
            )
        for event_id, occurred_at, payload in found:
            received = ReceivedEvent(
                OperatorActed.model_validate(payload), event_id, 1, occurred_at, scope
            )
            async with homes.transactions.begin(TenancyScope(Home.EU)) as session:
                await audit_operator_action(session, received)
        rows = await fetch_rows(
            self.run_slot.claimed.connections[Home.EU],
            "SELECT action, subject_id FROM operator_audit_events"
            " WHERE target_user_id = %s ORDER BY created_at",
            (owner,),
        )
        return [(row["action"], row["subject_id"]) for row in rows]


@pytest_asyncio.fixture
async def admin_bench(
    rooms_bench: RoomsBench, valkey: Redis, run_slot: RunSlot
) -> AsyncIterator[AdminBench]:
    transactions, load = rooms_bench.homes.transactions, LoadDouble()
    ports = PortDirectory()
    journal = OperatorJournal(EventOutbox(EventTypes(list(IDENTITY_EVENTS))))
    ports.install([ADMIN_GATE.bind(BenchGate()), OPERATOR_AUDIT.bind(journal)])
    outbox = EventOutbox(EventTypes([CallStarted, CallEnded, RecordingReady]))
    calls = Calls(transactions, (outbox, cast("TaskSender", None)), lambda: NOW)
    sfu, passes = rooms_bench.sfu, RoomPasses(valkey)
    router = build_admin_livekit_router(
        LiveKitWatch(sfu, load, FACTS, lambda: NOW),
        AdminRoomActions(transactions, (sfu, passes, ports), calls.find, lambda: NOW),
        ports,
    )
    app = build_probe_app(extra=(router,)).app
    async with client_of(app) as admin, client_of(app) as anonymous:
        admin.cookies.set(ADMIN_COOKIE, ADMIN_SESSION)
        yield AdminBench(admin, anonymous, rooms_bench, load, run_slot)


async def live_room(bench: AdminBench, owner: uuid.UUID) -> tuple[str, str, list[str]]:
    """A room of the owner with the owner and a guest in its call: id, LiveKit name, identities."""
    rooms = bench.rooms
    rooms.people.named[owner] = "Анна"
    room_id, token = await open_room(rooms, owner)
    join = f"/v1/meetings/join/{token}"
    mine = (await rooms.http.post(join, json={}, headers=rooms.bearer(owner))).json()
    guest = (await rooms.http.post(join, json={"name": "Гость"})).json()
    name = next(name for name in rooms.sfu.rooms_held if name not in rooms.sfu.deleted)
    rooms.sfu.seat(name, [mine["identity"], guest["identity"]])
    return room_id, name, [mine["identity"], guest["identity"]]


async def test_the_overview_reads_the_sfu_and_prometheus(admin_bench: AdminBench) -> None:
    _, name, _ = await live_room(admin_bench, uuid.uuid4())
    sfu = admin_bench.rooms.sfu
    sfu.egress_reports["EG_old"] = EgressReport(
        "EG_old", name, "EGRESS_COMPLETE", size_bytes=900, started_at=NOW - timedelta(hours=1)
    )
    sfu.egress_reports["EG_new"] = EgressReport("EG_new", name, "EGRESS_ACTIVE", started_at=NOW)
    admin_bench.load.load = LoadNow(
        started_at=NOW - timedelta(days=2), published_tracks=3, bandwidth_in_mbps=1.5,
        bandwidth_out_mbps=4.0,
        nodes=(NodeLoad("ND_a", up=True, rooms=1, participants=2, cpu_percent=12.5,
                        memory_bytes=192 * MIB), NodeLoad("livekit-2:6789", up=False)),
    )  # fmt: skip
    admin_bench.load.samples = [LoadSample(NOW, 2, 1.5, 4.0)]

    answer = await admin_bench.admin.get("/v1/admin/livekit/overview")
    anonymous = await admin_bench.anonymous.get("/v1/admin/livekit/overview")

    body = answer.json()
    assert (body["server"]["health"], body["server"]["url"]) == (
        "degraded",
        "wss://rtc.shosai.tech",
    )
    assert body["stats"] == {
        "active_rooms": 1, "participants": 2, "published_tracks": 3, "bandwidth_in_mbps": 1.5,
        "bandwidth_out_mbps": 4.0, "active_egress": 1,
    }  # fmt: skip
    assert [(n["id"], n["memory_percent"], n["state"]) for n in body["nodes"]] == [
        ("ND_a", 50.0, "serving"), ("livekit-2:6789", None, "down"),
    ]  # fmt: skip
    assert [(r["name"], r["num_participants"]) for r in body["rooms"]] == [(name, 2)]
    assert "title" not in body["rooms"][0]
    assert [(e["id"], e["status"], e["file_size_bytes"]) for e in body["egress"]] == [
        ("EG_new", "active", None), ("EG_old", "complete", 900),
    ]  # fmt: skip
    assert len(body["history"]) == 1
    assert (anonymous.status_code, code_of(anonymous)) == (401, "admin_sign_in_required")


async def test_without_prometheus_there_is_no_data_and_without_livekit_the_server_is_down(
    admin_bench: AdminBench,
) -> None:
    await live_room(admin_bench, uuid.uuid4())

    no_metrics = (await admin_bench.admin.get("/v1/admin/livekit/overview")).json()
    admin_bench.rooms.sfu.up = False
    no_server = await admin_bench.admin.get("/v1/admin/livekit/overview")

    assert no_metrics["server"]["health"] == "healthy"
    assert (no_metrics["nodes"], no_metrics["history"]) == ([], [])
    stats: dict[str, Any] = no_metrics["stats"]
    assert (stats["published_tracks"], stats["bandwidth_in_mbps"]) == (None, None)
    assert no_server.status_code == 200
    assert (no_server.json()["server"]["health"], no_server.json()["rooms"]) == ("down", [])


async def test_a_room_shows_its_sessions_devices_and_codecs(admin_bench: AdminBench) -> None:
    _, name, identities = await live_room(admin_bench, uuid.uuid4())
    admin_bench.rooms.sfu.sessions[name] = [
        SfuParticipant(
            identity=identities[1], name="Гость", joined_at=NOW,
            attributes={"device.os": "macos", "device.client": "web", "device.browser": "Chrome"},
            tracks=(SfuTrack("TR_v", TrackKind.VIDEO, muted=False, mime_type="video/VP8"),
                    SfuTrack("TR_a", TrackKind.AUDIO, muted=True, mime_type="audio/opus")),
        )
    ]  # fmt: skip

    room = (await admin_bench.admin.get(f"/v1/admin/livekit/rooms/{name}")).json()
    missing = await admin_bench.admin.get("/v1/admin/livekit/rooms/r-0000000000000000")

    assert (room["video_codec"], room["audio_codec"]) == ("VP8", "Opus")
    guest = room["participants"][0]
    assert guest["device"] == {
        "os": "macos", "os_version": None, "client": "web", "client_version": None,
        "browser": "Chrome",
    }  # fmt: skip
    assert [(t["kind"], t["muted"]) for t in guest["tracks"]] == [("video", False), ("audio", True)]
    assert (missing.status_code, code_of(missing)) == (404, "room_not_found")


async def test_ending_a_room_closes_it_by_the_admin_ends_it_in_the_sfu_and_is_audited(
    admin_bench: AdminBench,
) -> None:
    owner = uuid.uuid4()
    room_id, name, _ = await live_room(admin_bench, owner)

    ended = await admin_bench.admin.delete(f"/v1/admin/livekit/rooms/{name}")
    unknown = await admin_bench.admin.delete("/v1/admin/livekit/rooms/r-0000000000000000")

    homes = admin_bench.rooms.homes
    async with homes.transactions.begin(TenancyScope(Home.RU, owner), read_only=True) as session:
        row = await session.get_one(RoomRecord, uuid.UUID(room_id))
    assert ended.status_code == 204
    assert (row.state, row.closed_by) == ("closed", "admin")
    assert name in admin_bench.rooms.sfu.deleted
    assert (unknown.status_code, code_of(unknown)) == (404, "room_not_found")
    assert await admin_bench.audit(owner) == [("room_closed", uuid.UUID(room_id))]


async def test_removing_bans_by_the_admin_disconnects_and_is_audited(
    admin_bench: AdminBench,
) -> None:
    owner = uuid.uuid4()
    room_id, name, (mine, guest) = await live_room(admin_bench, owner)
    base = f"/v1/admin/livekit/rooms/{name}/participants"

    removed = await admin_bench.admin.delete(f"{base}/{guest}")
    owner_removal = await admin_bench.admin.delete(f"{base}/{mine}")
    egress = await admin_bench.admin.delete(f"{base}/EG_recorder")

    homes = admin_bench.rooms.homes
    async with homes.transactions.begin(TenancyScope(Home.RU, owner), read_only=True) as session:
        bans = (await session.scalars(select(RoomBanRecord.banned_by))).all()
    assert removed.status_code == 204
    assert [item.identity for item in admin_bench.rooms.sfu.sessions[name]] == [mine]
    assert bans == ["admin"]
    assert (owner_removal.status_code, code_of(owner_removal)) == (409, "cannot_remove_owner")
    assert (egress.status_code, code_of(egress)) == (404, "participant_not_found")
    assert await admin_bench.audit(owner) == [("room_participant_removed", uuid.UUID(room_id))]
