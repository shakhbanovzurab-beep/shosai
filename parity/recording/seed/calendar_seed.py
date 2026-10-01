"""Календарь «руководителя»: события июля, видеовстреча, стрим, Google и iCal.

Момент стенда — пятница 17 июля 2026, 15:00 по Москве. Сетка месяца показывает
29 июня — 9 августа. Пятнадцатого пять событий — у дня кнопка «+N». Сегодняшнее
событие уже прошло. Будущие события лежат дальше суток от момента стенда:
нормализатор фикстур считает отметки в пределах суток «сейчас» API и заменил бы их.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from meetassist.features.stream.infrastructure.models import Stream, StreamMember
from meetassist.models.calendar_event import CalendarEvent
from meetassist.models.calendar_integration import CalendarIntegration
from meetassist.models.calendar_sync import CalendarSyncState
from meetassist.models.oauth_account import OAuthAccount
from meetassist.models.room import Room
from meetassist.models.session import Session
from meetassist.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession

from stable_ids import ICAL_TOKEN, ROOM_INVITE, STREAM_INVITE

_ZONE = "Europe/Moscow"
_GOOGLE_ACCOUNT = "maria.sokolova@gmail.com"
_TEAM = [{"name": "Иван Петров", "email": "ivan@acme.test"}, {"name": "Ольга Ким", "email": "olga@acme.test"}]

#: Событие: день июля (или (месяц, день)), час и минута UTC, минуты, тип, название.
_EVENTS = (
    ((7, 1), 7, 0, 30, "meeting", "Планёрка", {}),
    ((7, 3), 11, 0, 60, "meeting", "Обед с партнёром", {"location": "Кафе «Пушкин»"}),
    ((7, 8), 13, 0, 40, "meeting", "Демо для клиента Acme", {"session": "demo"}),
    ((7, 10), 6, 0, 30, "task", "Отправить счёт Acme", {}),
    ((7, 15), 6, 0, 30, "meeting", "Стендап", {}),
    ((7, 15), 8, 0, 60, "meeting", "Ревью дизайна портала", {"participants": _TEAM}),
    ((7, 15), 11, 0, 60, "meeting", "Интервью: фронтенд", {}),
    ((7, 15), 13, 30, 30, "meeting", "Созвон с юристом", {}),
    ((7, 15), 15, 0, 30, "meeting", "Разбор метрик", {}),
    ((7, 17), 7, 0, 47, "meeting", "Планирование бюджета Q4", {"session": "budget"}),
    ((7, 20), 7, 0, 60, "meeting", "Созвон с Acme", {"room": True, "participants": _TEAM,
                                                       "description": "Статус внедрения и план на август"}),
    ((7, 20), 15, 0, 60, "stream", "Эфир: итоги квартала", {"stream": True}),
    ((7, 21), 9, 0, 60, "meeting", "Ревью бюджета", {"location": "Переговорная 3", "participants": _TEAM,
                                                     "description": "Согласовать бюджет маркетинга и найма"}),
    ((7, 24), 7, 0, 30, "task", "Сдать смету по маркетингу", {}),
    ((7, 28), 6, 0, 15, "reminder", "Оплатить хостинг", {}),
    ((8, 3), 7, 0, 30, "meeting", "Планёрка", {}),
)


async def seed_calendar(db: AsyncSession, owner: User, clock: datetime, sessions: dict[str, Session]) -> None:
    """Засевает календарь владельца, его подключение Google и ссылку iCal."""
    room = Room(owner_id=owner.id, name="Созвон с Acme", lk_room_name="r-parity-acme", invite_token=ROOM_INVITE,
                status="active", created_at=clock - timedelta(days=3))
    stage = Room(owner_id=owner.id, name="Эфир: итоги квартала", lk_room_name="r-parity-stream",
                 invite_token=STREAM_INVITE, status="active", created_at=clock - timedelta(days=3))
    db.add_all([room, stage])
    await db.flush()
    stream = Stream(owner_id=owner.id, room_id=stage.id, title="Эфир: итоги квартала",
                    description="Итоги второго квартала для всей компании", status="scheduled",
                    created_at=clock - timedelta(days=3))
    db.add(stream)
    await db.flush()
    db.add(StreamMember(stream_id=stream.id, principal=str(owner.id), display_name="Мария Соколова", role="host",
                        position=0, created_at=clock - timedelta(days=3)))
    for index, ((month, day), hour, minute, minutes, kind, title, extra) in enumerate(_EVENTS):
        start = clock.replace(month=month, day=day, hour=hour, minute=minute, second=0, microsecond=0)
        session_key = extra.get("session")
        db.add(
            CalendarEvent(
                owner_id=owner.id,
                title=title,
                description=extra.get("description"),
                start_at=start,
                end_at=start + timedelta(minutes=minutes),
                event_type=kind,
                location=extra.get("location"),
                timezone=_ZONE,
                participants=list(extra.get("participants", [])),
                reminders=[{"minutes_before": 15}] if kind == "meeting" else [],
                session_id=None if session_key is None else sessions[str(session_key)].id,
                meeting_room_id=room.id if extra.get("room") else stage.id if extra.get("stream") else None,
                created_at=clock - timedelta(days=40) + timedelta(minutes=index),
            )
        )
    await _google(db, owner, clock)
    owner.ical_token = ICAL_TOKEN
    await db.flush()


async def _google(db: AsyncSession, owner: User, clock: datetime) -> None:
    """Подключённый Google: основной календарь и семейный, оба синхронизированы."""
    account = OAuthAccount(user_id=owner.id, provider="google", external_account_id="parity-google-account",
                           display_name=_GOOGLE_ACCOUNT, access_token_enc=b"parity-seed", expires_at=None, scopes=[],
                           status="active", created_at=clock - timedelta(days=14))
    db.add(account)
    await db.flush()
    integration = CalendarIntegration(user_id=owner.id, provider="google", enabled=True, oauth_account_id=account.id,
                                      write_calendar_id=_GOOGLE_ACCOUNT, created_at=clock - timedelta(days=14))
    db.add(integration)
    await db.flush()
    synced = clock - timedelta(hours=2)
    for calendar, primary in ((_GOOGLE_ACCOUNT, True), ("family.sokolovy@group.calendar.google.com", False)):
        db.add(CalendarSyncState(integration_id=integration.id, external_calendar_id=calendar,
                                 is_write_target=primary, last_full_sync_at=synced - timedelta(days=13),
                                 last_incremental_sync_at=synced, consecutive_failures=0, updated_at=synced))
