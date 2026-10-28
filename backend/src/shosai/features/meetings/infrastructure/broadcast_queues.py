"""A broadcast's two queues in Valkey: raised hands for 20 minutes, the waiting room for 10.

Neither outlives its window (DATA_MAPPING §5.21: dropped), so neither is a table. A hand is
one key per principal and a knock one key per knock, each with its own life; a set per
broadcast lists them, and a reader drops what has expired. A lost Valkey loses the queues,
never a broadcast: a viewer raises the hand or knocks again.
"""

import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Final
from uuid import UUID

from redis.asyncio import Redis

from shosai.features.meetings.domain.broadcasts import HAND_TTL, KNOCK_TTL

PREFIX: Final = "meetings:bc:"
KNOCK_BYTES: Final = 18


class KnockState(StrEnum):
    """Where a knock stands: waiting for the host, let in or turned away."""

    WAITING = "waiting"
    ADMITTED = "admitted"
    DENIED = "denied"


@dataclass(frozen=True, slots=True)
class Hand:
    """A viewer asks to speak; the host may invite them to the stage."""

    principal: str
    identity: str
    name: str
    at: datetime
    invited: bool


@dataclass(frozen=True, slots=True)
class Knock:
    """A viewer waits to be let in."""

    id: str
    stream_id: UUID
    principal: str
    name: str
    at: datetime
    state: KnockState


def _text(value: bytes | str) -> str:
    return value.decode() if isinstance(value, bytes) else value


class BroadcastQueues:
    """Raised hands and the waiting room of every broadcast."""

    def __init__(self, valkey: Redis) -> None:
        self._valkey = valkey

    async def raise_hand(self, stream_id: UUID, hand: Hand) -> None:
        """Keep the hand for 20 minutes; raising it again keeps its place and invitation."""
        key, listed = self._hand_key(stream_id, hand.principal), f"{PREFIX}hands:{stream_id}"
        held = await self.hand(stream_id, hand.principal)
        kept = held or hand
        seconds = int(HAND_TTL.total_seconds())
        async with self._valkey.pipeline(transaction=True) as pipe:
            await pipe.set(key, self._hand_json(kept), ex=seconds)
            await pipe.sadd(listed, hand.principal)
            await pipe.expire(listed, seconds)
            await pipe.execute()

    async def invite(self, stream_id: UUID, principal: str) -> bool:
        """Mark the hand invited to the stage; False when it is gone."""
        held = await self.hand(stream_id, principal)
        if held is None:
            return False
        invited = Hand(held.principal, held.identity, held.name, held.at, invited=True)
        key = self._hand_key(stream_id, principal)
        return bool(await self._valkey.set(key, self._hand_json(invited), keepttl=True, xx=True))

    async def lower_hand(self, stream_id: UUID, principal: str) -> None:
        """Drop the hand, if any."""
        async with self._valkey.pipeline(transaction=True) as pipe:
            await pipe.delete(self._hand_key(stream_id, principal))
            await pipe.srem(f"{PREFIX}hands:{stream_id}", principal)
            await pipe.execute()

    async def hand(self, stream_id: UUID, principal: str) -> Hand | None:
        """The principal's hand while it lives."""
        raw = await self._valkey.get(self._hand_key(stream_id, principal))
        return None if raw is None else self._hand_of(_text(raw))

    async def hands(self, stream_id: UUID) -> list[Hand]:
        """The broadcast's raised hands, the earliest first."""
        listed = f"{PREFIX}hands:{stream_id}"
        principals = sorted(_text(item) for item in await self._valkey.smembers(listed))
        if not principals:
            return []
        raws = await self._valkey.mget([self._hand_key(stream_id, item) for item in principals])
        gone = [item for item, raw in zip(principals, raws, strict=True) if raw is None]
        if gone:
            await self._valkey.srem(listed, *gone)
        found = [self._hand_of(_text(raw)) for raw in raws if raw is not None]
        return sorted(found, key=lambda hand: hand.at)

    async def knock(self, stream_id: UUID, principal: str, name: str) -> Knock:
        """A new knock in the waiting room, alive for 10 minutes."""
        knock = Knock(
            id=secrets.token_urlsafe(KNOCK_BYTES), stream_id=stream_id, principal=principal,
            name=name, at=datetime.now(UTC), state=KnockState.WAITING,
        )  # fmt: skip
        seconds = int(KNOCK_TTL.total_seconds())
        listed = f"{PREFIX}knocks:{stream_id}"
        async with self._valkey.pipeline(transaction=True) as pipe:
            await pipe.set(f"{PREFIX}knock:{knock.id}", self._knock_json(knock), ex=seconds)
            await pipe.sadd(listed, knock.id)
            await pipe.expire(listed, seconds)
            await pipe.execute()
        return knock

    async def knock_of(self, knock_id: str) -> Knock | None:
        """The knock while it lives."""
        raw = await self._valkey.get(f"{PREFIX}knock:{knock_id}")
        return None if raw is None else self._knock_of(knock_id, _text(raw))

    async def waiting(self, stream_id: UUID) -> list[Knock]:
        """The knocks still waiting, the earliest first."""
        listed = f"{PREFIX}knocks:{stream_id}"
        ids = sorted(_text(item) for item in await self._valkey.smembers(listed))
        if not ids:
            return []
        raws = await self._valkey.mget([f"{PREFIX}knock:{knock_id}" for knock_id in ids])
        gone = [knock_id for knock_id, raw in zip(ids, raws, strict=True) if raw is None]
        if gone:
            await self._valkey.srem(listed, *gone)
        knocks = [
            self._knock_of(knock_id, _text(raw))
            for knock_id, raw in zip(ids, raws, strict=True)
            if raw is not None
        ]
        return sorted(
            (item for item in knocks if item.state is KnockState.WAITING), key=lambda item: item.at
        )

    async def answer(self, stream_id: UUID, knock_id: str, *, admitted: bool) -> bool:
        """Let the knock in or turn it away; False when it is gone or another broadcast's."""
        held = await self.knock_of(knock_id)
        if held is None or held.stream_id != stream_id:
            return False
        state = KnockState.ADMITTED if admitted else KnockState.DENIED
        answered = Knock(held.id, held.stream_id, held.principal, held.name, held.at, state)
        key = f"{PREFIX}knock:{knock_id}"
        return bool(await self._valkey.set(key, self._knock_json(answered), keepttl=True, xx=True))

    @staticmethod
    def _hand_key(stream_id: UUID, principal: str) -> str:
        return f"{PREFIX}hand:{stream_id}:{principal}"

    @staticmethod
    def _hand_json(hand: Hand) -> str:
        values = {"principal": hand.principal, "identity": hand.identity, "name": hand.name}
        return json.dumps(values | {"at": hand.at.isoformat(), "invited": hand.invited})

    @staticmethod
    def _hand_of(raw: str) -> Hand:
        values = json.loads(raw)
        return Hand(
            principal=values["principal"], identity=values["identity"], name=values["name"],
            at=datetime.fromisoformat(values["at"]), invited=bool(values["invited"]),
        )  # fmt: skip

    @staticmethod
    def _knock_json(knock: Knock) -> str:
        values = {
            "stream_id": str(knock.stream_id),
            "principal": knock.principal,
            "name": knock.name,
        }
        return json.dumps(values | {"at": knock.at.isoformat(), "state": knock.state.value})

    @staticmethod
    def _knock_of(knock_id: str, raw: str) -> Knock:
        values = json.loads(raw)
        return Knock(
            id=knock_id, stream_id=UUID(values["stream_id"]), principal=values["principal"],
            name=values["name"], at=datetime.fromisoformat(values["at"]),
            state=KnockState(values["state"]),
        )  # fmt: skip
