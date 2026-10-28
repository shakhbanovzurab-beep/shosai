"""Joining a room by its link (meetings plan §3.5 flow 2, MR-D2).

The token is looked up in both homes at once, through the tables' owner's function, so the
link reveals nothing and a room in either home is found in one round trip. The join then
reads the room in its owner's scope and decides in the domain's order: unknown or a hidden
owner, finished, removed, full. The first to join creates the SFU room with the owner's
ceiling — the plan's value capped by the platform's — and its marks; anyone after counts the
people already in it. Each join is a new session of its principal: a LiveKit pass for 10
minutes and a room pass for meetings' own routes.
"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Final
from uuid import UUID

import structlog
from sqlalchemy import select, text

from shosai.core.db.errors import HomeUnavailableError
from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.features.billing.contracts import ENTITLEMENTS
from shosai.features.identity.contracts import ACCOUNT_PROFILE_READER
from shosai.features.identity.contracts import Principal as Person
from shosai.features.meetings.application.room_reads import recording_on, room_of
from shosai.features.meetings.application.video_server import (
    PassRequest,
    RoomSpec,
    SessionPass,
    VideoServer,
)
from shosai.features.meetings.domain.invites import is_invite_token
from shosai.features.meetings.domain.joining import (
    IN_CALL,
    ROOM_PASS_TTL,
    CallRole,
    JoinFacts,
    JoinRefusal,
    call_role,
    join_refusal,
)
from shosai.features.meetings.domain.principals import (
    NameRuleError,
    Principal,
    checked_name,
    new_identity,
    principal_of,
)
from shosai.features.meetings.domain.rooms import ClosedBy, Room, room_ceiling
from shosai.features.meetings.domain.wire import RoomMarks, device_attributes, room_metadata
from shosai.features.meetings.infrastructure.room_passes import PassHolder, RoomPasses
from shosai.features.meetings.infrastructure.room_records import RoomBanRecord, RoomRecord
from shosai.features.meetings.infrastructure.stream_records import StreamRecord

# Потолок, который не ограничивает: для отказов, решаемых до чтения SFU.
CEILING_MAX: Final = 1_000_000
LOOKUP = text("SELECT room_id, owner_id, org_id FROM meetings_room_by_token(:token)")
log = structlog.stdlib.get_logger(__name__)


REFUSAL_STATUS: Final = {
    JoinRefusal.NOT_FOUND: HTTPStatus.NOT_FOUND,
    JoinRefusal.ROOM_FINISHED: HTTPStatus.GONE,
    JoinRefusal.REMOVED: HTTPStatus.FORBIDDEN,
    JoinRefusal.ROOM_FULL: HTTPStatus.CONFLICT,
}


class JoinRefusedError(AppError):
    """The link does not admit; the code says why."""

    def __init__(self, refusal: JoinRefusal) -> None:
        super().__init__(refusal.value, REFUSAL_STATUS[refusal])


@dataclass(frozen=True, slots=True)
class Entrant:
    """Who opens the link: a principal and the name they join under."""

    principal: Principal
    name: str
    device: dict[str, str | None]


@dataclass(frozen=True, slots=True)
class Admission:
    """What a join gives: the room, the session's passes and its part in the call."""

    room: Room
    marks: RoomMarks
    session: SessionPass
    room_pass: str
    pass_expires_at: datetime
    identity: str
    role: CallRole
    ceiling: int


@dataclass(frozen=True, slots=True)
class FoundRoom:
    """Where a token's room lives."""

    home: Home
    room_id: UUID
    owner_id: UUID
    org_id: UUID | None


class JoinDesk:
    """The public join of rooms in every home."""

    def __init__(
        self,
        transactions: HomeTransactions,
        services: tuple[VideoServer, RoomPasses, PortDirectory],
        platform_ceiling: int,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._server, self._passes, self._ports = services
        self._platform_ceiling = platform_ceiling
        self._clock = clock

    async def entrant(
        self, person: Person | None, name: str | None, device: dict[str, str | None]
    ) -> Entrant:
        """The principal and name of whoever opens the link: a person under their profile's
        name, a guest under the name they give."""
        if person is None:
            try:
                return Entrant(Principal.new_guest(), checked_name(name), device)
            except NameRuleError as error:
                raise AppError(error.code, HTTPStatus.UNPROCESSABLE_ENTITY) from error
        async with self._transactions.begin(person.scope(), read_only=True) as session:
            profile = await self._ports.get(ACCOUNT_PROFILE_READER).profile(session, person.user_id)
        shown = profile.display_name if profile is not None and profile.display_name else name
        try:
            clean = checked_name(shown)
        except NameRuleError as error:
            raise AppError(error.code, HTTPStatus.UNPROCESSABLE_ENTITY) from error
        return Entrant(Principal.of_user(person.user_id), clean, device)

    async def find(self, token: str) -> FoundRoom:
        """The token's room in whichever home holds it; `not_found` otherwise."""
        if not is_invite_token(token):
            raise JoinRefusedError(JoinRefusal.NOT_FOUND)
        answers = await asyncio.gather(
            *(self._lookup(home, token) for home in Home), return_exceptions=True
        )
        found = [answer for answer in answers if isinstance(answer, FoundRoom)]
        if found:
            return found[0]
        failures = [answer for answer in answers if isinstance(answer, BaseException)]
        if failures:
            # Комната может быть в недоступном доме: «не найдено» здесь было бы неправдой.
            raise failures[0]
        raise JoinRefusedError(JoinRefusal.NOT_FOUND)

    async def admit(self, found: FoundRoom, entrant: Entrant) -> Admission:
        """Let the entrant in, or refuse in the domain's order."""
        scope = TenancyScope(found.home, found.owner_id, found.org_id)
        async with self._transactions.begin(scope, read_only=True) as session:
            record = await session.get(RoomRecord, found.room_id)
            # Комната трансляции — не звонок: её ссылка ведёт в эфир, а не в разговор.
            broadcast = await session.scalar(
                select(StreamRecord.id).where(StreamRecord.room_id == found.room_id)
            )
            if record is None or broadcast is not None:
                raise JoinRefusedError(JoinRefusal.NOT_FOUND)
            room = room_of(record)
            banned = await session.scalar(
                select(RoomBanRecord.id).where(
                    RoomBanRecord.room_id == room.id,
                    RoomBanRecord.principal == entrant.principal.value,
                )
            )
            marks = RoomMarks(notes=room.notes_on, recording=await recording_on(session, room.id))
        facts = JoinFacts(
            room=room,
            owner_hidden=room.closed_by is ClosedBy.ACCOUNT,
            principal=entrant.principal,
            banned=banned is not None,
            present=0,
            ceiling=CEILING_MAX,
        )
        # Сначала отказы, которым не нужен SFU: закрытая комната и снятый участник его не трогают.
        refusal = join_refusal(facts)
        ceiling = CEILING_MAX
        if refusal is None:
            ceiling, present = await self._occupancy(found, room, marks)
            refusal = join_refusal(replace(facts, present=present, ceiling=ceiling))
        if refusal is not None:
            log.info("Вход по ссылке отклонён", room_id=str(room.id), refusal=refusal.value)
            raise JoinRefusedError(refusal)
        return await self._issue(found, room, (entrant, marks, ceiling))

    async def _occupancy(self, found: FoundRoom, room: Room, marks: RoomMarks) -> tuple[int, int]:
        """The call's ceiling and how many people are in it, creating the SFU room if needed."""
        if not room.is_open:
            return self._platform_ceiling, 0
        held = await self._server.rooms([room.lk_room_name])
        if held:
            people = await self._server.participants(room.lk_room_name)
            present = sum(1 for person in people if principal_of(person.identity) is not None)
            return held[0].max_participants or self._platform_ceiling, present
        snapshot = await self._ports.get(ENTITLEMENTS).snapshot(found.home, found.owner_id)
        ceiling = room_ceiling(snapshot.limits.room_participants, self._platform_ceiling)
        spec = RoomSpec(room.lk_room_name, ceiling, room_metadata(room.id, room.owner_id, marks))
        await self._server.create_room(spec)
        return ceiling, 0

    async def _issue(
        self, found: FoundRoom, room: Room, admitted: tuple[Entrant, RoomMarks, int]
    ) -> Admission:
        entrant, marks, ceiling = admitted
        identity = new_identity(entrant.principal)
        session = self._server.session_pass(
            PassRequest(
                room_name=room.lk_room_name,
                identity=identity,
                name=entrant.name,
                grants=IN_CALL,
                attributes=device_attributes(entrant.device),
            ),
            self._clock(),
        )
        holder = PassHolder(
            room_id=room.id, home=found.home, owner_id=found.owner_id, org_id=found.org_id,
            principal=entrant.principal.value, identity=identity, author=entrant.name,
        )  # fmt: skip
        room_pass = await self._passes.issue(holder)
        now = self._clock()
        log.info("Вход по ссылке", room_id=str(room.id), guest=entrant.principal.user_id is None)
        return Admission(
            room=room, marks=marks, session=session, room_pass=room_pass,
            pass_expires_at=now + ROOM_PASS_TTL, identity=identity,
            role=call_role(room, entrant.principal), ceiling=ceiling,
        )  # fmt: skip

    async def _lookup(self, home: Home, token: str) -> FoundRoom | None:
        try:
            async with self._transactions.begin(TenancyScope(home), read_only=True) as session:
                row = (await session.execute(LOOKUP, {"token": token})).first()
        except HomeUnavailableError:
            log.warning("Дом не ответил на поиск комнаты по ссылке", home=home.value)
            raise
        if row is None:
            return None
        return FoundRoom(home=home, room_id=row.room_id, owner_id=row.owner_id, org_id=row.org_id)
