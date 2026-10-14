"""Outgoing mail and the people who left a kind of it, in every home (F6 plan §3.8).

An `email_messages` row is written in the caller's transaction (F6-C10), so a mail exists
exactly when its cause does; the relay of the home sends it later, outside any transaction.
The row holds the recipient's address — personal data, kept 7 days after the mail reached
a final state — and the template's parameters; secret ones (codes, reset links) are
encrypted with the Fernet key ring and never logged. A campaign key is unique per recipient,
so a newsletter repeated by a retried batch is written once.

`email_suppressions` holds one row per (user, kind) the person unsubscribed from; the
`account` kind is never suppressed. Neither table has row-level security: the relay sweeps
every tenant of the home, and the application reaches them only through `core/email`.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    LargeBinary,
    PrimaryKeyConstraint,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from shosai.core.db.model_base import ModelBase

KINDS_CHECK = "kind IN ('account', 'notification', 'newsletter')"


class EmailMessage(ModelBase):
    """One mail to send, being sent, or sent and kept for diagnosis."""

    __tablename__ = "email_messages"
    __table_args__ = (
        CheckConstraint(KINDS_CHECK, name="kind_known"),
        CheckConstraint("status IN ('queued', 'sending', 'sent', 'failed')", name="status_known"),
        CheckConstraint("jsonb_typeof(params) = 'object'", name="params_object"),
        CheckConstraint("attempts >= 0", name="attempts_not_negative"),
        CheckConstraint(
            "length(recipient) BETWEEN 3 AND 254 AND length(template) BETWEEN 1 AND 64 "
            "AND length(locale) BETWEEN 2 AND 8",
            name="lengths",
        ),
        CheckConstraint(
            "(status IN ('sent', 'failed')) = (finished_at IS NOT NULL)", name="finished"
        ),
        Index(
            "ix_email_messages_due",
            "run_at",
            "id",
            postgresql_where=text("status IN ('queued', 'sending')"),
        ),
        Index(
            "uq_email_messages_campaign",
            "recipient",
            "campaign_key",
            unique=True,
            postgresql_where=text("campaign_key IS NOT NULL"),
        ),
        Index(
            "ix_email_messages_finished",
            "finished_at",
            postgresql_where=text("finished_at IS NOT NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    user_id: Mapped[UUID | None] = mapped_column(Uuid)
    recipient: Mapped[str] = mapped_column(Text)
    locale: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    template: Mapped[str] = mapped_column(Text)
    params: Mapped[dict[str, Any]] = mapped_column(JSONB)
    secrets: Mapped[bytes | None] = mapped_column(LargeBinary)
    reply_to: Mapped[str | None] = mapped_column(Text)
    unsubscribe_url: Mapped[str | None] = mapped_column(Text)
    campaign_key: Mapped[str | None] = mapped_column(Text)
    message_id: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="queued")
    attempts: Mapped[int] = mapped_column(Integer, server_default="0")
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Аренда отправки: пока она жива, второй отправитель письмо не берёт; истекла — берёт.
    sending_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    smtp_code: Mapped[int | None] = mapped_column(Integer)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EmailSuppression(ModelBase):
    """A person who unsubscribed from one kind of mail."""

    __tablename__ = "email_suppressions"
    __table_args__ = (
        PrimaryKeyConstraint("user_id", "kind", name="pk_email_suppressions"),
        CheckConstraint("kind IN ('notification', 'newsletter')", name="kind_suppressible"),
        CheckConstraint("source IN ('link', 'draft_link', 'settings')", name="source_known"),
    )

    user_id: Mapped[UUID] = mapped_column(Uuid)
    kind: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
