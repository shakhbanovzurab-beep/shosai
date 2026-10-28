"""What every part of a broadcast reads: its row by its room, its stage, whose part is whose,
and the push that tells the room to read its state again (MR-D7)."""

import json
from collections.abc import Sequence
from http import HTTPStatus
from typing import Final
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.kernel.errors import AppError
from shosai.features.meetings.application.video_server import VideoServer, VideoUnavailableError
from shosai.features.meetings.domain.broadcasts import TOPIC, StageRole
from shosai.features.meetings.domain.principals import principal_of
from shosai.features.meetings.infrastructure.stream_records import StreamMemberRecord, StreamRecord

PUSH_VERSION: Final = 1
log = structlog.stdlib.get_logger(__name__)


def broadcast_missing() -> AppError:
    """No broadcast behind this room or this id."""
    return AppError("broadcast_not_found", HTTPStatus.NOT_FOUND)


def not_allowed() -> AppError:
    """The part on the stage does not allow it."""
    return AppError("not_allowed", HTTPStatus.FORBIDDEN)


async def stream_of_room(
    session: AsyncSession, room_id: UUID, *, lock: bool = False
) -> StreamRecord:
    """The room's broadcast; `broadcast_not_found` when the room serves a call."""
    statement = select(StreamRecord).where(StreamRecord.room_id == room_id)
    stream = await session.scalar(statement.with_for_update() if lock else statement)
    if stream is None:
        raise broadcast_missing()
    return stream


async def stage_of(session: AsyncSession, stream_id: UUID) -> list[StreamMemberRecord]:
    """The stage in its order: the host first."""
    return list(
        (
            await session.scalars(
                select(StreamMemberRecord)
                .where(StreamMemberRecord.stream_id == stream_id)
                .order_by(StreamMemberRecord.position, StreamMemberRecord.created_at)
            )
        ).all()
    )


def role_of(stage: Sequence[StreamMemberRecord], principal: str) -> StageRole | None:
    """The principal's part on the stage; None for the audience."""
    member = next((item for item in stage if item.principal == principal), None)
    return None if member is None else StageRole(member.role)


def sessions_of(identities: Sequence[str], principal: str) -> list[str]:
    """The principal's sessions among the room's."""
    return [
        identity
        for identity in identities
        if (found := principal_of(identity)) is not None and found.value == principal
    ]


async def push(server: VideoServer, room_name: str, kind: str) -> None:
    """Tell everyone in the room on topic `stream` what changed; they read the state again."""
    payload = json.dumps({"v": PUSH_VERSION, "kind": kind}).encode()
    try:
        await server.publish(room_name, TOPIC, payload)
    except VideoUnavailableError:
        # Состояние уже записано: клиенты перечитают его при следующем пакете или переподключении.
        log.warning("Пакет трансляции не разослан SFU", kind=kind)
