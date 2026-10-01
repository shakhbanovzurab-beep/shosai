"""Дела (хабы) «руководителя»: доски трекера, хабы, история фактов Acme, материалы.

Встречи Acme — уже засеянные: «без названия» (начало внедрения), «Демо для
клиента Acme» и «Планирование бюджета Q4». Новых встреч засев не заводит:
бегущая строка считает все встречи базы, и новые сдвинули бы её на каждом экране.

Факты разложены так, чтобы пульс дела показал каждый вид петли: решение
изменилось (противоречие), просрочено, просрочено после отклонения, «круг 3»,
скоро срок, вопрос без ответа. Учёт показа (`raised_at`) засеян моментом стенда:
иначе первый же GET пульса записал бы показ, и петли пошли бы на второй круг.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from meetassist.features.context_graph.contracts.dto import FactKind
from meetassist.features.context_graph.domain.facts import dedup_key
from meetassist.features.context_graph.domain.resolution import norm_key
from meetassist.features.context_graph.infrastructure.models import PcgEntity, PcgFact
from meetassist.features.hub.infrastructure.models import Hub, HubMaterial, HubMeeting
from meetassist.models.session import Session
from meetassist.models.storage import StorageFile
from meetassist.models.tracker import TrackerProject, TrackerStatus
from meetassist.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession

from stable_ids import HUBS, KNOWLEDGE_DOCUMENT

_STATUSES = (("To Do", "todo", "#94A3B8"), ("In Progress", "in_progress", "#3B82F6"), ("Done", "done", "#22C55E"))


@dataclass(frozen=True)
class _Fact:
    key: str
    meeting: str
    kind: str
    subject: str
    text: str
    due: datetime | None = None


def _at(day: int, hour: int = 9) -> datetime:
    return datetime(2026, 7, day, hour, tzinfo=UTC)


#: История Acme: встреча засева, вид, тема, текст, срок.
_FACTS = (
    _Fact("a", "untitled", "decision", "Миграция данных", "Миграцию делаем одним окном за выходные"),
    _Fact("b", "untitled", "commitment", "Миграция данных", "Подготовим скрипт миграции одним пакетом", _at(31)),
    _Fact("c", "untitled", "decision", "Обучение", "Обучаем всех 40 пользователей до запуска"),
    _Fact("d", "untitled", "commitment", "Доступ к API", "Откроем тестовый доступ к API", _at(15)),
    _Fact("r", "untitled", "risk", "SSO", "Если ИБ не согласует SSO до августа, запуск сдвинется"),
    _Fact("e", "demo", "decision", "Миграция данных", "Миграцию делаем поэтапно, по отделам"),
    _Fact("f", "demo", "commitment", "Миграция данных", "Перепишем план миграции по отделам", _at(31)),
    _Fact("g", "demo", "decision", "SSO", "Вход только через SSO (Azure AD)"),
    _Fact("h", "demo", "commitment", "SSO", "Пришлём SAML-метаданные", _at(13)),
    _Fact("i", "demo", "commitment", "NDA", "Согласуем с юристами форму NDA", _at(10)),
    _Fact("j", "demo", "question", "Приёмка", "Кто подписывает акт приёмки?"),
    _Fact("k", "demo", "commitment", "Бюджет пилота", "Пришлём смету до 15 июля", _at(15)),
    _Fact("l", "budget", "decision", "Бюджет пилота", "Бюджет пилота утверждён: 1,2 млн ₽"),
    _Fact("m", "budget", "commitment", "Бюджет пилота", "Пришлём обновлённую смету", _at(28)),
    _Fact("n", "budget", "commitment", "Обучение", "Пришлём программу обучения администраторов", _at(21, 12)),
    _Fact("o", "budget", "risk", "Бюджет пилота", "Закупка лицензий может уехать на следующий квартал"),
    _Fact("p", "budget", "problem", "Бюджет пилота", "Текущий тариф не покрывает 40 мест"),
    _Fact("q", "budget", "question", "Обучение", "Нужен ли отдельный стенд для обучения?"),
)

#: Петли, которые пульс уже показывал; «d» — третий раз.
_RAISED = {"b": 0, "d": 2, "h": 0, "i": 0, "j": 0, "n": 0}


async def seed_hubs(db: AsyncSession, owner: User, clock: datetime, sessions: dict[str, Session]) -> None:
    """Засевает дела владельца и всё, что дело показывает."""
    boards = await _boards(db, owner, clock)
    acme = Hub(id=HUBS["acme"], user_id=owner.id, name="Acme", kind="client", tracker_project_id=boards["ACME"],
               purpose="Внедрение Whisperer в отделе продаж Acme",
               success="40 сотрудников Acme ежедневно работают в системе две недели подряд",
               created_at=clock - timedelta(days=45))
    wind = Hub(id=HUBS["wind"], user_id=owner.id, name="Северный ветер", kind="internal",
               purpose="Портал для партнёров", created_at=clock - timedelta(days=40))
    archived = Hub(id=HUBS["archived"], user_id=owner.id, name="Ромашка (пилот 2025)", kind="client",
                   tracker_project_id=boards["PORTAL"], archived=True, created_at=datetime(2026, 3, 1, tzinfo=UTC))
    db.add_all([acme, wind, archived])
    await db.flush()
    for hub, meeting in ((acme, "budget"), (acme, "demo"), (acme, "untitled"), (wind, "kickoff")):
        db.add(HubMeeting(user_id=owner.id, hub_id=hub.id, session_id=sessions[meeting].id, primary=True,
                          addressed_by="human", confidence=1.0, created_at=sessions[meeting].ended_at))
    # «Синку» черновик подскажет «Acme»: факт из его стенограммы называет клиента по имени.
    sync = sessions["sync"]
    db.add(PcgFact(user_id=owner.id, kind="commitment", text="Исправить экспорт отчётов для Acme до среды",
                   dedup_key="parity:acme-export", status="detected", confidence=0.8, source_kind="meeting",
                   source_id=str(sync.id), extracted_by="leo", created_at=sync.ended_at))
    await _facts(db, owner, clock, sessions)
    await _materials(db, owner, acme, clock, sessions)


async def _boards(db: AsyncSession, owner: User, clock: datetime) -> dict[str, uuid.UUID]:
    boards: dict[str, uuid.UUID] = {}
    for position, (key, name) in enumerate((("ACME", "Внедрение Acme"), ("PORTAL", "Портал"))):
        project = TrackerProject(user_id=owner.id, name=name, key=key, position=position,
                                 created_at=clock - timedelta(days=50 - position))
        db.add(project)
        await db.flush()
        for order, (status, category, color) in enumerate(_STATUSES):
            db.add(TrackerStatus(project_id=project.id, name=status, category=category, color=color, position=order))
        boards[key] = project.id
    return boards


async def _facts(db: AsyncSession, owner: User, clock: datetime, sessions: dict[str, Session]) -> None:
    topics: dict[str, PcgEntity] = {}
    for fact in _FACTS:
        if fact.subject not in topics:
            topics[fact.subject] = PcgEntity(user_id=owner.id, kind="topic", name=fact.subject,
                                             norm_key=norm_key(fact.subject), confidence=0.8, source_kind="meeting",
                                             source_id=str(sessions[fact.meeting].id))
    db.add_all(topics.values())
    await db.flush()
    rows: dict[str, PcgFact] = {}
    for index, fact in enumerate(_FACTS):
        stated = sessions[fact.meeting].started_at
        row = PcgFact(user_id=owner.id, kind=fact.kind, text=fact.text, dedup_key=dedup_key(FactKind(fact.kind), fact.text),
                      status="detected", confidence=0.8, due_at=fact.due, source_kind="meeting",
                      source_id=str(sessions[fact.meeting].id), extracted_by="leo",
                      subject_entity_id=topics[fact.subject].id, valid_from=stated,
                      created_at=stated + timedelta(seconds=index))
        if fact.key in _RAISED:
            row.raised_at = clock
            row.raised_count = _RAISED[fact.key]
            row.raised_as = "overdue" if fact.key == "d" else None
        rows[fact.key] = row
    # Отклонённая человеком петля, у которой срок отклонения уже вышел.
    rows["i"].refuted_reason = "human"
    rows["i"].refuted_evidence = "человек отклонил 2026-07-10"
    rows["i"].refuted_as = "overdue"
    rows["i"].refuted_until = _at(15, 0)
    rows["k"].status = "cancelled"
    rows["k"].resolved_at = sessions["budget"].started_at
    db.add_all(rows.values())
    await db.flush()
    # Решение «одним окном» вытеснено поэтапным, смета до 15 июля — обновлённой.
    rows["a"].superseded_by_id = rows["e"].id
    rows["k"].superseded_by_id = rows["m"].id
    await db.flush()


async def _materials(db: AsyncSession, owner: User, hub: Hub, clock: datetime, sessions: dict[str, Session]) -> None:
    estimate = StorageFile(owner_id=owner.id, name="Смета_пилота_Acme_v2.xlsx", s3_key="parity/smeta-acme-v2.xlsx",
                           size=48_128, mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           created_at=_at(15, 10))
    db.add(estimate)
    await db.flush()
    db.add_all([
        HubMaterial(user_id=owner.id, hub_id=hub.id, kind="document", ref_id=str(KNOWLEDGE_DOCUMENT),
                    title="Итоги: бюджет пилота Acme", session_id=sessions["budget"].id,
                    created_at=clock - timedelta(hours=1)),
        HubMaterial(user_id=owner.id, hub_id=hub.id, kind="file", ref_id=str(estimate.id),
                    title="Смета_пилота_Acme_v2.xlsx", created_at=_at(15, 10)),
    ])
    await db.flush()
