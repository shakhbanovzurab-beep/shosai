"""Streams of the `lead` persona beyond the calendar one: live, ended and members only.

Live (`live`): the host and a speaker on stage, a chat with a pinned message, entry
requests (waiting, waiting through the visit's link, denied) and a raised hand from
`pro`. Entry is open: a viewer with an account gets into the stream at once, and the
requests are visible in the control panel and through their own token. The draft takes
the viewer count from the SFU or from Redis; Redis is emptied before every recording, so
record.sh writes the value (recording/seed/redis.txt).

The draft forgets entry requests and raised hands after 10 and 20 minutes, while a
recording takes longer: their time is six hours ahead. The screen does not show it, and
the normalizer maps timestamps within that day to the parity clock.

Ended (`ended`): the chat archive is saved, so a viewer sees the audience's messages.
Members only (`members`): the draft answers a guest that an account is required.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from meetassist.features.stream.infrastructure.models import (
    Stream,
    StreamAdmission,
    StreamChatMessage,
    StreamMember,
    StreamRequest,
)
from meetassist.models.room import Room
from meetassist.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession

from stable_ids import KNOCKS, ROOMS, STREAM_INVITES, STREAMS

#: Чат эфира: автор (ключ персоны или гость), имя, текст, минут до момента стенда, со сцены, закреплено.
_LIVE_CHAT = (
    ("lead", "Мария Соколова", "Добрый день! Начинаем через минуту.", 24, True, False),
    ("guest-5eed00000001", "Олег", "Звук отличный, всё слышно", 22, False, False),
    ("max", "Жанна Морозова", "Сегодня покажу итоги квартала по продажам", 20, True, True),
    ("guest-5eed00000002", "Анна", "Будет ли запись эфира?", 15, False, False),
    ("lead", "Мария Соколова", "Да, запись пришлём всем участникам", 14, True, False),
)
_ENDED_CHAT = (
    ("lead", "Мария Соколова", "Спасибо всем, что пришли!", 30, True),
    ("guest-5eed00000004", "Игорь", "Спасибо, было полезно", 28, False),
    ("guest-5eed00000005", "Светлана", "Где взять презентацию?", 25, False),
)
#: Заявки на вход в эфир: ключ токена, гость, имя, статус.
_ADMISSIONS = (
    ("pending", "guest-5eed00000003", "Олег Петров", "pending"),
    ("wait", "guest-5eed00000006", "Гость", "pending"),
    ("denied", "guest-5eed00000007", "Гость", "denied"),
)


def _principal(author: str, accounts: dict[str, User]) -> str:
    return author if author.startswith("guest-") else str(accounts[author].id)


async def seed_streams(db: AsyncSession, accounts: dict[str, User], clock: datetime) -> None:
    """Seed the streams of `lead` and their queues."""
    lead = accounts["lead"]
    live = await _stream(db, lead, clock, "live", "Квартальные итоги продаж", status="live",
                         started_at=clock - timedelta(minutes=25))
    db.add(StreamMember(stream_id=live.id, principal=str(accounts["max"].id), display_name="Жанна Морозова",
                        role="speaker", position=1, created_at=clock - timedelta(minutes=25)))
    for author, name, text, minutes, from_stage, pinned in _LIVE_CHAT:
        db.add(StreamChatMessage(stream_id=live.id, principal=_principal(author, accounts), author_name=name,
                                 text=text, from_stage=from_stage, pinned=pinned,
                                 created_at=clock - timedelta(minutes=minutes)))
    pro = accounts["pro"]
    db.add(StreamRequest(stream_id=live.id, principal=str(pro.id), identity=f"{pro.id}__0000beef",
                         display_name="Егор Волков", status="pending", created_at=clock + timedelta(hours=6)))
    for key, identity, name, status in _ADMISSIONS:
        db.add(StreamAdmission(stream_id=live.id, knock_token=KNOCKS[key], identity=identity, display_name=name,
                               status=status, decided_at=clock + timedelta(hours=6) if status == "denied" else None,
                               created_at=clock + timedelta(hours=6)))
    ended = await _stream(db, lead, clock, "ended", "Запуск партнёрского портала", status="ended",
                          started_at=clock - timedelta(days=2), ended_at=clock - timedelta(days=2) + timedelta(minutes=58),
                          save_chat=True)
    for author, name, text, minutes, from_stage in _ENDED_CHAT:
        db.add(StreamChatMessage(stream_id=ended.id, principal=_principal(author, accounts), author_name=name,
                                 text=text, from_stage=from_stage,
                                 created_at=clock - timedelta(days=2) + timedelta(minutes=58 - minutes)))
    await _stream(db, lead, clock, "members", "Разбор для сотрудников", status="live",
                  started_at=clock - timedelta(minutes=10), registered_only=True)
    await db.flush()


async def _stream(db: AsyncSession, owner: User, clock: datetime, key: str, title: str, *, status: str,
                  started_at: datetime, ended_at: datetime | None = None, **settings: bool) -> Stream:
    """The stage (a room), the stream and the host on stage."""
    room = Room(id=ROOMS[f"{key}Stage"], owner_id=owner.id, name=title, lk_room_name=f"r-parity-{key}",
                invite_token=STREAM_INVITES[key], status="closed" if status == "ended" else "active",
                closed_at=ended_at, created_at=clock - timedelta(days=5))
    db.add(room)
    await db.flush()
    stream = Stream(id=STREAMS[key], owner_id=owner.id, room_id=room.id, title=title, status=status,
                    started_at=started_at, ended_at=ended_at, created_at=clock - timedelta(days=5), **settings)
    db.add(stream)
    await db.flush()
    db.add(StreamMember(stream_id=stream.id, principal=str(owner.id), display_name="Мария Соколова", role="host",
                        position=0, created_at=clock - timedelta(days=5)))
    return stream
