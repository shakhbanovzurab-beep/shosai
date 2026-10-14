"""The transfer journal, in the home the account leaves (identity plan §3.5).

The row has no foreign key to the account: the account row of this home is purged at the
end of the transfer, while the journal stays as its record. `run_at` is the due column the
sweep claims; at most one transfer of an account is open at a time.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, Text, Uuid, func, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from shosai.core.db.model_base import ModelBase

STEPS = "'freeze', 'copy', 'verify', 'switch', 'bump', 'purge', 'cancelling', 'done', 'cancelled'"
OPEN = "step IN ('freeze', 'copy', 'verify', 'switch', 'bump', 'purge', 'cancelling')"


class HomeTransfer(ModelBase):
    """One account's move from one home to the other, step by step."""

    __tablename__ = "home_transfers"
    __table_args__ = (
        CheckConstraint(f"step IN ({STEPS})", name="step_known"),
        CheckConstraint(
            "from_home IN ('ru', 'eu') AND to_home IN ('ru', 'eu') AND from_home <> to_home",
            name="homes_differ",
        ),
        CheckConstraint("attempts >= 0", name="attempts_not_negative"),
        CheckConstraint(
            "(step IN ('done', 'cancelled')) = (finished_at IS NOT NULL)", name="finished"
        ),
        Index("uq_home_transfers_open", "user_id", unique=True, postgresql_where=text(OPEN)),
        Index("ix_home_transfers_due", "run_at", "id", postgresql_where=text(OPEN)),
        Index("ix_home_transfers_finished", "finished_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(Uuid)
    from_home: Mapped[str] = mapped_column(Text)
    to_home: Mapped[str] = mapped_column(Text)
    step: Mapped[str] = mapped_column(Text)
    # Состояние аккаунта до заморозки: к нему он вернётся после переноса или отмены.
    prior_state: Mapped[str | None] = mapped_column(Text)
    requested_by: Mapped[UUID | None] = mapped_column(Uuid)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, server_default="0")
    copied_owners: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    # Дайджесты владельцев в источнике, сверенные с целевым домом перед переключением.
    manifest: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error_code: Mapped[str | None] = mapped_column(Text)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


TRANSFER_MODELS = (HomeTransfer,)
