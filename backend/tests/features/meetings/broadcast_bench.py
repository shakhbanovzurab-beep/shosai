"""Broadcasts' routes beside the rooms' bench: the host's, the link's and the stage's."""

import uuid
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass
from typing import Any

import httpx
import pytest_asyncio
from prometheus_client import CollectorRegistry
from redis.asyncio import Redis

from shosai.core.idempotency.ledger import EffectLedger
from shosai.core.idempotency.metrics import EffectKeyMetrics
from shosai.core.kv.metrics import KeyValueMetrics
from shosai.core.kv.rate_limits import RateLimiter
from shosai.core.ports.directory import PortDirectory
from shosai.features.billing.contracts import ENTITLEMENTS
from shosai.features.identity.contracts import ACCOUNT_PROFILE_READER, AUTHENTICATOR
from shosai.features.meetings.application.broadcast_chat import BroadcastChat
from shosai.features.meetings.application.broadcast_entry import BroadcastDoor
from shosai.features.meetings.application.broadcast_stage import BroadcastStage
from shosai.features.meetings.application.broadcasts import Broadcasts
from shosai.features.meetings.application.joining import JoinDesk
from shosai.features.meetings.application.passes import PassCheck
from shosai.features.meetings.channels.http.broadcasts import build_broadcasts_router
from shosai.features.meetings.channels.http.joining import build_joining_router
from shosai.features.meetings.channels.http.live import build_live_router, build_live_stage_router
from shosai.features.meetings.infrastructure.broadcast_queues import BroadcastQueues
from shosai.features.meetings.infrastructure.room_passes import RoomPasses
from tests.core.web.probe_app import build_probe_app, client_of
from tests.features.billing.people_bench import BearerOfTheTest
from tests.features.meetings.room_bench import NOW, ORIGIN, PLATFORM_CEILING, People, SfuDouble
from tests.harness.database_access import DatabaseAccess


@dataclass(frozen=True, slots=True)
class BroadcastBench:
    """The routes, the SFU double and the plan double."""

    http: httpx.AsyncClient
    sfu: SfuDouble
    people: People

    @staticmethod
    def bearer(person: uuid.UUID) -> Mapping[str, str]:
        """The person's authorization header."""
        return {"Authorization": f"Bearer person:{person}:ru"}

    async def create(self, host: uuid.UUID, *, waiting_room: bool = False) -> tuple[str, str]:
        """A new broadcast of the host: its id and its link's token."""
        self.people.named[host] = "Ведущая"
        headers = {**self.bearer(host), "Idempotency-Key": uuid.uuid4().hex}
        body = {"title": "Обзор релиза", "waiting_room": waiting_room}
        made = (await self.http.post("/v1/meetings/broadcasts", json=body, headers=headers)).json()
        return str(made["id"]), str(made["link"]).rsplit("/", 1)[1]

    async def join(self, token: str, who: uuid.UUID | str) -> dict[str, Any]:
        """The ticket the link gives a signed-in person or a named guest."""
        signed = isinstance(who, uuid.UUID)
        headers = self.bearer(who) if isinstance(who, uuid.UUID) else {}
        body = {} if signed else {"name": who}
        answer = await self.http.post(f"/v1/meetings/live/{token}/join", json=body, headers=headers)
        return dict(answer.json())

    async def call(
        self, method: str, token: str, path: str, room_pass: str, body: object = None
    ) -> httpx.Response:
        """A request to the link's routes with a room pass."""
        headers = {"X-Room-Pass": room_pass, "Idempotency-Key": uuid.uuid4().hex}
        url = f"/v1/meetings/live/{token}{path}"
        return await self.http.request(method, url, json=body, headers=headers)


@pytest_asyncio.fixture
async def broadcast_bench(homes: DatabaseAccess, valkey: Redis) -> AsyncIterator[BroadcastBench]:
    sfu, people, ports = SfuDouble(), People(named={}), PortDirectory()
    ports.install(
        [
            AUTHENTICATOR.bind(BearerOfTheTest()),
            ENTITLEMENTS.bind(people),
            ACCOUNT_PROFILE_READER.bind(people),
        ]
    )
    registry = CollectorRegistry()
    effects, limiter = (
        EffectLedger(EffectKeyMetrics(registry)),
        RateLimiter(valkey, KeyValueMetrics(registry)),
    )
    passes, queues = RoomPasses(valkey), BroadcastQueues(valkey)
    desk = JoinDesk(homes.transactions, (sfu, passes, ports), PLATFORM_CEILING, lambda: NOW)
    check = PassCheck(homes.transactions, passes)
    door = BroadcastDoor(homes.transactions, (desk, sfu, passes, queues), lambda: NOW)
    stage = BroadcastStage(homes.transactions, (sfu, queues))
    chat = BroadcastChat(homes.transactions, (effects, limiter, sfu), lambda: NOW)
    broadcasts = Broadcasts(homes.transactions, (effects, ports, sfu, desk), lambda: NOW)
    routers = (
        build_broadcasts_router(broadcasts, ports, ORIGIN),
        build_live_router((door, stage, chat), desk, check, (ports, limiter)),
        build_live_stage_router((door, stage), desk, check),
        build_joining_router(desk, check, ports, limiter),
    )
    async with client_of(build_probe_app(extra=routers).app) as http:
        yield BroadcastBench(http, sfu, people)
