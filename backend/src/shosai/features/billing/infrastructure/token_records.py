"""Token use per tier and period, and the token packs ledger (revision `c93f5a2e7d18`)."""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    Index,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from shosai.core.db.model_base import ModelBase


class TokenUsageRecord(ModelBase):
    """A person's tokens of one tier in the current week or day."""

    __tablename__ = "token_usage"
    __table_args__ = (
        CheckConstraint("tier IN ('standard', 'frontier')", name="tier_known"),
        CheckConstraint("period IN ('week', 'day')", name="period_known"),
        CheckConstraint("tokens >= 0", name="tokens_not_negative"),
        Index("uq_token_usage_period", "user_id", "tier", "period", unique=True),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(Uuid)
    tier: Mapped[str] = mapped_column(Text)
    period: Mapped[str] = mapped_column(Text)
    # Понедельник недели или день UTC, к которому относится счёт.
    starts_on: Mapped[date] = mapped_column(Date)
    tokens: Mapped[int] = mapped_column(BigInteger)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CreditLedgerRecord(ModelBase):
    """One movement of a person's token packs: a purchase, a debit or a refund."""

    __tablename__ = "premium_credit_ledger"
    __table_args__ = (
        CheckConstraint("kind IN ('purchase', 'debit', 'refund')", name="kind_known"),
        CheckConstraint(
            "(kind = 'debit' AND tokens < 0 AND cost_id IS NOT NULL) OR "
            "(kind = 'purchase' AND tokens > 0 AND transaction_id IS NOT NULL) OR "
            "(kind = 'refund' AND tokens < 0 AND transaction_id IS NOT NULL)",
            name="entry_shape",
        ),
        Index("ix_premium_credit_ledger_user", "user_id"),
        Index("uq_premium_credit_ledger_cost", "cost_id", unique=True),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(Uuid)
    kind: Mapped[str] = mapped_column(Text)
    tokens: Mapped[int] = mapped_column(BigInteger)
    cost_id: Mapped[UUID | None] = mapped_column(Uuid)
    transaction_id: Mapped[UUID | None] = mapped_column(Uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
