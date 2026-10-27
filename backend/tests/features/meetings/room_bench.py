"""Meetings' routes over the slot's homes, with an SFU double and the doubles of the ports."""

import uuid
from collections.abc import AsyncIterator, Collection, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta

import httpx
import pytest_asyncio
from prometheus_client import CollectorRegistry
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.idempotency.ledger import EffectLedger
from shosai.core.idempotency.metrics import EffectKeyMetrics
from shosai.core.kernel.homes import Home
from shosai.core.kv.metrics import KeyValueMetrics
from shosai.core.kv.rate_limits import RateLimiter
from shosai.core.ports.directory import PortDirectory
from shosai.features.billing.contracts import (
    ENTITLEMENTS,
    EntitlementSnapshot,
    EntitlementSource,
)
from shosai.features.billing.domain.plans import Audience, PlanLimits
from shosai.features.identity.contracts import (
    ACCOUNT_PROFILE_READER,
    AUTHENTICATOR,
    AccountProfile,
)
from shosai.features.meetings.application.chat import Chat
from shosai.features.meetings.application.joining import JoinDesk
from shosai.features.meetings.application.passes import PassCheck
from shosai.features.meetings.application.removals import Removals
from shosai.features.meetings.application.rooms import RoomBook
from shosai.features.meetings.application.video_server import (
    BucketTarget,
    EgressReport,
    PassRequest,
    RoomSpec,
    SessionPass,
    SfuParticipant,
    SfuRoom,
    SfuWebhook,
    VideoUnavailableError,
    WebhookRejectedError,
)
from shosai.features.meetings.channels.http.chat import build_chat_router
from shosai.features.meetings.channels.http.joining import build_joining_router
from shosai.features.meetings.channels.http.rooms import build_rooms_router
from shosai.features.meetings.infrastructure.room_passes import RoomPasses
from shosai.features.workspaces.contracts import MEMBERSHIP_READER
from tests.core.web.probe_app import build_probe_app, client_of
from tests.features.billing.people_bench import BearerOfTheTest
from tests.features.memory.facts_api_bench import Spaces
from tests.harness.database_access import DatabaseAccess

ORIGIN = "https://shosai.tech"
PLATFORM_CEILING = 6
NOW = datetime(2026, 10, 27, 12, tzinfo=UTC)


@dataclass
class SfuDouble:
    """The SFU as the test sets it: its rooms, their sessions and whether it answers."""

    rooms_held: dict[str, SfuRoom] = field(default_factory=dict)
    sessions: dict[str, list[SfuParticipant]] = field(default_factory=dict)
    deleted: list[str] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)
    published: list[tuple[str, str, bytes]] = field(default_factory=list)
    egress_reports: dict[str, EgressReport] = field(default_factory=dict)
    targets: dict[str, BucketTarget] = field(default_factory=dict)
    up: bool = True

    def _answering(self) -> None:
        if not self.up:
            raise VideoUnavailableError

    async def create_room(self, spec: RoomSpec) -> SfuRoom:
        """The room, made once."""
        self._answering()
        room = self.rooms_held.setdefault(
            spec.name,
            SfuRoom(
                spec.name, f"RM_{uuid.uuid4().hex[:12]}", 0, spec.metadata, NOW,
                spec.max_participants,
            ),
        )  # fmt: skip
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

    async def remove_participant(self, room_name: str, identity: str) -> bool:
        """Drop a session."""
        self._answering()
        before = self.sessions.get(room_name, [])
        self.sessions[room_name] = [item for item in before if item.identity != identity]
        return len(before) != len(self.sessions[room_name])

    async def publish(self, room_name: str, topic: str, payload: bytes) -> bool:
        """Keep what was published to a held room."""
        self._answering()
        if room_name not in self.rooms_held:
            return False
        self.published.append((room_name, topic, payload))
        return True

    async def set_attributes(
        self, room_name: str, identity: str, attributes: Mapping[str, str]
    ) -> bool:
        """Change a session's attributes; an empty value removes one."""
        self._answering()
        for index, item in enumerate(self.sessions.get(room_name, [])):
            if item.identity == identity:
                merged = {**item.attributes, **attributes}
                kept = {key: value for key, value in merged.items() if value}
                self.sessions[room_name][index] = replace(item, attributes=kept)
                return True
        return False

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

    async def record(self, room_name: str, target: BucketTarget) -> str:
        """A started recording's egress."""
        self._answering()
        egress_id = f"EG_{uuid.uuid4().hex[:12]}"
        self.egress_reports[egress_id] = EgressReport(egress_id, room_name, "EGRESS_STARTING")
        self.targets[egress_id] = target
        return egress_id

    async def stop_egress(self, egress_id: str) -> None:
        """Mark the egress ending."""
        self._answering()
        report = self.egress_reports[egress_id]
        self.egress_reports[egress_id] = replace(report, status="EGRESS_ENDING")

    async def egresses(
        self, room_name: str | None = None, *, active: bool = True
    ) -> Sequence[EgressReport]:
        """The egresses not over, or every one it knows when `active` is off."""
        self._answering()
        running = {"EGRESS_STARTING", "EGRESS_ACTIVE", "EGRESS_ENDING"}
        return [
            report
            for report in self.egress_reports.values()
            if (report.status in running or not active) and room_name in {None, report.room_name}
        ]

    async def egress(self, egress_id: str) -> EgressReport | None:
        """One egress as last set."""
        self._answering()
        return self.egress_reports.get(egress_id)

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
            held.name, held.sid, len(identities), held.metadata, NOW, held.max_participants
        )


@dataclass
class People:
    """The plan's ceiling of every owner and the names of signed-in people."""

    room_participants: int | None = None
    named: dict[uuid.UUID, str] = field(default_factory=dict)
    paid: bool = True
    file_manager_gb: int | None = None

    async def snapshot(self, home: Home, user_id: uuid.UUID) -> EntitlementSnapshot:
        """A plan with the test's ceiling."""
        del home
        return EntitlementSnapshot(
            user_id=user_id, plan_slug="pro", plan_name="Pro", audience=Audience.INDIVIDUAL,
            paid=self.paid, in_grace=False, paid_until=None,
            limits=PlanLimits(
                None, self.file_manager_gb, None, room_participants=self.room_participants
            ),
            capabilities=frozenset(), source=EntitlementSource.PERSONAL, workspace_id=None,
            version=1,
        )  # fmt: skip

    async def profile(self, session: AsyncSession, user_id: uuid.UUID) -> AccountProfile | None:
        """The person's name."""
        del session
        name = self.named.get(user_id)
        return None if name is None else AccountProfile(name, "ru", None)

    async def names(
        self, session: AsyncSession, user_ids: Collection[uuid.UUID]
    ) -> Mapping[uuid.UUID, str]:
        """The names of the people among the ids."""
        del session
        return {user_id: self.named[user_id] for user_id in user_ids if user_id in self.named}


@dataclass(frozen=True, slots=True)
class RoomsBench:
    """The routes, the doubles behind them and the slot's homes."""

    http: httpx.AsyncClient
    homes: DatabaseAccess
    sfu: SfuDouble
    spaces: Spaces
    people: People

    def bearer(self, person: uuid.UUID, home: Home = Home.RU) -> Mapping[str, str]:
        """The person's authorization header."""
        return {"Authorization": f"Bearer person:{person}:{home.value}"}


@pytest_asyncio.fixture
async def rooms_bench(homes: DatabaseAccess, valkey: Redis) -> AsyncIterator[RoomsBench]:
    sfu, spaces, people = SfuDouble(), Spaces(), People()
    ports = PortDirectory()
    ports.install(
        [
            AUTHENTICATOR.bind(BearerOfTheTest()),
            MEMBERSHIP_READER.bind(spaces),
            ENTITLEMENTS.bind(people),
            ACCOUNT_PROFILE_READER.bind(people),
        ]
    )
    registry = CollectorRegistry()
    effects = EffectLedger(EffectKeyMetrics(registry))
    book = RoomBook(homes.transactions, (effects, ports), sfu, lambda: NOW)
    passes = RoomPasses(valkey)
    desk = JoinDesk(homes.transactions, (sfu, passes, ports), PLATFORM_CEILING, lambda: NOW)
    limiter = RateLimiter(valkey, KeyValueMetrics(registry))
    routers = (
        build_rooms_router((book, Removals(homes.transactions, sfu, passes)), ports, ORIGIN),
        build_joining_router(desk, PassCheck(homes.transactions, passes), ports, limiter),
        build_chat_router(
            Chat(homes.transactions, (effects, limiter, sfu), lambda: NOW),
            PassCheck(homes.transactions, passes),
        ),
    )
    async with client_of(build_probe_app(extra=routers).app) as http:
        yield RoomsBench(http, homes, sfu, spaces, people)
