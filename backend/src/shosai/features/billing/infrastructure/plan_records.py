"""The plan catalogue in the EU home (billing plan §3.4; revision `f1b7c3e9a05d`).

Platform data without an owning account: one copy that both homes read through the
catalogue. Prices are minor units per currency and period; a NULL limit is unlimited.
The Free plan comes from the migration, so tests keep the table and restore its rows.
"""

from datetime import datetime
from typing import Final
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
    true,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from shosai.core.db.model_base import ModelBase, table_info
from shosai.core.kernel.homes import Home

CURRENCY_COLUMNS: Final = ("rub", "usd", "eur")
CAPABILITIES: Final = (
    "'shared_workspace', 'member_management', 'centralized_billing', 'sso', "
    "'admin_controls', 'priority_support', 'usage_analytics', 'frontier_models'"
)
LIMIT_COLUMNS: Final = (
    "meeting_minutes_per_month",
    "file_manager_gb",
    "knowledge_base_mb",
    "weekly_standard_tokens",
    "weekly_frontier_tokens",
    "daily_standard_tokens",
)


def period_rule(period: str) -> str:
    """A period's prices are all zero or all positive; a custom-priced plan has none."""
    columns = [f"price_{period}_{currency}" for currency in CURRENCY_COLUMNS]
    zero = " AND ".join(f"{column} = 0" for column in columns)
    positive = " AND ".join(f"{column} > 0" for column in columns)
    bounded = " AND ".join(f"{column} BETWEEN 0 AND 1000000000" for column in columns)
    return f"({bounded}) AND (({zero}) OR (NOT custom_pricing AND {positive}))"


def price() -> Mapped[int]:
    """One price in minor units."""
    return mapped_column(BigInteger, server_default=text("0"))


class TariffRecord(ModelBase):
    """One plan of the catalogue."""

    __tablename__ = "tariffs"
    __table_args__ = (
        CheckConstraint(
            "slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$' AND length(slug) BETWEEN 2 AND 40",
            name="slug_form",
        ),
        CheckConstraint("length(name) BETWEEN 1 AND 60", name="name_length"),
        CheckConstraint("length(description) <= 300", name="description_length"),
        CheckConstraint("audience IN ('individual', 'team', 'enterprise')", name="audience_known"),
        CheckConstraint(
            "(seats_min IS NULL AND seats_max IS NULL) OR (seats_min >= 1 AND "
            "(seats_max IS NULL OR seats_max >= seats_min))",
            name="seats_range",
        ),
        CheckConstraint("audience <> 'team' OR seats_min IS NOT NULL", name="team_has_seats"),
        CheckConstraint(period_rule("month"), name="month_prices"),
        CheckConstraint(period_rule("year"), name="year_prices"),
        CheckConstraint(
            " AND ".join(f"coalesce({column}, 0) >= 0" for column in LIMIT_COLUMNS),
            name="limits_not_negative",
        ),
        CheckConstraint(
            "room_participants IS NULL OR room_participants BETWEEN 2 AND 1000",
            name="room_participants_range",
        ),
        CheckConstraint(
            f"capabilities <@ ARRAY[{CAPABILITIES}]::text[]", name="capabilities_known"
        ),
        CheckConstraint("cardinality(features) <= 20", name="features_count"),
        CheckConstraint("sort_order BETWEEN 0 AND 999", name="sort_order_range"),
        CheckConstraint(
            "archived_at IS NULL OR (NOT is_active AND NOT is_featured)", name="archived_off_sale"
        ),
        Index("uq_tariffs_slug", "slug", unique=True),
        {"info": table_info(homes=(Home.EU,), seeded_by_migration=True)},
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    slug: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, server_default=text("''"))
    audience: Mapped[str] = mapped_column(Text)
    seats_min: Mapped[int | None] = mapped_column(Integer)
    seats_max: Mapped[int | None] = mapped_column(Integer)
    custom_pricing: Mapped[bool] = mapped_column(Boolean, server_default=false())
    price_month_rub: Mapped[int] = price()
    price_month_usd: Mapped[int] = price()
    price_month_eur: Mapped[int] = price()
    price_year_rub: Mapped[int] = price()
    price_year_usd: Mapped[int] = price()
    price_year_eur: Mapped[int] = price()
    meeting_minutes_per_month: Mapped[int | None] = mapped_column(Integer)
    file_manager_gb: Mapped[int | None] = mapped_column(Integer)
    knowledge_base_mb: Mapped[int | None] = mapped_column(Integer)
    weekly_standard_tokens: Mapped[int | None] = mapped_column(BigInteger)
    weekly_frontier_tokens: Mapped[int | None] = mapped_column(BigInteger)
    daily_standard_tokens: Mapped[int | None] = mapped_column(BigInteger)
    room_participants: Mapped[int | None] = mapped_column(Integer)
    capabilities: Mapped[list[str]] = mapped_column(
        ARRAY(Text), server_default=text("'{}'::text[]")
    )
    features: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'::text[]"))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=true())
    is_featured: Mapped[bool] = mapped_column(Boolean, server_default=false())
    sort_order: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
