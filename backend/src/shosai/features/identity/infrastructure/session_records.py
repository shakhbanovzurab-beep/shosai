"""Sessions and sign-in events, in the account's home (identity plan §3.5; §8.2).

A refresh family is one signed-in device. The sign-in log is a high-volume table with
monthly partitions kept 12 months; failures of existing accounts are recorded too (the
draft never wrote them).
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    PrimaryKeyConstraint,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import Mapped, mapped_column

from shosai.core.db.model_base import ModelBase
from shosai.core.db.partitions.policy import monthly_partition_range


class RefreshSession(ModelBase):
    """One signed-in device: its refresh family, rotated on every refresh."""

    __tablename__ = "refresh_sessions"
    __table_args__ = (
        CheckConstraint("client_kind IN ('web', 'desktop')", name="client_kind_known"),
        CheckConstraint("generation >= 0", name="generation_not_negative"),
        CheckConstraint("length(current_id_hash) = 32", name="current_id_hash_length"),
        CheckConstraint(
            "user_agent IS NULL OR length(user_agent) <= 512", name="user_agent_length"
        ),
        CheckConstraint(
            "device_label IS NULL OR length(device_label) <= 128", name="device_label_length"
        ),
        CheckConstraint(
            "(revoked_at IS NULL) = (revoke_reason IS NULL)", name="revoked_with_reason"
        ),
        Index("ix_refresh_sessions_user", "user_id", postgresql_where=text("revoked_at IS NULL")),
        Index("ix_refresh_sessions_expires", "expires_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"))
    client_kind: Mapped[str] = mapped_column(Text)
    generation: Mapped[int] = mapped_column(Integer, server_default="0")
    current_id_hash: Mapped[bytes] = mapped_column(LargeBinary)
    previous_id_hash: Mapped[bytes | None] = mapped_column(LargeBinary)
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoke_reason: Mapped[str | None] = mapped_column(Text)
    device_label: Mapped[str | None] = mapped_column(Text)
    ip: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class LoginEvent(ModelBase):
    """One sign-in attempt of an existing account and how it ended."""

    __tablename__ = "login_events"
    __table_args__ = (
        PrimaryKeyConstraint("id", "created_at", name="pk_login_events"),
        CheckConstraint(
            "outcome IN ('success', 'wrong_password', 'blocked')", name="outcome_known"
        ),
        CheckConstraint("client_kind IN ('web', 'desktop')", name="client_kind_known"),
        CheckConstraint(
            "user_agent IS NULL OR length(user_agent) <= 512", name="user_agent_length"
        ),
        Index("ix_login_events_user", "user_id", "created_at"),
        {"postgresql_partition_by": monthly_partition_range("created_at")},
    )

    id: Mapped[UUID] = mapped_column(Uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    user_id: Mapped[UUID] = mapped_column(Uuid)
    outcome: Mapped[str] = mapped_column(Text)
    client_kind: Mapped[str] = mapped_column(Text)
    ip: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(Text)


SESSION_MODELS = (RefreshSession, LoginEvent)
