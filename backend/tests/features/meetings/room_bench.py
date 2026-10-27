"""Meetings' routes over the slot's homes, with an SFU double and the doubles of the ports."""

import uuid
from collections.abc import AsyncIterator, Collection, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import httpx
import pytest_asyncio
from prometheus_client import CollectorRegistry

from shosai.core.idempotency.ledger import EffectLedger
from shosai.core.idempotency.metrics import EffectKeyMetrics
from shosai.core.kernel.homes import Home
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import AUTHENTICATOR
from shosai.features.meetings.application.rooms import RoomBook
from shosai.features.meetings.application.video_server import (
    PassRequest,
    RoomSpec,
    SessionPass,
    SfuParticipant,
    SfuRoom,
    SfuWebhook,
    VideoUnavailableError,
    WebhookRejectedError,
)
from shosai.features.meetings.channels.http.rooms import build_rooms_router
from shosai.features.workspaces.contracts import MEMBERSHIP_READER
from tests.core.web.probe_app import build_probe_app, client_of
from tests.features.billing.people_bench import BearerOfTheTest
from tests.features.memory.facts_api_bench import Spaces
from tests.harness.database_access import DatabaseAccess

ORIGIN = "https://shosai.tech"
NOW = datetime(2026, 10, 27, 12, tzinfo=UTC)


@dataclass
class SfuDouble:
    """The SFU as the test sets it: its rooms, their sessions and whether it answers."""

    rooms_held: dict[str, SfuRoom] = field(default_factory=dict)
    sessions: dict[str, list[SfuParticipant]] = field(default_factory=dict)
    deleted: list[str] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)
    up: bool = True

    def _answering(self) -> None:
        if not self.up:
            raise VideoUnavailableError

    async def create_room(self, spec: RoomSpec) -> SfuRoom:
        """The room, made once."""
        self._answering()
        room = self.rooms_held.setdefault(
            spec.name, SfuRoom(spec.name, f"RM_{uuid.uuid4().hex[:12]}", 0, spec.metadata, NOW)
        )
        self.metadata[spec.name] = spec.metadata
        return room

    async def rooms(self, names: Collection[str] = ()) -> Sequence[SfuRoom]:
        """The rooms held, named ones only when asked."""
        self._answering()
        return [room for name, room in self.rooms_held.items() if not names or name in names]

    async def delete_room(self, name: str) -> None:
        """End the room."""
        self._answering()
        self.deleted.append(name)
        self.rooms_held.pop(name, None)
        self.sessions.pop(name, None)

    async def participants(self, room_name: str) -> Sequence[SfuParticipant]:
        """The room's sessions."""
        self._answering()
        return list(self.sessions.get(room_name, []))

    async def set_metadata(self, room_name: str, metadata: str) -> bool:
        """Replace the metadata of a held room."""
        self._answering()
        if room_name not in self.rooms_held:
            return False
        self.metadata[room_name] = metadata
        return True

    def session_pass(self, request: PassRequest, now: datetime) -> SessionPass:
        """A readable pass: the room and the identity."""
        self._answering()
        token = f"{request.room_name}|{request.identity}"
        return SessionPass(
            token=token, url="wss://rtc.example", expires_at=now + timedelta(minutes=10)
        )

    def verify_webhook(self, body: bytes, authorization: str | None) -> SfuWebhook:
        """No webhook in these tests."""
        del body, authorization
        raise WebhookRejectedError

    async def ping(self) -> None:
        """Answer when up."""
        self._answering()

    def seat(self, room_name: str, identities: Sequence[str]) -> None:
        """Put sessions in a held room."""
        self.sessions[room_name] = [
            SfuParticipant(identity=identity, name="Гость", joined_at=NOW, attributes={})
            for identity in identities
        ]
        held = self.rooms_held[room_name]
        self.rooms_held[room_name] = SfuRoom(
            held.name, held.sid, len(identities), held.metadata, NOW
        )


@dataclass(frozen=True, slots=True)
class RoomsBench:
    """The routes, the doubles behind them and the slot's homes."""

    http: httpx.AsyncClient
    homes: DatabaseAccess
    sfu: SfuDouble
    spaces: Spaces

    def bearer(self, person: uuid.UUID, home: Home = Home.RU) -> Mapping[str, str]:
        """The person's authorization header."""
        return {"Authorization": f"Bearer person:{person}:{home.value}"}


@pytest_asyncio.fixture
async def rooms_bench(homes: DatabaseAccess) -> AsyncIterator[RoomsBench]:
    sfu, spaces = SfuDouble(), Spaces()
    ports = PortDirectory()
    ports.install([AUTHENTICATOR.bind(BearerOfTheTest()), MEMBERSHIP_READER.bind(spaces)])
    effects = EffectLedger(EffectKeyMetrics(CollectorRegistry()))
    book = RoomBook(homes.transactions, (effects, ports), sfu, lambda: NOW)
    router = build_rooms_router(book, ports, ORIGIN)
    async with client_of(build_probe_app(extra=(router,)).app) as http:
        yield RoomsBench(http, homes, sfu, spaces)
