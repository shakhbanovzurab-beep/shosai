"""The plan catalogue, promo codes and payment routes, in the EU home only (billing step 2).

Platform data without an owning account (ADR 0005): one copy, one writer, read by both
homes through the catalogue; a plan is archived, never deleted while anyone has it. The
Free plan is seeded with a fixed id that entitlements fall back to; payment routes are
seeded as the draft runs them (TBank, lava and lava PayPal on, CloudPayments off).
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from shosai.core.db.migration_scope import (
    APPLICATION_WRITES,
    MigrationScope,
    grant_to_application,
    revoke_from_application,
    runs_in,
)
from shosai.core.kernel.homes import Home

revision: str = "f1b7c3e9a05d"
down_revision: str | None = "e5a9c0d4f218"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = (Home.EU,)

FREE_PLAN_ID = "0199f2a0-0000-7000-8000-000000000001"
PRICE = "BETWEEN 0 AND 1000000000"
CAPABILITIES = (
    "'shared_workspace', 'member_management', 'centralized_billing', 'sso', "
    "'admin_controls', 'priority_support', 'usage_analytics', 'frontier_models'"
)


def check(table: str, sql: str, name: str) -> sa.CheckConstraint:
    """A check constraint named by the project's convention."""
    return sa.CheckConstraint(sql, name=op.f(f"ck_{table}_{name}"))


def prices(period: str) -> list[sa.Column[int]]:
    """A period's price in each currency, minor units."""
    return [
        sa.Column(f"price_{period}_{currency}", sa.BigInteger(), server_default="0", nullable=False)
        for currency in ("rub", "usd", "eur")
    ]


def period_rule(period: str) -> str:
    """A period's prices are all zero or all positive; a custom-priced plan has none."""
    columns = [f"price_{period}_{currency}" for currency in ("rub", "usd", "eur")]
    zero = " AND ".join(f"{column} = 0" for column in columns)
    positive = " AND ".join(f"{column} > 0" for column in columns)
    bounded = " AND ".join(f"{column} {PRICE}" for column in columns)
    return f"({bounded}) AND (({zero}) OR (NOT custom_pricing AND {positive}))"


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Create the catalogue, promo codes and payment routes with their seeds."""
    create_tariffs()
    create_promo_codes()
    create_payment_routes()
    for table in ("tariffs", "promo_codes", "payment_routes"):
        grant_to_application(scope, table, APPLICATION_WRITES)


def tariff_checks() -> list[sa.CheckConstraint]:
    """The catalogue's rules the database holds."""
    return [
        check(
            "tariffs",
            "slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$' AND length(slug) BETWEEN 2 AND 40",
            "slug_form",
        ),
        check("tariffs", "length(name) BETWEEN 1 AND 60", "name_length"),
        check("tariffs", "length(description) <= 300", "description_length"),
        check("tariffs", "audience IN ('individual', 'team', 'enterprise')", "audience_known"),
        check(
            "tariffs",
            "(seats_min IS NULL AND seats_max IS NULL) OR (seats_min >= 1 AND "
            "(seats_max IS NULL OR seats_max >= seats_min))",
            "seats_range",
        ),
        check("tariffs", "audience <> 'team' OR seats_min IS NOT NULL", "team_has_seats"),
        check("tariffs", period_rule("month"), "month_prices"),
        check("tariffs", period_rule("year"), "year_prices"),
        check(
            "tariffs",
            "coalesce(meeting_minutes_per_month, 0) >= 0 AND coalesce(file_manager_gb, 0) >= 0 "
            "AND coalesce(knowledge_base_mb, 0) >= 0 AND coalesce(weekly_standard_tokens, 0) >= 0 "
            "AND coalesce(weekly_frontier_tokens, 0) >= 0 "
            "AND coalesce(daily_standard_tokens, 0) >= 0",
            "limits_not_negative",
        ),
        check("tariffs", f"capabilities <@ ARRAY[{CAPABILITIES}]::text[]", "capabilities_known"),
        check("tariffs", "cardinality(features) <= 20", "features_count"),
        check("tariffs", "sort_order BETWEEN 0 AND 999", "sort_order_range"),
        check(
            "tariffs",
            "archived_at IS NULL OR (NOT is_active AND NOT is_featured)",
            "archived_off_sale",
        ),
    ]


def create_tariffs() -> None:
    """The plan catalogue with the Free plan everyone falls back to."""
    tariffs = op.create_table(
        "tariffs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("audience", sa.Text(), nullable=False),
        sa.Column("seats_min", sa.Integer(), nullable=True),
        sa.Column("seats_max", sa.Integer(), nullable=True),
        sa.Column("custom_pricing", sa.Boolean(), server_default=sa.false(), nullable=False),
        *prices("month"),
        *prices("year"),
        sa.Column("meeting_minutes_per_month", sa.Integer(), nullable=True),
        sa.Column("file_manager_gb", sa.Integer(), nullable=True),
        sa.Column("knowledge_base_mb", sa.Integer(), nullable=True),
        sa.Column("weekly_standard_tokens", sa.BigInteger(), nullable=True),
        sa.Column("weekly_frontier_tokens", sa.BigInteger(), nullable=True),
        sa.Column("daily_standard_tokens", sa.BigInteger(), nullable=True),
        sa.Column(
            "capabilities",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column(
            "features",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("is_featured", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        *tariff_checks(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tariffs")),
    )
    op.create_index("uq_tariffs_slug", "tariffs", ["slug"], unique=True)
    op.bulk_insert(
        tariffs,
        [
            {
                "id": FREE_PLAN_ID,
                "slug": "free",
                "name": "Free",
                "audience": "individual",
                "meeting_minutes_per_month": 120,
                "file_manager_gb": 0,
                "knowledge_base_mb": 0,
                # Стартовые значения владельца; дальше их меняет админ по реальным данным.
                "weekly_standard_tokens": 1_000_000,
                "weekly_frontier_tokens": 0,
                "daily_standard_tokens": 250_000,
            }
        ],
    )


def create_promo_codes() -> None:
    """Promo codes; a use is counted on a successful payment only."""
    op.create_table(
        "promo_codes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("percent_off", sa.Integer(), nullable=True),
        sa.Column("amount_off_rub", sa.BigInteger(), nullable=True),
        sa.Column("amount_off_usd", sa.BigInteger(), nullable=True),
        sa.Column("amount_off_eur", sa.BigInteger(), nullable=True),
        # NULL — все тарифы, в том числе будущие; иначе — только перечисленные.
        sa.Column("plan_ids", postgresql.ARRAY(sa.Uuid()), nullable=True),
        sa.Column("billing_period", sa.Text(), server_default="both", nullable=False),
        sa.Column("max_redemptions", sa.Integer(), nullable=True),
        sa.Column("per_user_limit", sa.Integer(), nullable=True),
        sa.Column("redemptions", sa.Integer(), server_default="0", nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("first_payment_only", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        check("promo_codes", "code ~ '^[A-Z0-9_-]{3,32}$'", "code_form"),
        check(
            "promo_codes",
            "(percent_off IS NOT NULL) <> "
            "(coalesce(amount_off_rub, amount_off_usd, amount_off_eur) IS NOT NULL)",
            "one_discount_kind",
        ),
        check(
            "promo_codes", "percent_off IS NULL OR percent_off BETWEEN 1 AND 100", "percent_range"
        ),
        check(
            "promo_codes",
            "coalesce(amount_off_rub, 100) >= 100 AND coalesce(amount_off_usd, 100) >= 100 "
            "AND coalesce(amount_off_eur, 100) >= 100",
            "fixed_minimum",
        ),
        check("promo_codes", "billing_period IN ('month', 'year', 'both')", "period_known"),
        check(
            "promo_codes",
            "max_redemptions IS NULL OR max_redemptions BETWEEN 1 AND 10000000",
            "max_range",
        ),
        check(
            "promo_codes",
            "per_user_limit IS NULL OR (per_user_limit BETWEEN 1 AND 1000 AND "
            "(max_redemptions IS NULL OR per_user_limit <= max_redemptions))",
            "per_user_range",
        ),
        check("promo_codes", "redemptions >= 0", "redemptions_not_negative"),
        check(
            "promo_codes",
            "valid_from IS NULL OR valid_until IS NULL OR valid_from <= valid_until",
            "dates_ordered",
        ),
        check(
            "promo_codes",
            "plan_ids IS NULL OR (cardinality(plan_ids) <= 50 AND "
            "(cardinality(plan_ids) >= 1 OR NOT is_active))",
            "plan_ids_count",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_promo_codes")),
    )
    op.create_index("uq_promo_codes_code", "promo_codes", ["code"], unique=True)


def create_payment_routes() -> None:
    """Which acquirer takes which currency zone, in which order (draft routing as data)."""
    routes = op.create_table(
        "payment_routes",
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("method", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        check("payment_routes", "scope IN ('RUB', 'FX')", "scope_known"),
        check(
            "payment_routes",
            "method IN ('tbank', 'cloudpayments', 'lava', 'lava_paypal')",
            "method_known",
        ),
        check("payment_routes", "position BETWEEN 1 AND 100", "position_range"),
        sa.PrimaryKeyConstraint("scope", "method", name=op.f("pk_payment_routes")),
    )
    op.bulk_insert(
        routes,
        [
            {"scope": "RUB", "method": "tbank", "enabled": True, "position": 1},
            {"scope": "RUB", "method": "cloudpayments", "enabled": False, "position": 2},
            {"scope": "FX", "method": "lava", "enabled": True, "position": 1},
            {"scope": "FX", "method": "lava_paypal", "enabled": True, "position": 2},
        ],
    )


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Drop the catalogue, promo codes and payment routes."""
    for table in ("payment_routes", "promo_codes", "tariffs"):
        revoke_from_application(scope, table)
        op.drop_table(table)
