"""Deletion requests and the erasure saga's journal, in the account's home (identity plan §3.5).

One row per account: the window while the deletion is scheduled, then the owners whose
handlers already erased their part. `run_at` is the due column the sweep claims; it starts
at `erase_at` and moves forward by the claim's lease. The row goes in the saga's last
transaction, together with the anonymisation of the account.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Text, Uuid, func, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from shosai.core.db.model_base import ModelBase

PENDING = "state IN ('scheduled', 'erasing')"


class AccountDeletion(ModelBase):
    """A person's deletion: scheduled, cancelled by a sign-in, or being erased."""

    __tablename__ = "account_deletions"
    __table_args__ = (
        CheckConstraint("state IN ('scheduled', 'cancelled', 'erasing')", name="state_known"),
        CheckConstraint("erase_at > requested_at", name="erase_after_request"),
        CheckConstraint("(state = 'cancelled') = (cancelled_at IS NOT NULL)", name="cancelled"),
        CheckConstraint("(state = 'erasing') = (started_at IS NOT NULL)", name="started"),
        Index("ix_account_deletions_due", "run_at", "user_id", postgresql_where=text(PENDING)),
    )

    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    state: Mapped[str] = mapped_column(Text)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    erase_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Владельцы, чьи обработчики уже стёрли свою часть: повтор саги их пропускает.
    erased_owners: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")


DELETION_MODELS = (AccountDeletion,)
