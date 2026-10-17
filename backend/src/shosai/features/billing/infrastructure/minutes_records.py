"""Usage tombstones by month and the Free plan's device claims (revision `b7e1d4a90c26`).

Both are personal by row-level security; `usage_events` is partitioned by the month of
the meeting and keeps the current and the previous month.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    LargeBinary,
    PrimaryKeyConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from shosai.core.db.model_base import ModelBase
from shosai.core.db.partitions.policy import monthly_partition_range


class UsageEventRecord(ModelBase):
    """A deleted meeting's minutes, counted in the month the meeting happened."""

    __tablename__ = "usage_events"
    __table_args__ = (
        PrimaryKeyConstraint("id", "occurred_at", name="pk_usage_events"),
        CheckConstraint("seconds BETWEEN 0 AND 604800", name="seconds_range"),
        Index("ix_usage_events_user", "user_id", "occurred_at"),
        Index("uq_usage_events_meeting", "meeting_id", "occurred_at", unique=True),
        {"postgresql_partition_by": monthly_partition_range("occurred_at")},
    )

    id: Mapped[UUID] = mapped_column(Uuid)
    # Начало встречи: по нему выбирается месяц.
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    user_id: Mapped[UUID] = mapped_column(Uuid)
    meeting_id: Mapped[UUID] = mapped_column(Uuid)
    seconds: Mapped[int] = mapped_column(Integer)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class FreePlanDeviceRecord(ModelBase):
    """A desktop device claimed by one Free account, by the SHA-256 of its id or name."""

    __tablename__ = "free_plan_devices"
    __table_args__ = (
        CheckConstraint("octet_length(device_hash) = 32", name="hash_length"),
        Index("ix_free_plan_devices_user", "user_id"),
    )

    device_hash: Mapped[bytes] = mapped_column(LargeBinary, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(Uuid)
    claimed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
