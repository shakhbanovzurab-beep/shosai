"""Memory's tables in each home (memory plan §3.6, ADR 0071).

Every table is personal by nature: row-level security admits the person's own rows only
(ADR 0053). A fact keeps its vector beside it, `halfvec(1024)` stored inline (`PLAIN`), so a
fact and its vector change in one transaction and recall reads no TOAST (ADR 0033). Recall
scans the person's own current facts exactly, through a b-tree on the person: no HNSW, whose
graph filtered to one person loses results (MM-D6). PostgreSQL keeps every closed set, the
statement's length and the rules that tie a fact's columns together.
"""

from datetime import datetime
from typing import Final
from uuid import UUID

from pgvector.sqlalchemy import HALFVEC
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Double,
    Index,
    Integer,
    Text,
    Uuid,
    false,
    func,
    text,
    true,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from shosai.core.db.model_base import ModelBase
from shosai.features.memory.domain.facts import (
    STATEMENT_MAX,
    EndReason,
    FactKind,
    FactStatus,
    MemorySource,
    Sensitivity,
)

EMBEDDING_DIMENSIONS: Final = 1_024
TAINTS: Final = ("none", "external")


KINDS: Final = ", ".join(f"'{kind}'" for kind in FactKind)
SOURCES: Final = ", ".join(f"'{source}'" for source in MemorySource)
STATUSES: Final = ", ".join(f"'{status}'" for status in FactStatus)
REASONS: Final = ", ".join(f"'{reason}'" for reason in EndReason)
SENSITIVITIES: Final = ", ".join(f"'{level}'" for level in Sensitivity)
SOURCE_TAINTS: Final = ", ".join(f"'{taint}'" for taint in TAINTS)
CURRENT: Final = text("status = 'active' AND valid_to IS NULL")
PENDING: Final = text("status = 'candidate' AND valid_to IS NULL")


class MemoryFactRecord(ModelBase):
    """A fact Leo remembers about a person, a candidate, or an ended one kept for history."""

    __tablename__ = "memory_facts"
    __table_args__ = (
        CheckConstraint(f"kind IN ({KINDS})", name="kind_known"),
        CheckConstraint(f"source_kind IN ({SOURCES})", name="source_known"),
        CheckConstraint(f"status IN ({STATUSES})", name="status_known"),
        CheckConstraint(f"sensitivity IN ({SENSITIVITIES})", name="sensitivity_known"),
        CheckConstraint(f"source_taint IN ({SOURCE_TAINTS})", name="source_taint_known"),
        CheckConstraint(
            f"ended_reason IS NULL OR ended_reason IN ({REASONS})", name="ended_reason_known"
        ),
        CheckConstraint(
            f"char_length(statement) BETWEEN 1 AND {STATEMENT_MAX}", name="statement_length"
        ),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="confidence_range"),
        CheckConstraint("confirmations >= 0", name="confirmations_counted"),
        CheckConstraint("NOT pinned OR status = 'active'", name="pinned_when_active"),
        CheckConstraint(
            "(status = 'forgotten') = (ended_reason IS NOT NULL AND ended_at IS NOT NULL)",
            name="ended_when_forgotten",
        ),
        CheckConstraint("superseded_by IS NULL OR valid_to IS NOT NULL", name="superseded_closed"),
        CheckConstraint(
            "(embedding IS NULL) = (embedding_model IS NULL)", name="embedding_with_model"
        ),
        Index("ix_memory_facts_current", "user_id", postgresql_where=CURRENT),
        Index("ix_memory_facts_listing", "user_id", "status", "created_at", "id"),
        Index("ix_memory_facts_thread_pending", "thread_id", postgresql_where=PENDING),
        Index(
            "ix_memory_facts_erase_after",
            "erase_after",
            postgresql_where=text("erase_after IS NOT NULL"),
        ),
        Index(
            "ix_memory_facts_forgotten", "ended_at", postgresql_where=text("status = 'forgotten'")
        ),
        Index(
            "ix_memory_facts_superseded", "valid_to", postgresql_where=text("valid_to IS NOT NULL")
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(Uuid)
    # Пространство источника: факт живёт, пока человек в нём (MM-D4).
    org_id: Mapped[UUID | None] = mapped_column(Uuid)
    kind: Mapped[str] = mapped_column(Text)
    statement: Mapped[str] = mapped_column(Text)
    subject_refs: Mapped[list[UUID]] = mapped_column(
        ARRAY(Uuid), server_default=text("'{}'::uuid[]")
    )
    source_kind: Mapped[str] = mapped_column(Text)
    # Идентификаторы источника: тред и сообщение, встреча и находка или чат и сообщение.
    source_ref: Mapped[dict[str, str]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    thread_id: Mapped[UUID | None] = mapped_column(Uuid)
    confidence: Mapped[float] = mapped_column(Double, server_default=text("1"))
    sensitivity: Mapped[str] = mapped_column(Text, server_default="normal")
    explicit: Mapped[bool] = mapped_column(Boolean, server_default=false())
    confirmed: Mapped[bool] = mapped_column(Boolean, server_default=false())
    source_taint: Mapped[str] = mapped_column(Text, server_default="none")
    status: Mapped[str] = mapped_column(Text)
    ended_reason: Mapped[str | None] = mapped_column(Text)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    superseded_by: Mapped[UUID | None] = mapped_column(Uuid)
    # Предшественник, которого кандидат предлагает заменить по ответу политики.
    replaces: Mapped[UUID | None] = mapped_column(Uuid)
    pinned: Mapped[bool] = mapped_column(Boolean, server_default=false())
    confirmations: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    last_confirmed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    embedding: Mapped[list[float] | None] = mapped_column(HALFVEC(EMBEDDING_DIMENSIONS))
    embedding_model: Mapped[str | None] = mapped_column(Text)
    erase_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MemorySettingsRecord(ModelBase):
    """A person's memory switch; absent while it stays on."""

    __tablename__ = "memory_settings"

    user_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, server_default=true())
    # Когда переключатель сменился: монитор ищет факты, записанные после выключения.
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MemorySummaryRecord(ModelBase):
    """The overview of a person's memory, as last written and checked."""

    __tablename__ = "memory_summaries"
    __table_args__ = (
        CheckConstraint("char_length(language) BETWEEN 2 AND 10", name="language_length"),
        CheckConstraint("jsonb_typeof(sections) = 'array'", name="sections_list"),
        CheckConstraint("jsonb_typeof(suggestions) = 'array'", name="suggestions_list"),
    )

    user_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    sections: Mapped[list[dict[str, str]]] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb")
    )
    suggestions: Mapped[list[str]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    language: Mapped[str] = mapped_column(Text)
    # Отпечаток текущих фактов, из которых написана сводка.
    facts_digest: Mapped[str] = mapped_column(Text, server_default="")
    written_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    stale: Mapped[bool] = mapped_column(Boolean, server_default=false())


MEMORY_MODELS: Final[tuple[type[ModelBase], ...]] = (
    MemoryFactRecord,
    MemorySettingsRecord,
    MemorySummaryRecord,
)
