"""Вкладка Leo кабинета «руководителя»: персонализация, сервисы, инициатива, память, поручения.

Память черновик показывает с «удержанием», которое считает по часам сервера от
`last_used_at`. API работает под libfaketime от момента стенда, поэтому моменты
заданы от него же; одна запись давно не вспоминалась — её удержание ниже порога,
и экран помечает её «забыто».

Поручения — без `workflow_id`: отмена тогда не идёт в движок поручений, которого
на стенде нет.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta

from meetassist.features.connectors.infrastructure.models import ConnectorConnection
from meetassist.features.errands.infrastructure.models import Errand
from meetassist.features.memory.infrastructure.models import MemoryItem
from meetassist.features.personalization.infrastructure.models import LeoPersonalization
from meetassist.features.proactive.infrastructure.models import (
    ProactiveMailWatch,
    ProactivePushSubscription,
    ProactiveSetting,
)
from meetassist.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession

#: Размерность вектора памяти черновика; содержимое вектора экран не читает.
_EMBEDDING_SIZE = 384

#: Память: вид, важность, подтверждения, дней с последнего обращения, текст.
_MEMORY = (
    ("fact", 0.9, 3, 2, "Руководит продуктовым направлением в финтех-компании."),
    ("fact", 0.5, 0, 10, "Ключевой клиент — Acme: запуск на платформе к 1 сентября."),
    ("fact", 0.5, 1, 30, "Цифры просит показывать таблицей, сроки — датами."),
    ("procedure", 0.5, 1, 20, "Перед встречей с клиентом просит сводку прошлых договорённостей."),
    ("episode", 0.3, 0, 5, "Обсуждали сокращение офлайн-ивентов на 30 %."),
    ("episode", 0.0, 0, 90, "Спрашивал про шаблон квартального отчёта."),
)

#: Поручения: вид, статус, сдвиг срока в часах от момента стенда, сводка, ошибка.
_ERRANDS = (
    ("remind", "scheduled", 3, "Напомнить: созвон с Acme в 16:00", None),
    ("remind", "scheduled", 48, "Напомнить: отправить обновлённую смету пилота", None),
    ("remind", "done", -24, "Напомнить: подготовить повестку ретро", None),
    ("send_email", "failed", -3, "Письмо Ивану Петрову: итоги бюджета Q4", "Gmail отклонил отправку: доступ истёк"),
    ("remind", "cancelled", -120, "Напомнить: продлить домен", None),
)


async def seed_leo_cabinet(db: AsyncSession, owner: User, clock: datetime) -> None:
    """Засевает вкладку Leo владельца."""
    db.add(LeoPersonalization(user_id=owner.id, occupation="Руководитель продукта в финтехе", style="friendly",
                              warmth="more", enthusiasm="default", structure="more", emoji="less",
                              instructions="Сначала вывод, потом детали. Цифры — таблицей, сроки — датами.",
                              created_at=clock - timedelta(days=30)))
    # Почта подключена, Slack потерял доступ. Остальные карточки каталога черновик
    # показывает по ключам провайдеров в окружении; на стенде их нет.
    db.add_all([
        ConnectorConnection(user_id=owner.id, provider_config_key="google-mail", connection_id="parity-gmail",
                            broken=False, connected_at=clock - timedelta(days=12)),
        ConnectorConnection(user_id=owner.id, provider_config_key="slack", connection_id="parity-slack",
                            broken=True, connected_at=clock - timedelta(days=40)),
    ])
    db.add(ProactiveSetting(user_id=owner.id, level="reserved", muted_kinds=["hub_looping"], channels=["in_app"],
                            quiet_from=time(22, 0), quiet_to=time(8, 0), quiet_enabled=True,
                            notification_preview=True))
    db.add_all([
        ProactiveMailWatch(user_id=owner.id, email="olga.kim@example.com", label="тимлид",
                           created_at=clock - timedelta(days=2)),
        ProactiveMailWatch(user_id=owner.id, email="ivan.petrov@acme.example", label="клиент",
                           created_at=clock - timedelta(days=9)),
    ])
    db.add(ProactivePushSubscription(user_id=owner.id, endpoint="https://fcm.googleapis.com/fcm/send/parity-device",
                                     p256dh="parity-p256dh", auth="parity-auth", label="Chrome · macOS",
                                     last_push_at=clock - timedelta(days=1), created_at=clock - timedelta(days=14)))
    _memory(db, owner, clock)
    _errands(db, owner, clock)
    await db.flush()


def _memory(db: AsyncSession, owner: User, clock: datetime) -> None:
    vector = [1.0] + [0.0] * (_EMBEDDING_SIZE - 1)
    for kind, importance, confirmations, days, text in _MEMORY:
        used = clock - timedelta(days=days)
        db.add(MemoryItem(user_id=owner.id, kind=kind, scope="agent", text=text, embedding=vector,
                          importance=importance, confirmations=confirmations, last_used_at=used,
                          created_at=used - timedelta(days=1)))


def _errands(db: AsyncSession, owner: User, clock: datetime) -> None:
    for index, (kind, status, hours, summary, error) in enumerate(_ERRANDS):
        run_at = clock + timedelta(hours=hours)
        payload = (
            {"to": "ivan.petrov@acme.example", "subject": "Итоги бюджета Q4", "body": "Бюджет утверждён."}
            if kind == "send_email"
            else {"text": summary}
        )
        db.add(Errand(user_id=owner.id, kind=kind, status=status, run_at=run_at, summary=summary, payload=payload,
                      workflow_id=None, error=error, finished_at=_finished_at(status, run_at, clock),
                      created_at=clock - timedelta(days=7, hours=index)))


def _finished_at(status: str, run_at: datetime, clock: datetime) -> datetime | None:
    """Выполненное и сорвавшееся завершились в свой срок, отменённое — за день до срока."""
    if status in ("done", "failed"):
        return run_at
    if status == "cancelled":
        return clock - timedelta(days=6)
    return None
