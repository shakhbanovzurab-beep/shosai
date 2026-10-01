"""Трекер «руководителя»: доски, колонки, задачи, метки и связи с Jira.

Доски нужны и делам (хаб отправляет работу на доску), поэтому они засеваются
первыми. У доски Acme есть пустая колонка «На проверке» — экран пустой колонки.

У задачи не больше одной метки: метки задачи черновик читает без сортировки, и
порядок двух меток мог бы меняться от записи к записи. Сроки — 09:00 UTC, чтобы
дата по Москве не сдвигалась.

Jira: одна учётная запись Atlassian без токенов и две связи — живая на Acme и
сбойная на «Портале». Статус связи черновик отдаёт из базы, без сети.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from meetassist.features.jira.infrastructure.models import JiraLink
from meetassist.models.oauth_account import OAuthAccount
from meetassist.models.tracker import TrackerLabel, TrackerProject, TrackerStatus, TrackerTask, tracker_task_labels
from meetassist.models.user import User
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from stable_ids import BOARDS

#: Колонки досок: название, категория, цвет.
_COLUMNS: dict[str, tuple[tuple[str, str, str], ...]] = {
    "ACME": (("To Do", "todo", "#94A3B8"), ("In Progress", "in_progress", "#3B82F6"),
             ("На проверке", "in_progress", "#A855F7"), ("Done", "done", "#22C55E")),
    "PORTAL": (("To Do", "todo", "#94A3B8"), ("In Progress", "in_progress", "#3B82F6"), ("Done", "done", "#22C55E")),
}
_BOARDS = (("ACME", "Внедрение Acme", "Запуск Acme на платформе к 1 сентября"), ("PORTAL", "Портал", None))
_LABELS = (("Интеграция", "#8B5CF6"), ("Обучение", "#F59E0B"), ("Финансы", "#22C55E"), ("Безопасность", "#EF4444"))


@dataclass(frozen=True)
class _Task:
    column: str
    title: str
    priority: str
    label: str | None = None
    due_day: int | None = None
    description: str | None = None


#: Задачи доски Acme; день срока — июль 2026.
_TASKS = (
    _Task("To Do", "Открыть тестовый доступ к API", "urgent", "Интеграция", 14, "Ключи и песочница для команды Acme"),
    _Task("To Do", "Подготовить скрипт миграции по отделам", "high", None, 31),
    _Task("To Do", "Собрать требования к SSO", "medium"),
    _Task("In Progress", "Настроить вход через Azure AD", "high", "Безопасность", 24),
    _Task("In Progress", "Программа обучения администраторов", "medium", "Обучение", 21),
    _Task("In Progress", "Обновить смету пилота", "low", "Финансы", 28),
    _Task("Done", "Согласовать бюджет пилота", "medium", "Финансы"),
    _Task("Done", "Подписать NDA", "high"),
    _Task("Done", "Кик-офф с командой Acme", "low"),
    _Task("Done", "Демо для клиента", "medium", "Обучение"),
)


async def seed_boards(db: AsyncSession, owner: User, clock: datetime) -> dict[str, dict[str, uuid.UUID]]:
    """Доски и колонки владельца; возвращает id колонок по доске и названию (`""` — сама доска)."""
    boards: dict[str, dict[str, uuid.UUID]] = {}
    for position, (key, name, description) in enumerate(_BOARDS):
        project = TrackerProject(id=BOARDS[key], user_id=owner.id, name=name, key=key, description=description,
                                 position=position,
                                 created_at=clock - timedelta(days=50 - position))
        db.add(project)
        await db.flush()
        boards[key] = {"": project.id}
        for order, (status, category, color) in enumerate(_COLUMNS[key]):
            column = TrackerStatus(project_id=project.id, name=status, category=category, color=color, position=order,
                                   created_at=clock - timedelta(days=50 - position, minutes=-order))
            db.add(column)
            await db.flush()
            boards[key][status] = column.id
    return boards


async def seed_tracker(db: AsyncSession, owner: User, clock: datetime, boards: dict[str, dict[str, uuid.UUID]]) -> None:
    """Задачи и метки доски Acme и связи досок с Jira."""
    acme = boards["ACME"]
    labels: dict[str, uuid.UUID] = {}
    for index, (name, color) in enumerate(_LABELS):
        label = TrackerLabel(project_id=acme[""], name=name, color=color, created_at=clock - timedelta(days=40, minutes=-index))
        db.add(label)
        await db.flush()
        labels[name] = label.id
    positions: dict[str, int] = {}
    links: list[dict[str, uuid.UUID]] = []
    for index, task in enumerate(_TASKS):
        position = positions.get(task.column, 0)
        positions[task.column] = position + 1
        row = TrackerTask(project_id=acme[""], status_id=acme[task.column], title=task.title, description=task.description,
                          priority=task.priority, position=position,
                          due_at=None if task.due_day is None else datetime(2026, 7, task.due_day, 9, tzinfo=UTC),
                          created_at=clock - timedelta(days=30, minutes=-index))
        db.add(row)
        await db.flush()
        if task.label is not None:
            links.append({"task_id": row.id, "label_id": labels[task.label]})
    await db.execute(insert(tracker_task_labels), links)
    await _jira(db, owner, clock, boards)


async def _jira(db: AsyncSession, owner: User, clock: datetime, boards: dict[str, dict[str, uuid.UUID]]) -> None:
    account = OAuthAccount(user_id=owner.id, provider="jira", external_account_id="parity-atlassian-account",
                           display_name="Мария Соколова", access_token_enc=None, refresh_token_enc=None, expires_at=None,
                           scopes=[], status="active", personal_data_retrieved_at=clock - timedelta(days=14),
                           provider_metadata={"sites": [{"cloud_id": "parity-cloud", "name": "acme",
                                                         "url": "https://acme.atlassian.net"}]},
                           created_at=clock - timedelta(days=14))
    db.add(account)
    await db.flush()
    db.add_all([
        JiraLink(user_id=owner.id, oauth_account_id=account.id, tracker_project_id=boards["ACME"][""],
                 cloud_id="parity-cloud", jira_project_id="10000", jira_project_key="ACME",
                 jira_project_name="Acme Implementation", webhook_id="1", webhook_expires_at=clock + timedelta(days=20),
                 synced_through=clock - timedelta(hours=2), last_sync_at=clock - timedelta(hours=2),
                 created_at=clock - timedelta(days=14)),
        JiraLink(user_id=owner.id, oauth_account_id=account.id, tracker_project_id=boards["PORTAL"][""],
                 cloud_id="parity-cloud", jira_project_id="10001", jira_project_key="PORT",
                 jira_project_name="Partner Portal", webhook_id=None, last_sync_at=clock - timedelta(days=3),
                 last_error="503: Service Unavailable", consecutive_failures=3,
                 backoff_until=clock - timedelta(hours=1), created_at=clock - timedelta(days=13)),
    ])
    await db.flush()
