"""Model prices and the Central Bank's rates: platform tables of the EU home (ADR 0035, 0036)."""

import sqlalchemy as sa
from alembic import op

from shosai.core.db.migration_scope import (
    MigrationScope,
    grant_to_application,
    revoke_from_application,
    runs_in,
)
from shosai.core.kernel.homes import Home

revision: str = "db93c8f9b9d0"
down_revision: str | None = "7f9095f97350"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = (Home.EU,)

UNITS_CHECK = (
    "unit IN ('input_token', 'cached_input_token', 'output_token', 'audio_second', 'page', "
    "'document', 'request', 'image')"
)


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Create the price list and the rates; the application reads and appends, never edits."""
    op.create_table(
        "provider_prices",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("unit", sa.Text(), nullable=False),
        sa.Column("price_usd", sa.Numeric(20, 12), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(UNITS_CHECK, name=op.f("ck_provider_prices_unit_known")),
        sa.CheckConstraint("price_usd >= 0", name=op.f("ck_provider_prices_price_not_negative")),
        sa.CheckConstraint(
            "source IN ('seed', 'openrouter', 'operator')",
            name=op.f("ck_provider_prices_source_known"),
        ),
        sa.CheckConstraint(
            "length(provider) <= 32 AND length(model) <= 128",
            name=op.f("ck_provider_prices_names_length"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_provider_prices")),
        sa.UniqueConstraint(
            "provider",
            "model",
            "unit",
            "effective_from",
            name=op.f("uq_provider_prices_provider"),
        ),
    )
    op.create_index(
        "ix_provider_prices_lookup",
        "provider_prices",
        ["provider", "model", "unit", "effective_from"],
    )
    grant_to_application(scope, "provider_prices", ("SELECT", "INSERT"))
    op.create_table(
        "exchange_rates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("currency_pair", sa.Text(), nullable=False),
        sa.Column("rate", sa.Numeric(12, 4), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "currency_pair IN ('USD/RUB', 'EUR/RUB')", name=op.f("ck_exchange_rates_pair_known")
        ),
        sa.CheckConstraint("rate > 0", name=op.f("ck_exchange_rates_rate_positive")),
        sa.CheckConstraint(
            "source IN ('cbr', 'manual')", name=op.f("ck_exchange_rates_source_known")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_exchange_rates")),
    )
    op.create_index("ix_exchange_rates_latest", "exchange_rates", ["currency_pair", "fetched_at"])
    grant_to_application(scope, "exchange_rates", ("SELECT", "INSERT"))


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Drop the rates and the price list."""
    revoke_from_application(scope, "exchange_rates")
    op.drop_table("exchange_rates")
    revoke_from_application(scope, "provider_prices")
    op.drop_table("provider_prices")
