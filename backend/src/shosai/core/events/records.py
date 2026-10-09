"""The outbox and the delivery marks, in every home (target architecture §8.1, §12).

An outbox row is written in the transaction of the effect it reports, so the event
exists exactly when the effect does. It keeps the tenancy of that transaction — the
delivery runs in the same scope — and the trace context and request id that caused it
(§16.2). The relay claims due rows for a short lease, queues one delivery per subscriber
and marks the row published; a row whose deliveries could not be queued is due again
after a backoff. Published rows stay 7 days, delivery marks 14 (F1 plan, F1-C5).

A delivery mark `(consumer, event_id)` is written in the consumer's transaction together
with its effect, so a redelivered event changes nothing. Both tables hold ids and codes
only. They have no row-level security: the relay and the purge sweep every tenant of the
home, and the application reaches them only through `core/events`.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, Text, Uuid, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from shosai.core.db.model_base import ModelBase


class OutboxMessage(ModelBase):
    """One event waiting for the relay, or published and kept for diagnosis."""

    __tablename__ = "outbox_messages"
    __table_args__ = (
        CheckConstraint(
            "event_type ~ '^[a-z][a-z0-9_]*\\.[a-z][a-z0-9_]*\\.[a-z][a-z0-9_]*$' "
            "AND length(event_type) <= 64",
            name="event_type_format",
        ),
        CheckConstraint("version >= 1", name="version_positive"),
        CheckConstraint("jsonb_typeof(payload) = 'object'", name="payload_object"),
        CheckConstraint("attempts >= 0", name="attempts_not_negative"),
        CheckConstraint("length(traceparent) <= 128", name="traceparent_length"),
        CheckConstraint("length(request_id) <= 64", name="request_id_length"),
        # Единственный запрос relay: частичный индекс не растёт вместе с опубликованной историей.
        Index(
            "ix_outbox_messages_due",
            "available_at",
            "id",
            postgresql_where=text("published_at IS NULL"),
        ),
        Index(
            "ix_outbox_messages_published_at",
            "published_at",
            postgresql_where=text("published_at IS NOT NULL"),
        ),
    )

    # UUIDv7 события — ключ дедупликации у потребителя.
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    event_type: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    user_id: Mapped[UUID | None] = mapped_column(Uuid)
    org_id: Mapped[UUID | None] = mapped_column(Uuid)
    traceparent: Mapped[str | None] = mapped_column(Text)
    request_id: Mapped[str | None] = mapped_column(Text)
    # Время транзакции эффекта: часы сервера базы, а не процесса.
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # Раньше этого момента relay строку не берёт: аренда захвата или пауза после сбоя.
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    attempts: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProcessedEvent(ModelBase):
    """A consumer has applied an event: written in the transaction of its effect."""

    __tablename__ = "processed_events"
    __table_args__ = (Index("ix_processed_events_processed_at", "processed_at"),)

    consumer: Mapped[str] = mapped_column(Text, primary_key=True)
    event_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
