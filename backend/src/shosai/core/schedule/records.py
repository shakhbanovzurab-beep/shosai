"""The last run of each periodic job, in every home (§12, F6-C13).

One row per job and home, created when the job is first seen and never deleted by the code:
a job removed from the code keeps its row, and a job unknown to the code is left alone. The
application role reads, creates and claims rows; nothing else touches them.
"""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column

from shosai.core.db.model_base import ModelBase


class ScheduleRun(ModelBase):
    """When a periodic job was last queued in this home; NULL before its first run."""

    __tablename__ = "schedule_runs"
    __table_args__ = (
        CheckConstraint(
            "job_name ~ '^[a-z][a-z0-9_]*(\\.[a-z][a-z0-9_]*)+$' AND length(job_name) <= 64",
            name="job_name_format",
        ),
    )

    job_name: Mapped[str] = mapped_column(Text, primary_key=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
