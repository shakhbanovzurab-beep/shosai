"""Leo's runs and actions, and the audit of what the actions did (agent plan §3.4, Leo §8.4, §10).

A run's row is its telemetry and its status: ids, numbers and codes only, in monthly
partitions kept four months. An action keeps its planned items until 30 days after it ends;
every change of its status is one conditional update, so the row is where approvals race and
exactly one wins. The audit is append-only — the application may insert and read, never
change — and keeps ids, tool names and codes for 12 months.
"""

from datetime import datetime
from typing import Any, Final
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    PrimaryKeyConstraint,
    SmallInteger,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy import text as sql_text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from shosai.core.db.model_base import ModelBase
from shosai.core.db.partitions.policy import monthly_partition_range
from shosai.features.agent.domain.actions import AuditEvent

RUN_STATUSES: Final = "'running', 'paused', 'completed', 'failed', 'cancelled'"
CHANNELS: Final = "'web', 'admin'"
ACTION_STATUSES: Final = (
    "'proposed', 'approved', 'executing', 'succeeded', 'partially_succeeded', 'failed', "
    "'outcome_unknown', 'rejected', 'expired', 'superseded'"
)
ORIGINS: Final = "'turn', 'proposal_port'"
VIAS: Final = "'web', 'inbox'"
AUDIT_EVENTS: Final = ", ".join(f"'{event.value}'" for event in AuditEvent)
CODE_FORM: Final = "~ '^[a-z0-9_.:-]{1,64}$'"


class AgentRunRecord(ModelBase):
    """One run of Leo: its status, the model and what it cost, as numbers and codes."""

    __tablename__ = "agent_runs"
    __table_args__ = (
        PrimaryKeyConstraint("id", "started_at", name="pk_agent_runs"),
        CheckConstraint(f"status IN ({RUN_STATUSES})", name="status_known"),
        CheckConstraint(f"channel IN ({CHANNELS})", name="channel_known"),
        CheckConstraint(
            f"outcome_code IS NULL OR outcome_code {CODE_FORM}", name="outcome_code_form"
        ),
        CheckConstraint(
            "(status IN ('running', 'paused')) = (ended_at IS NULL)", name="ended_when_over"
        ),
        CheckConstraint(
            "language IS NULL OR language ~ '^[a-z]{2,3}(-[A-Za-z]{2,4})?$'", name="language_form"
        ),
        Index("ix_agent_runs_thread", "thread_id", sql_text("started_at DESC")),
        Index(
            "ix_agent_runs_live",
            "status",
            "started_at",
            postgresql_where=sql_text("status IN ('running', 'paused')"),
        ),
        {"postgresql_partition_by": monthly_partition_range("started_at")},
    )

    id: Mapped[UUID] = mapped_column(Uuid)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    thread_id: Mapped[UUID] = mapped_column(Uuid)
    user_id: Mapped[UUID] = mapped_column(Uuid)
    channel: Mapped[str] = mapped_column(Text)
    # Язык ответа, выбранный при старте хода: оценочный случай хранит его.
    language: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="running")
    outcome_code: Mapped[str | None] = mapped_column(Text)
    model: Mapped[str | None] = mapped_column(Text)
    tier: Mapped[str | None] = mapped_column(Text)
    token_route: Mapped[str | None] = mapped_column(Text)
    rounds: Mapped[int] = mapped_column(SmallInteger, server_default="0")
    tool_calls: Mapped[int] = mapped_column(SmallInteger, server_default="0")
    input_tokens: Mapped[int] = mapped_column(Integer, server_default="0")
    cached_tokens: Mapped[int] = mapped_column(Integer, server_default="0")
    output_tokens: Mapped[int] = mapped_column(Integer, server_default="0")
    cost_micro_usd: Mapped[int] = mapped_column(BigInteger, server_default="0")
    ttft_ms: Mapped[int | None] = mapped_column(Integer)
    overhead_ms: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    # Какие наборы инструментов выбраны и каким правилом (AG-D7): имена и код правила.
    routing: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=sql_text("'{}'::jsonb"))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgentActionRecord(ModelBase):
    """A write Leo proposed: its planned items, its status, and who decided when."""

    __tablename__ = "agent_actions"
    __table_args__ = (
        CheckConstraint(f"status IN ({ACTION_STATUSES})", name="status_known"),
        CheckConstraint(f"origin IN ({ORIGINS})", name="origin_known"),
        CheckConstraint("approved_via IS NULL OR approved_via IN (" + VIAS + ")", name="via_known"),
        CheckConstraint("friction BETWEEN 0 AND 2 AND taint BETWEEN 0 AND 2", name="levels"),
        CheckConstraint("jsonb_array_length(items) BETWEEN 1 AND 20", name="items_count"),
        CheckConstraint(
            "(status IN ('proposed', 'approved', 'executing')) = (resolved_at IS NULL)",
            name="resolved_when_over",
        ),
        UniqueConstraint("user_id", "origin", "origin_key", name="uq_agent_actions_origin_key"),
        Index(
            "ix_agent_actions_pending",
            "user_id",
            sql_text("created_at DESC"),
            postgresql_where=sql_text("status = 'proposed'"),
        ),
        Index("ix_agent_actions_due", "status", "expires_at"),
        Index("ix_agent_actions_resolved", "resolved_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(Uuid)
    # Пространство, куда пишет действие: для карточки; None — личное.
    org_id: Mapped[UUID | None] = mapped_column(Uuid)
    thread_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("agent_threads.id", ondelete="SET NULL")
    )
    run_id: Mapped[UUID | None] = mapped_column(Uuid)
    message_id: Mapped[UUID | None] = mapped_column(Uuid)
    origin: Mapped[str] = mapped_column(Text)
    # Ключ идемпотентности источника (AG-R2): тот же ключ — та же карточка.
    origin_key: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="proposed")
    nonce: Mapped[str] = mapped_column(Text)
    items: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    friction: Mapped[int] = mapped_column(SmallInteger, server_default="0")
    taint: Mapped[int] = mapped_column(SmallInteger, server_default="0")
    taint_sources: Mapped[list[str]] = mapped_column(
        ARRAY(Text), server_default=sql_text("'{}'::text[]")
    )
    not_before: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_via: Mapped[str | None] = mapped_column(Text)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AgentAuditRecord(ModelBase):
    """One step of an action's life: proposed, decided, an item's effect — codes only."""

    __tablename__ = "agent_audit"
    __table_args__ = (
        PrimaryKeyConstraint("id", "created_at", name="pk_agent_audit"),
        CheckConstraint(f"event IN ({AUDIT_EVENTS})", name="event_known"),
        CheckConstraint(f"code IS NULL OR code {CODE_FORM}", name="code_form"),
        Index("ix_agent_audit_action", "action_id", "created_at"),
        Index("ix_agent_audit_item", "item_key", postgresql_where=sql_text("item_key IS NOT NULL")),
        {"postgresql_partition_by": monthly_partition_range("created_at")},
    )

    # Идентификатор события outbox или перехода: повторная доставка не пишет вторую строку.
    id: Mapped[UUID] = mapped_column(Uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    user_id: Mapped[UUID] = mapped_column(Uuid)
    action_id: Mapped[UUID] = mapped_column(Uuid)
    item_key: Mapped[str | None] = mapped_column(Text)
    tool_name: Mapped[str | None] = mapped_column(Text)
    event: Mapped[str] = mapped_column(Text)
    via: Mapped[str | None] = mapped_column(Text)
    targets: Mapped[int | None] = mapped_column(Integer)
    code: Mapped[str | None] = mapped_column(Text)


RUN_MODELS: Final = (AgentRunRecord, AgentActionRecord, AgentAuditRecord)
