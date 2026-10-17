"""A person's subscription and queued plans in their home (revision `a4c2e8f61b93`).

Both tables are personal by row-level security. The plan is the EU catalogue's id,
without a foreign key across homes; `version` grows with every change.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    Text,
    Uuid,
    false,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from shosai.core.db.model_base import ModelBase


class SubscriptionRecord(ModelBase):
    """The plan in force of a person and how it ends."""

    __tablename__ = "subscriptions"
    __table_args__ = (
        CheckConstraint("billing_period IN ('month', 'year')", name="period_known"),
        CheckConstraint("expires_at IS NULL OR expires_at > started_at", name="expiry_after_start"),
        CheckConstraint("NOT (trial AND auto_renew)", name="trial_not_renewed"),
        CheckConstraint("version >= 1", name="version_positive"),
        Index("uq_subscriptions_user", "user_id", unique=True),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(Uuid)
    plan_id: Mapped[UUID] = mapped_column(Uuid)
    billing_period: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    auto_renew: Mapped[bool] = mapped_column(Boolean, server_default=false())
    trial: Mapped[bool] = mapped_column(Boolean, server_default=false())
    version: Mapped[int] = mapped_column(BigInteger, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SubscriptionSegmentRecord(ModelBase):
    """A plan queued behind the one in force, with the days it has left."""

    __tablename__ = "subscription_segments"
    __table_args__ = (
        CheckConstraint("position BETWEEN 1 AND 100", name="position_range"),
        CheckConstraint("remaining_days BETWEEN 1 AND 36600", name="days_range"),
        Index("uq_subscription_segments_position", "user_id", "position", unique=True),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(Uuid)
    plan_id: Mapped[UUID] = mapped_column(Uuid)
    position: Mapped[int] = mapped_column(Integer)
    remaining_days: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
