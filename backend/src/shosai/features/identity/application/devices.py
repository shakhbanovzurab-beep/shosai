"""The person's devices: their live sessions, one ended, or all but this one (FM-5).

A device is a refresh family that is neither revoked nor expired. Ending one revokes its
family in the home and marks it in Valkey, so its live access token stops on its next
request too. Another person's session id answers 404, like an unknown one (the draft's
anti-IDOR rule).
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Any, Final, cast
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import ColumnElement, Row, Select, Table, select, update

from shosai.core.db.transactions import HomeTransactions
from shosai.core.events.outbox import EventOutbox
from shosai.core.kernel.errors import AppError
from shosai.core.pagination.cursor import CursorCodec
from shosai.core.pagination.keyset import Keyset
from shosai.core.pagination.page import Page, PageRequest, page_of
from shosai.features.identity.contracts import Principal, SessionsRevoked
from shosai.features.identity.infrastructure.account_markers import AccountMarkers
from shosai.features.identity.infrastructure.session_records import RefreshSession


class DevicePosition(BaseModel):
    """Where a page of devices ended: the last family id (UUIDv7, newest first)."""

    id: UUID


@dataclass(frozen=True, slots=True)
class Device:
    """One signed-in device."""

    id: UUID
    client_kind: str
    device_label: str | None
    ip: str | None
    created_at: datetime
    last_used_at: datetime
    current: bool


CODEC: Final = CursorCodec("identity.devices", DevicePosition)
SESSIONS: Final = cast("Table", RefreshSession.__table__)
NEWEST_FIRST: Final = Keyset((SESSIONS.c.id,), descending=True)


class Devices:
    """List and end the person's sessions."""

    def __init__(
        self, transactions: HomeTransactions, markers: AccountMarkers, outbox: EventOutbox
    ) -> None:
        self._transactions = transactions
        self._markers = markers
        self._outbox = outbox

    async def page(self, principal: Principal, request: PageRequest) -> Page[Device]:
        """A page of the live sessions, newest first."""
        after = None if request.cursor is None else (CODEC.decode(request.cursor).id,)
        live: Select[tuple[Any, ...]] = select(
            SESSIONS.c.id,
            SESSIONS.c.client_kind,
            SESSIONS.c.device_label,
            SESSIONS.c.ip,
            SESSIONS.c.created_at,
            SESSIONS.c.last_used_at,
        ).where(
            SESSIONS.c.user_id == principal.user_id,
            SESSIONS.c.revoked_at.is_(None),
            SESSIONS.c.expires_at > datetime.now(UTC),
        )
        statement = NEWEST_FIRST.page(live, after, request.limit)
        async with self._transactions.begin(principal.scope(), read_only=True) as session:
            rows = list((await session.execute(statement)).all())
        return page_of(
            rows,
            request,
            CODEC,
            lambda row: _device(row, principal),
            lambda row: DevicePosition(id=row.id),
        )

    async def end(self, principal: Principal, family_id: UUID) -> None:
        """End one session of the person; another's or an unknown id is 404."""
        ended = await self._revoke(principal, RefreshSession.id == family_id, "device_ended")
        if not ended:
            raise AppError("device_not_found", HTTPStatus.NOT_FOUND)

    async def end_others(self, principal: Principal) -> int:
        """End every session but the current one; all of them for a token without one."""
        condition = (
            RefreshSession.id != principal.family_id
            if principal.family_id is not None
            else RefreshSession.id.is_not(None)
        )
        return len(await self._revoke(principal, condition, "signed_out_elsewhere"))

    async def _revoke(
        self, principal: Principal, condition: ColumnElement[bool], reason: str
    ) -> list[UUID]:
        async with self._transactions.begin(principal.scope()) as session:
            ended = list(
                await session.scalars(
                    update(RefreshSession)
                    .where(
                        RefreshSession.user_id == principal.user_id,
                        RefreshSession.revoked_at.is_(None),
                        condition,
                    )
                    .values(revoked_at=datetime.now(UTC), revoke_reason=reason)
                    .returning(RefreshSession.id)
                )
            )
            if ended:
                await self._outbox.add(session, SessionsRevoked(user_id=principal.user_id))
        await self._markers.revoke_families(ended)
        return ended


def _device(row: Row[Any], principal: Principal) -> Device:
    return Device(
        id=row.id,
        client_kind=row.client_kind,
        device_label=row.device_label,
        # psycopg отдаёт inet адресом из ipaddress: наружу — строкой.
        ip=None if row.ip is None else str(row.ip),
        created_at=row.created_at,
        last_used_at=row.last_used_at,
        current=row.id == principal.family_id,
    )
