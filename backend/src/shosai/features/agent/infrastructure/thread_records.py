"""A person's threads with Leo, their messages and the stored results of tools (agent plan §3.4).

Personal by nature: row-level security admits the person's own rows only. Messages are kept
with their thread in monthly partitions, so a thread's pages read recent partitions first;
the stored whole results of tools are read for 30 days and their partitions are dropped
after two months. A workspace's thread names the workspace; when the person's membership
ends it is marked `erase_after` and erased unless the membership comes back (AG-D3).
"""

from datetime import datetime
from typing import Any, Final
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    PrimaryKeyConstraint,
    Text,
    Uuid,
    func,
)
from sqlalchemy import text as sql_text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from shosai.core.db.model_base import ModelBase
from shosai.core.db.partitions.policy import monthly_partition_range

SCOPES: Final = "'personal', 'workspace', 'hub'"
TITLE_SOURCES: Final = "'question', 'model', 'person'"
ROLES: Final = "'user', 'assistant', 'tool', 'server'"
ANSWER_STATUSES: Final = "'done', 'stopped', 'failed'"
EMPTY_LIST: Final = sql_text("'[]'::jsonb")


class AgentThreadRecord(ModelBase):
    """A person's conversation with Leo in one space."""

    __tablename__ = "agent_threads"
    __table_args__ = (
        CheckConstraint(f"scope_kind IN ({SCOPES})", name="scope_known"),
        CheckConstraint(
            "(org_id IS NOT NULL) = (scope_kind = 'workspace') "
            "AND (hub_id IS NOT NULL) = (scope_kind = 'hub')",
            name="scope_names_its_space",
        ),
        CheckConstraint("char_length(title) BETWEEN 1 AND 120", name="title_length"),
        CheckConstraint(f"title_source IN ({TITLE_SOURCES})", name="title_source_known"),
        Index(
            "ix_agent_threads_scope",
            "user_id",
            "scope_kind",
            "org_id",
            "hub_id",
            sql_text("last_activity_at DESC"),
            sql_text("id DESC"),
        ),
        Index(
            "ix_agent_threads_erase_after",
            "erase_after",
            postgresql_where=sql_text("erase_after IS NOT NULL"),
        ),
        Index(
            "ix_agent_threads_workspace",
            "org_id",
            "user_id",
            postgresql_where=sql_text("org_id IS NOT NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(Uuid)
    scope_kind: Mapped[str] = mapped_column(Text)
    org_id: Mapped[UUID | None] = mapped_column(Uuid)
    hub_id: Mapped[UUID | None] = mapped_column(Uuid)
    # Пусто до первого вопроса: тред создаётся при его отправке и называется им.
    title: Mapped[str | None] = mapped_column(Text)
    title_source: Mapped[str] = mapped_column(Text, server_default="question")
    # Сводка старых ходов, которую пишет сжатие, и последнее сообщение, свёрнутое в неё.
    summary: Mapped[str] = mapped_column(Text, server_default="")
    summary_upto: Mapped[UUID | None] = mapped_column(Uuid)
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # Тред пространства, из которого человек ушёл: стирается после этого момента (AG-D3).
    erase_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AgentMessageRecord(ModelBase):
    """One row of a thread: a question, an answer, a tool round or a server note."""

    __tablename__ = "agent_messages"
    __table_args__ = (
        PrimaryKeyConstraint("id", "created_at", name="pk_agent_messages"),
        CheckConstraint(f"role IN ({ROLES})", name="role_known"),
        CheckConstraint(
            f"(status IS NULL) = (role <> 'assistant') AND (status IS NULL OR status IN "
            f"({ANSWER_STATUSES}))",
            name="answer_has_status",
        ),
        CheckConstraint(
            "(role = 'tool') = (tool_call_id IS NOT NULL AND tool_name IS NOT NULL)",
            name="tool_row_names_its_call",
        ),
        CheckConstraint("tokens >= 0", name="tokens_not_negative"),
        Index(
            "ix_agent_messages_thread",
            "thread_id",
            sql_text("created_at DESC"),
            sql_text("id DESC"),
        ),
        {"postgresql_partition_by": monthly_partition_range("created_at")},
    )

    id: Mapped[UUID] = mapped_column(Uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    thread_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("agent_threads.id", ondelete="CASCADE")
    )
    user_id: Mapped[UUID] = mapped_column(Uuid)
    run_id: Mapped[UUID | None] = mapped_column(Uuid)
    role: Mapped[str] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text, server_default="")
    # Вызовы инструментов, которые модель сделала в этом раунде (роль assistant).
    # None — SQL NULL, не JSON null: по нему строка разговора отличается от раунда.
    tool_calls: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB(none_as_null=True))
    tool_call_id: Mapped[str | None] = mapped_column(Text)
    tool_name: Mapped[str | None] = mapped_column(Text)
    # Что модель прочла из результата: целиком в пределах бюджета или дайджест со ссылкой.
    digest: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    result_id: Mapped[UUID | None] = mapped_column(Uuid)
    attachments: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default=EMPTY_LIST)
    steps: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default=EMPTY_LIST)
    sources: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default=EMPTY_LIST)
    artifacts: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default=EMPTY_LIST)
    action_ids: Mapped[list[UUID]] = mapped_column(
        ARRAY(Uuid), server_default=sql_text("'{}'::uuid[]")
    )
    # Оценка токенов строки: окно недавних сообщений режется по ней без пересчёта.
    tokens: Mapped[int] = mapped_column(Integer, server_default="0")
    duration_ms: Mapped[int | None] = mapped_column(Integer)


class AgentToolResultRecord(ModelBase):
    """A tool's whole output, paged by `read_result`, with the spaces of its sources."""

    __tablename__ = "agent_tool_results"
    __table_args__ = (
        PrimaryKeyConstraint("id", "created_at", name="pk_agent_tool_results"),
        CheckConstraint("tokens >= 0", name="tokens_not_negative"),
        Index("ix_agent_tool_results_user", "user_id", "created_at"),
        {"postgresql_partition_by": monthly_partition_range("created_at")},
    )

    id: Mapped[UUID] = mapped_column(Uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    user_id: Mapped[UUID] = mapped_column(Uuid)
    run_id: Mapped[UUID] = mapped_column(Uuid)
    tool_name: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    # Пространства источников результата: read_result проверяет членство при каждом чтении.
    spaces: Mapped[list[UUID]] = mapped_column(ARRAY(Uuid), server_default=sql_text("'{}'::uuid[]"))
    tokens: Mapped[int] = mapped_column(Integer, server_default="0")


# Строка разговора, а не раунд инструментов: у сообщения модели с вызовами есть tool_calls.
SPOKEN: Final = AgentMessageRecord.tool_calls.is_(None)
THREAD_MODELS: Final = (AgentThreadRecord, AgentMessageRecord, AgentToolResultRecord)
