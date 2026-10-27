"""Room passes in Valkey: what lets a session use meetings' routes in its call (meetings plan §3.3).

A pass is an opaque random token; Valkey keeps only its SHA-256, so a dump of Valkey lets no
one into a call. It names the room, its home, owner and space, the principal and session, and
the name the pass was issued with; it lives 12 hours and is renewed while the room is open.
Each principal's passes of a room are listed, so removing someone revokes every session of
theirs at once. A lost Valkey loses the passes, never a room: the client joins again.
"""

import hashlib
import json
import secrets
from dataclasses import asdict, dataclass
from datetime import timedelta
from typing import Final
from uuid import UUID

from redis.asyncio import Redis

from shosai.core.kernel.homes import Home
from shosai.features.meetings.domain.joining import ROOM_PASS_TTL

HOLDER_PREFIX: Final = "meetings:pass:"
PRINCIPAL_PREFIX: Final = "meetings:passes:"
TOKEN_BYTES: Final = 32


@dataclass(frozen=True, slots=True)
class PassHolder:
    """Who a pass lets in, and where."""

    room_id: UUID
    home: Home
    owner_id: UUID
    org_id: UUID | None
    principal: str
    identity: str
    author: str


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _pass_key(digest: str) -> str:
    return f"{HOLDER_PREFIX}{digest}"


def _principal_key(room_id: UUID, principal: str) -> str:
    return f"{PRINCIPAL_PREFIX}{room_id}:{principal}"


def _encoded(holder: PassHolder) -> str:
    values = asdict(holder)
    values.update(
        room_id=str(holder.room_id),
        home=holder.home.value,
        owner_id=str(holder.owner_id),
        org_id=None if holder.org_id is None else str(holder.org_id),
    )
    return json.dumps(values, separators=(",", ":"))


def _text(value: bytes | str) -> str:
    return value.decode() if isinstance(value, bytes) else value


def _decoded(raw: bytes | str) -> PassHolder:
    values = json.loads(raw)
    org = values["org_id"]
    return PassHolder(
        room_id=UUID(values["room_id"]),
        home=Home(values["home"]),
        owner_id=UUID(values["owner_id"]),
        org_id=None if org is None else UUID(org),
        principal=values["principal"],
        identity=values["identity"],
        author=values["author"],
    )


class RoomPasses:
    """Issue, read, renew and revoke room passes."""

    def __init__(self, valkey: Redis, ttl: timedelta = ROOM_PASS_TTL) -> None:
        self._valkey = valkey
        self._seconds = int(ttl.total_seconds())

    async def issue(self, holder: PassHolder) -> str:
        """A new pass for the holder."""
        token = secrets.token_urlsafe(TOKEN_BYTES)
        digest = _digest(token)
        listed = _principal_key(holder.room_id, holder.principal)
        async with self._valkey.pipeline(transaction=True) as pipe:
            await pipe.set(_pass_key(digest), _encoded(holder), ex=self._seconds)
            await pipe.sadd(listed, digest)
            await pipe.expire(listed, self._seconds)
            await pipe.execute()
        return token

    async def holder(self, token: str) -> PassHolder | None:
        """Who the pass lets in; None for an unknown, expired or revoked pass."""
        raw = await self._valkey.get(_pass_key(_digest(token)))
        return None if raw is None else _decoded(raw)

    async def renew(self, token: str, holder: PassHolder) -> str:
        """A fresh pass for the same holder; the old one stops working."""
        fresh = await self.issue(holder)
        digest = _digest(token)
        async with self._valkey.pipeline(transaction=True) as pipe:
            await pipe.delete(_pass_key(digest))
            await pipe.srem(_principal_key(holder.room_id, holder.principal), digest)
            await pipe.execute()
        return fresh

    async def revoke(self, room_id: UUID, principal: str) -> int:
        """Revoke every pass of the principal in the room; how many there were."""
        listed = _principal_key(room_id, principal)
        digests = [_text(item) for item in await self._valkey.smembers(listed)]
        async with self._valkey.pipeline(transaction=True) as pipe:
            for digest in digests:
                await pipe.delete(_pass_key(digest))
            await pipe.delete(listed)
            await pipe.execute()
        return len(digests)
