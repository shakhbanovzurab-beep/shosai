"""The call's chat (MR-D11, meetings plan §3.5 flow 3).

A message comes through meetings with a room pass: the room is open and its principal not
removed (the pass check), a call goes on (`no_live_call`), the sender keeps within 20 messages
per 10 seconds (`rate_limited` with its wait) and the text within its rules. It is kept with the
call under the next `seq` — the call's row is locked while the sequence is taken — once per
`Idempotency-Key`, and published to the room on topic `chat` after the commit. The SFU missing a
message costs nothing: everyone reads what they missed after the last `seq` they hold. The chat
lives for the call only; its handover deletes it (until notes take it, B3).
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from typing import Final
from uuid import UUID

import structlog
from pydantic import BaseModel
from sqlalchemy import func, select

from shosai.core.db.transactions import HomeTransactions
from shosai.core.idempotency.ledger import EffectKey, EffectLedger, EffectScope, fingerprint_of
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.ids import new_id
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.kv.rate_limits import RateLimit, RateLimiter
from shosai.core.web.rate_limit import RateLimitedError
from shosai.features.meetings.application.video_server import VideoServer, VideoUnavailableError
from shosai.features.meetings.domain.calls import CallState
from shosai.features.meetings.domain.chat import (
    HISTORY_PAGE_MAX,
    RATE_COUNT,
    RATE_WINDOW_SECONDS,
    TOPIC,
    ChatMessage,
    ChatRuleError,
    checked_text,
    next_seq,
    payload,
)
from shosai.features.meetings.infrastructure.call_records import RoomChatMessageRecord
from shosai.features.meetings.infrastructure.room_passes import PassHolder
from shosai.features.meetings.infrastructure.room_records import RoomCallRecord, RoomRecord

SENDS: Final = EffectScope("meetings.chat_send", timedelta(hours=24))
CHAT_RATE: Final = RateLimit(
    "meetings_chat",
    rate=RATE_COUNT,
    period=timedelta(seconds=RATE_WINDOW_SECONDS),
    burst=RATE_COUNT,
)
log = structlog.stdlib.get_logger(__name__)


class SentPrint(BaseModel):
    """The print of a message, for its `Idempotency-Key`."""

    text: str


class Sent(BaseModel):
    """The outcome a repeated key answers: the message it kept."""

    message_id: UUID


@dataclass(frozen=True, slots=True)
class ChatPage:
    """Messages after a sequence and the `after` of the next page, if any."""

    items: list[ChatMessage]
    next_after: int | None


def message_of(record: RoomChatMessageRecord) -> ChatMessage:
    """The domain's message of a row."""
    return ChatMessage(
        id=record.id, call_id=record.call_id, seq=record.seq, principal=record.principal,
        identity=record.identity, author=record.author, text=record.body, sent_at=record.sent_at,
    )  # fmt: skip


class Chat:
    """The chat of the calls of rooms in every home."""

    def __init__(
        self,
        transactions: HomeTransactions,
        services: tuple[EffectLedger, RateLimiter, VideoServer],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._effects, self._limiter, self._server = services
        self._clock = clock

    async def send(self, holder: PassHolder, raw: str, client_key: str) -> ChatMessage:
        """Keep a message with the call once per key, then publish it to the room."""
        try:
            text = checked_text(raw)
        except ChatRuleError as error:
            raise AppError(error.code, HTTPStatus.UNPROCESSABLE_ENTITY) from error
        decision = await self._limiter.check(CHAT_RATE, f"{holder.room_id}:{holder.principal}")
        if not decision.allowed:
            raise RateLimitedError(decision.retry_after)
        effect = EffectKey(
            SENDS, f"{holder.principal}:{client_key}", fingerprint_of(SentPrint(text=text))
        )
        scope = TenancyScope(holder.home, holder.owner_id, holder.org_id)
        async with self._transactions.begin(scope) as session:
            call = await session.scalar(
                select(RoomCallRecord)
                .where(
                    RoomCallRecord.room_id == holder.room_id,
                    RoomCallRecord.state == CallState.LIVE.value,
                )
                .with_for_update()
            )
            if call is None:
                raise AppError("no_live_call", HTTPStatus.CONFLICT)
            live = call

            async def first() -> Sent:
                last = await session.scalar(
                    select(func.max(RoomChatMessageRecord.seq)).where(
                        RoomChatMessageRecord.call_id == live.id
                    )
                )
                record = RoomChatMessageRecord(
                    id=new_id(), call_id=live.id, owner_id=holder.owner_id, org_id=holder.org_id,
                    seq=next_seq(last), principal=holder.principal, identity=holder.identity,
                    author=holder.author, body=text, sent_at=self._clock(),
                )  # fmt: skip
                session.add(record)
                await session.flush()
                return Sent(message_id=record.id)

            made = await self._effects.once(session, effect, Sent, first)
            message = message_of(
                await session.get_one(RoomChatMessageRecord, made.outcome.message_id)
            )
            room_name = await session.scalar(
                select(RoomRecord.lk_room_name).where(RoomRecord.id == holder.room_id)
            )
        if not made.replayed and room_name is not None:
            await self._publish(room_name, message)
        return message

    async def history(self, holder: PassHolder, after: int, limit: int) -> ChatPage:
        """The live call's messages after a sequence, oldest first."""
        size = max(1, min(limit, HISTORY_PAGE_MAX))
        scope = TenancyScope(holder.home, holder.owner_id, holder.org_id)
        async with self._transactions.begin(scope, read_only=True) as session:
            rows = (
                await session.scalars(
                    select(RoomChatMessageRecord)
                    .join(RoomCallRecord, RoomCallRecord.id == RoomChatMessageRecord.call_id)
                    .where(
                        RoomCallRecord.room_id == holder.room_id,
                        RoomCallRecord.state == CallState.LIVE.value,
                        RoomChatMessageRecord.seq > after,
                    )
                    .order_by(RoomChatMessageRecord.seq)
                    .limit(size + 1)
                )
            ).all()
        items = [message_of(row) for row in rows[:size]]
        return ChatPage(items, items[-1].seq if len(rows) > size else None)

    async def _publish(self, room_name: str, message: ChatMessage) -> None:
        try:
            await self._server.publish(room_name, TOPIC, payload(message))
        except VideoUnavailableError:
            # Сообщение сохранено: клиенты дочитают его по seq после переподключения.
            log.warning("Сообщение чата не разослано SFU", call_id=str(message.call_id))
