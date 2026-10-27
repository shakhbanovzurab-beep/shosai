"""Leo's voice conversations by month, for the plan's minutes (revision `d237c5ac833f`).

A row per conversation in the person's home, personal by row-level security: its start, the
seconds counted so far — written every minute, so a process that dies loses at most one —
and its end. Partitioned by the month of the start; the current and the previous month are
kept, as billing counts them.
"""

from datetime import datetime
from typing import Final
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, PrimaryKeyConstraint, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from shosai.core.db.model_base import ModelBase
from shosai.core.db.partitions.policy import monthly_partition_range
from shosai.features.capture.domain.voice import VoiceEnd

# Разговор длится до 30 минут; запас — на минуту, которую дописывает его конец.
SECONDS_MAX: Final = 3_600
END_CODES: Final = ", ".join(f"'{end.value}'" for end in VoiceEnd)


class VoiceSessionRecord(ModelBase):
    """One voice conversation's minutes."""

    __tablename__ = "capture_voice_sessions"
    __table_args__ = (
        PrimaryKeyConstraint("id", "started_at", name="pk_capture_voice_sessions"),
        CheckConstraint(f"seconds BETWEEN 0 AND {SECONDS_MAX}", name="seconds_range"),
        CheckConstraint(f"end_code IN ({END_CODES})", name="end_known"),
        CheckConstraint("(ended_at IS NULL) = (end_code IS NULL)", name="ended_with_code"),
        CheckConstraint("ended_at IS NULL OR ended_at >= started_at", name="ends_after_start"),
        Index("ix_capture_voice_sessions_user", "user_id", "started_at"),
        {"postgresql_partition_by": monthly_partition_range("started_at")},
    )

    id: Mapped[UUID] = mapped_column(Uuid)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    user_id: Mapped[UUID] = mapped_column(Uuid)
    seconds: Mapped[int] = mapped_column(Integer, default=0)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_code: Mapped[str | None] = mapped_column(Text)


VOICE_MODELS: Final = (VoiceSessionRecord,)
