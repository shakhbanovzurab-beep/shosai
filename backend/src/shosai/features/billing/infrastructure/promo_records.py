"""Promo codes and payment routes in the EU home (billing plan §3.4; revision `f1b7c3e9a05d`).

A promo code's plans are the catalogue's ids, or NULL for every plan including later
ones; a fixed discount is a column per currency it names. Payment routes say which
acquirer takes which currency zone in which order; the migration seeds them.
"""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Index,
    Integer,
    PrimaryKeyConstraint,
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


class PromoCodeRecord(ModelBase):
    """One promo code and how often it was used."""

    __tablename__ = "promo_codes"
    __table_args__ = (
        CheckConstraint("code ~ '^[A-Z0-9_-]{3,32}$'", name="code_form"),
        CheckConstraint(
            "(percent_off IS NOT NULL) <> "
            "(coalesce(amount_off_rub, amount_off_usd, amount_off_eur) IS NOT NULL)",
            name="one_discount_kind",
        ),
        CheckConstraint(
            "percent_off IS NULL OR percent_off BETWEEN 1 AND 100", name="percent_range"
        ),
        CheckConstraint(
            "coalesce(amount_off_rub, 100) >= 100 AND coalesce(amount_off_usd, 100) >= 100 "
            "AND coalesce(amount_off_eur, 100) >= 100",
            name="fixed_minimum",
        ),
        CheckConstraint("billing_period IN ('month', 'year', 'both')", name="period_known"),
        CheckConstraint(
            "max_redemptions IS NULL OR max_redemptions BETWEEN 1 AND 10000000", name="max_range"
        ),
        CheckConstraint(
            "per_user_limit IS NULL OR (per_user_limit BETWEEN 1 AND 1000 AND "
            "(max_redemptions IS NULL OR per_user_limit <= max_redemptions))",
            name="per_user_range",
        ),
        CheckConstraint("redemptions >= 0", name="redemptions_not_negative"),
        CheckConstraint(
            "valid_from IS NULL OR valid_until IS NULL OR valid_from <= valid_until",
            name="dates_ordered",
        ),
        CheckConstraint(
            "plan_ids IS NULL OR (cardinality(plan_ids) <= 50 AND "
            "(cardinality(plan_ids) >= 1 OR NOT is_active))",
            name="plan_ids_count",
        ),
        Index("uq_promo_codes_code", "code", unique=True),
        {"info": table_info(homes=(Home.EU,))},
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    code: Mapped[str] = mapped_column(Text)
    percent_off: Mapped[int | None] = mapped_column(Integer)
    amount_off_rub: Mapped[int | None] = mapped_column(BigInteger)
    amount_off_usd: Mapped[int | None] = mapped_column(BigInteger)
    amount_off_eur: Mapped[int | None] = mapped_column(BigInteger)
    # NULL — все тарифы, в том числе будущие; иначе — только перечисленные.
    plan_ids: Mapped[list[UUID] | None] = mapped_column(ARRAY(Uuid))
    billing_period: Mapped[str] = mapped_column(Text, server_default=text("'both'"))
    max_redemptions: Mapped[int | None] = mapped_column(Integer)
    per_user_limit: Mapped[int | None] = mapped_column(Integer)
    redemptions: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_until: Mapped[date | None] = mapped_column(Date)
    first_payment_only: Mapped[bool] = mapped_column(Boolean, server_default=false())
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=true())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PaymentRouteRecord(ModelBase):
    """Whether an acquirer takes a currency zone, and its place in the zone's order."""

    __tablename__ = "payment_routes"
    __table_args__ = (
        PrimaryKeyConstraint("scope", "method", name="pk_payment_routes"),
        CheckConstraint("scope IN ('RUB', 'FX')", name="scope_known"),
        CheckConstraint(
            "method IN ('tbank', 'cloudpayments', 'lava', 'lava_paypal')", name="method_known"
        ),
        CheckConstraint("position BETWEEN 1 AND 100", name="position_range"),
        {"info": table_info(homes=(Home.EU,), seeded_by_migration=True)},
    )

    scope: Mapped[str] = mapped_column(Text)
    method: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean)
    position: Mapped[int] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
