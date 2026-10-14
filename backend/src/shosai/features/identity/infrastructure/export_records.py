"""Export jobs, in the account's home (identity plan §3.5).

A job is queued by the person, claimed by the sweep, written as a ZIP into the home's
bucket under `exports/<user_id>/` and kept 7 days. At most one job per person is open at a
time: the partial unique index makes a second request return the first.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from shosai.core.db.model_base import ModelBase

OPEN = "state IN ('queued', 'running')"
READY = "state = 'ready'"


class DataExportJob(ModelBase):
    """One archive of everything Shosai keeps about a person."""

    __tablename__ = "data_export_jobs"
    __table_args__ = (
        CheckConstraint("state IN ('queued', 'running', 'ready', 'failed')", name="state_known"),
        CheckConstraint("attempts BETWEEN 0 AND 10", name="attempts_bounded"),
        CheckConstraint(
            "(state = 'ready') = (ready_at IS NOT NULL AND expires_at IS NOT NULL "
            "AND object_key IS NOT NULL AND size_bytes IS NOT NULL)",
            name="ready_archive",
        ),
        CheckConstraint("(state = 'failed') = (error_code IS NOT NULL)", name="failed_with_code"),
        CheckConstraint("size_bytes IS NULL OR size_bytes >= 0", name="size_not_negative"),
        Index("uq_data_export_jobs_open", "user_id", unique=True, postgresql_where=text(OPEN)),
        Index("ix_data_export_jobs_due", "run_at", "id", postgresql_where=text(OPEN)),
        Index("ix_data_export_jobs_user", "user_id", "requested_at"),
        Index("ix_data_export_jobs_expires", "expires_at", postgresql_where=text(READY)),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"))
    state: Mapped[str] = mapped_column(Text)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, server_default="0")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    object_key: Mapped[str | None] = mapped_column(Text)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    error_code: Mapped[str | None] = mapped_column(Text)


EXPORT_MODELS = (DataExportJob,)
