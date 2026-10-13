"""The Central Bank's rates, in the EU home, append-only (ADR 0036, DATA_MAPPING)."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Index, Numeric, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from shosai.core.db.model_base import ModelBase, table_info
from shosai.core.kernel.homes import Home


class ExchangeRate(ModelBase):
    """The rate of one currency pair as fetched at a moment."""

    __tablename__ = "exchange_rates"
    __table_args__ = (
        CheckConstraint("currency_pair IN ('USD/RUB', 'EUR/RUB')", name="pair_known"),
        CheckConstraint("rate > 0", name="rate_positive"),
        CheckConstraint("source IN ('cbr', 'manual')", name="source_known"),
        Index("ix_exchange_rates_latest", "currency_pair", "fetched_at"),
        {"info": table_info(homes=(Home.EU,))},
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    currency_pair: Mapped[str] = mapped_column(Text)
    rate: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    source: Mapped[str] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
