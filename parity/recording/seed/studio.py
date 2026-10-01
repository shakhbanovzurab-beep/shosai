"""Контекст и база знаний «руководителя».

Квота базы знаний — лимит тарифа Pro (50 МиБ); занято 20 МиБ, то есть 40 %.
Размеры документов, включая пришедшие из источника, в сумме дают занятое место:
ежедневная сверка черновика пересчитывает его по документам. Пять документов
называются «Бюджет…»: поиск по «бюджет» тогда находит их по имени и не идёт в
векторный индекс, которого на стенде нет (иначе — «База знаний не ответила»).
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta

from meetassist.features.knowledge.infrastructure.models import KnowledgeDocument, KnowledgeSource, KnowledgeSpace
from meetassist.models.user import User
from meetassist.models.user_context import UserContext
from meetassist.models.user_context_file import UserContextFile
from sqlalchemy.ext.asyncio import AsyncSession

from stable_ids import KNOWLEDGE_DOCUMENT

MIB = 1024 * 1024

_CONTEXT = """Я руководитель продуктового направления в финтех-компании, отвечаю за партнёрский портал и продажи крупным клиентам.

Отвечай коротко и по делу, на «ты». Цифры показывай таблицей, сроки — датами.

Сейчас в фокусе: бюджет на четвёртый квартал, проект «Северный ветер» и внедрение у клиента Acme. Ключевые люди: Иван Петров (финансы), Ольга Ким (маркетинг), Дмитрий Орлов (разработка).

Не предлагай решения, которые увеличивают расходы на офлайн-ивенты: мы их сокращаем. Если вопрос касается договоров, напомни согласовать с юристом."""

#: Файлы контекста: путь (со вложенными папками), MIME, размер.
_CONTEXT_FILES = (
    ("profile.md", "text/markdown", 2_100),
    ("projects/q4/budget-plan.md", "text/markdown", 5_400),
    ("projects/q4/notes/risks.txt", "text/plain", 1_800),
    ("docs/api/spec.yaml", "application/yaml", 9_300),
)

#: Загруженные документы: имя, МиБ, MIME, статус, дней назад.
_DOCUMENTS = (
    ("Бюджет 2026.xlsx", 3, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "indexed", 1),
    ("Бюджет маркетинга Q3.pdf", 2, "application/pdf", "indexed", 3),
    ("Бюджет найма.xlsx", 1, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "indexed", 5),
    ("Исполнение бюджета H1.pdf", 2, "application/pdf", "pending", 0),
    ("Бюджетный регламент.docx", 1, "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
     "indexed", 12),
    ("Договор аренды.pdf", 3, "application/pdf", "indexed", 20),
    ("Скан паспорта.png", 2, "image/png", "failed", 25),
)

#: Подключённые источники: вид, имя, статус, настройки, последняя ошибка.
_SOURCES = (
    ("obsidian", "Рабочий vault", "active", {}, None),
    ("web", "Документация", "paused", {"base_url": "https://docs.example.com"}, None),
    ("notion", "Notion — команда", "error", {}, "401 Unauthorized: token expired"),
    ("confluence", "Confluence ENG", "quarantined", {}, "topology mismatch: registry 42 vs index 40"),
)

#: Документ из активного источника: добирает занятое место до 20 МиБ.
_SOURCE_DOCUMENT_MIB = 6


async def seed_studio(db: AsyncSession, owner: User, clock: datetime) -> None:
    """Засевает контекст о себе и базу знаний владельца."""
    context = UserContext(user_id=owner.id, text=_CONTEXT, roles=["responses", "agent"],
                          updated_at=clock - timedelta(days=2))
    db.add(context)
    await db.flush()
    for index, (path, mime, size) in enumerate(_CONTEXT_FILES):
        db.add(UserContextFile(user_context_id=context.id, filename=path, mime_type=mime, size_bytes=size,
                               storage_path=f"/parity/context/{path}", extracted_text=f"{path}: бюджет и планы",
                               created_at=clock - timedelta(days=10 - index)))
    documents_mib = sum(size for _, size, _, _, _ in _DOCUMENTS)
    db.add(KnowledgeSpace(user_id=owner.id, used_bytes=(documents_mib + _SOURCE_DOCUMENT_MIB) * MIB,
                          provisioned_at=clock - timedelta(days=60)))
    for index, (name, size, mime, status, days) in enumerate(_DOCUMENTS):
        created = clock - timedelta(days=days, hours=index)
        # Первый документ — со стабильным id: визит подсвечивает его по ссылке.
        stable = {"id": KNOWLEDGE_DOCUMENT} if index == 0 else {}
        db.add(
            KnowledgeDocument(
                **stable,
                user_id=owner.id,
                source_id=None,
                name=name,
                size_bytes=size * MIB,
                mime_type=mime,
                status=status,
                content_sha256=hashlib.sha256(name.encode()).hexdigest(),
                indexed_at=created + timedelta(minutes=4) if status == "indexed" else None,
                last_error="ocr_not_configured" if status == "failed" else None,
                created_at=created,
            )
        )
    await db.flush()
    await _sources(db, owner, clock)


async def _sources(db: AsyncSession, owner: User, clock: datetime) -> None:
    first: KnowledgeSource | None = None
    for index, (kind, name, status, config, error) in enumerate(_SOURCES):
        source = KnowledgeSource(user_id=owner.id, kind=kind, display_name=name, status=status, config=config,
                                 last_indexed_at=clock - timedelta(hours=3 + index) if status in ("active", "paused")
                                 else None,
                                 last_error=error, created_at=clock - timedelta(days=30 - index))
        db.add(source)
        await db.flush()
        first = first or source
    if first is None:
        raise RuntimeError("засев источников пуст")
    db.add(KnowledgeDocument(user_id=owner.id, source_id=first.id, external_path="Проекты/План.md",
                             name="План.md", size_bytes=_SOURCE_DOCUMENT_MIB * MIB, mime_type="text/markdown",
                             status="indexed", indexed_at=clock - timedelta(hours=3), created_at=clock - timedelta(days=29)))
