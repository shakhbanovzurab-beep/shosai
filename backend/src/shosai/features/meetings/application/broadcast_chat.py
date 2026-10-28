"""The broadcast's chat (MR-D7, meetings A12b).

A message comes with the room's pass. The host's chat mode decides who writes — everyone,
the stage only, or nobody — and the sender keeps within their part's rate: 5 messages per
10 seconds for the audience, who ask, 20 for the stage, who answer. A message is kept under
the next number of the broadcast — its row is locked while the number is taken — once per
`Idempotency-Key`, marked when it comes from the stage, and announced on topic `stream`;
everyone reads what they miss after the last number they hold.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from typing import Final

from pydantic import BaseModel
from sqlalchemy import func, select

from shosai.core.db.transactions import HomeTransactions
from shosai.core.idempotency.ledger import EffectKey, EffectLedger, EffectScope, fingerprint_of
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.ids import new_id
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.kv.rate_limits import RateLimit, RateLimiter
from shosai.core.web.rate_limit import RateLimitedError
from shosai.features.meetings.application.broadcast_reads import (
    not_allowed,
    push,
    role_of,
    stage_of,
    stream_of_room,
)
from shosai.features.meetings.application.video_server import VideoServer
from shosai.features.meetings.domain.broadcasts import (
    CHAT_BURST_AUDIENCE,
    CHAT_BURST_STAGE,
    CHAT_WINDOW_SECONDS,
    BroadcastState,
)
from shosai.features.meetings.domain.chat import (
    HISTORY_PAGE_MAX,
    ChatRuleError,
    checked_text,
    next_seq,
)
from shosai.features.meetings.infrastructure.room_passes import PassHolder
from shosai.features.meetings.infrastructure.room_records import RoomRecord
from shosai.features.meetings.infrastructure.stream_records import StreamChatMessageRecord

SENDS: Final = EffectScope("meetings.broadcast_chat_send", timedelta(hours=24))
WINDOW: Final = timedelta(seconds=CHAT_WINDOW_SECONDS)
AUDIENCE_RATE: Final = RateLimit(
    "meetings_broadcast_chat_audience", CHAT_BURST_AUDIENCE, WINDOW, CHAT_BURST_AUDIENCE
)
STAGE_RATE: Final = RateLimit(
    "meetings_broadcast_chat_stage", CHAT_BURST_STAGE, WINDOW, CHAT_BURST_STAGE
)


class SentPrint(BaseModel):
    """The print of a message, for its `Idempotency-Key`."""

    text: str


class Sent(BaseModel):
    """The outcome a repeated key answers: the message it kept."""

    seq: int


@dataclass(frozen=True, slots=True)
class BroadcastMessage:
    """A message of the broadcast's chat."""

    seq: int
    principal: str
    author: str
    text: str
    from_stage: bool
    sent_at: datetime


def message_of(record: StreamChatMessageRecord) -> BroadcastMessage:
    """The message of a row."""
    return BroadcastMessage(
        seq=record.seq, principal=record.principal, author=record.author, text=record.body,
        from_stage=record.from_stage, sent_at=record.created_at,
    )  # fmt: skip


class BroadcastChat:
    """The chat of broadcasts in every home."""

    def __init__(
        self,
        transactions: HomeTransactions,
        services: tuple[EffectLedger, RateLimiter, VideoServer],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._effects, self._limiter, self._server = services
        self._clock = clock

    async def send(self, holder: PassHolder, raw: str, client_key: str) -> BroadcastMessage:
        """Keep a message once per key, then announce it to the room."""
        try:
            text = checked_text(raw)
        except ChatRuleError as error:
            raise AppError(error.code, HTTPStatus.UNPROCESSABLE_ENTITY) from error
        scope = TenancyScope(holder.home, holder.owner_id, holder.org_id)
        async with self._transactions.begin(scope) as session:
            stream = await stream_of_room(session, holder.room_id, lock=True)
            role = role_of(await stage_of(session, stream.id), holder.principal)
            if stream.status == BroadcastState.ENDED.value or stream.chat_mode == "off":
                raise AppError("chat_closed", HTTPStatus.CONFLICT)
            if stream.chat_mode == "speakers" and role is None:
                raise not_allowed()
            decision = await self._limiter.check(
                AUDIENCE_RATE if role is None else STAGE_RATE, f"{stream.id}:{holder.principal}"
            )
            if not decision.allowed:
                raise RateLimitedError(decision.retry_after)
            effect = EffectKey(
                SENDS, f"{holder.principal}:{client_key}", fingerprint_of(SentPrint(text=text))
            )

            async def first() -> Sent:
                last = await session.scalar(
                    select(func.max(StreamChatMessageRecord.seq)).where(
                        StreamChatMessageRecord.stream_id == stream.id
                    )
                )
                record = StreamChatMessageRecord(
                    id=new_id(), stream_id=stream.id, owner_id=holder.owner_id,
                    org_id=holder.org_id, seq=next_seq(last), principal=holder.principal,
                    author=holder.author, body=text, from_stage=role is not None,
                    created_at=self._clock(),
                )  # fmt: skip
                session.add(record)
                await session.flush()
                return Sent(seq=record.seq)

            made = await self._effects.once(session, effect, Sent, first)
            kept = await session.scalar(
                select(StreamChatMessageRecord).where(
                    StreamChatMessageRecord.stream_id == stream.id,
                    StreamChatMessageRecord.seq == made.outcome.seq,
                )
            )
            room = await session.get_one(RoomRecord, holder.room_id)
        if kept is None:
            raise AppError("message_not_found", HTTPStatus.NOT_FOUND)
        if not made.replayed:
            await push(self._server, room.lk_room_name, "chat")
        return message_of(kept)

    async def history(
        self, holder: PassHolder, after: int, limit: int
    ) -> tuple[list[BroadcastMessage], int | None]:
        """The messages after a number, oldest first, and the `after` of the next page."""
        size = max(1, min(limit, HISTORY_PAGE_MAX))
        scope = TenancyScope(holder.home, holder.owner_id, holder.org_id)
        async with self._transactions.begin(scope, read_only=True) as session:
            stream = await stream_of_room(session, holder.room_id)
            rows = (
                await session.scalars(
                    select(StreamChatMessageRecord)
                    .where(
                        StreamChatMessageRecord.stream_id == stream.id,
                        StreamChatMessageRecord.seq > after,
                        StreamChatMessageRecord.deleted_at.is_(None),
                    )
                    .order_by(StreamChatMessageRecord.seq)
                    .limit(size + 1)
                )
            ).all()
        items = [message_of(row) for row in rows[:size]]
        return items, items[-1].seq if len(rows) > size else None
