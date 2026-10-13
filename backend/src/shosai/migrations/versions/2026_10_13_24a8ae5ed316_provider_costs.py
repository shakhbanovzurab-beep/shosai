"""One row per paid model call, partitioned by month and kept 5 years (§8.1, ADR 0041)."""

import sqlalchemy as sa
from alembic import op

from shosai.core.db.migration_scope import (
    EVERY_HOME,
    MigrationScope,
    grant_to_application,
    revoke_from_application,
    runs_in,
)
from shosai.core.db.partitions.policy import (
    MonthlyPartitions,
    monthly_partition_range,
    register_monthly_partitions,
    unregister_monthly_partitions,
)

revision: str = "24a8ae5ed316"
down_revision: str | None = "db93c8f9b9d0"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME

UNITS_CHECK = (
    "unit IN ('input_token', 'cached_input_token', 'output_token', 'audio_second', 'page', "
    "'document', 'request', 'image')"
)
# Пять лет (402-ФЗ, ADR 0041): старшие помесячные партиции удаляет обслуживание ядра.
POLICY = MonthlyPartitions("provider_costs", ahead_months=2, keep_months=60)


def check(sql: str, name: str) -> sa.CheckConstraint:
    """A check constraint named by the project's convention."""
    return sa.CheckConstraint(sql, name=op.f(f"ck_provider_costs_{name}"))


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Create the cost rows, register their monthly partitions and open them for appends."""
    op.create_table(
        "provider_costs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("effect_key", sa.Text(), nullable=False),
        sa.Column("payer", sa.Text(), nullable=False),
        sa.Column("platform_account", sa.Text(), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("org_id", sa.Uuid(), nullable=True),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("feature", sa.Text(), nullable=False),
        sa.Column("call_class", sa.Text(), nullable=False),
        sa.Column("origin", sa.Text(), nullable=False),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("cached_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("output_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("units", sa.Numeric(18, 3), server_default="0", nullable=False),
        sa.Column("unit", sa.Text(), nullable=True),
        sa.Column("cost_usd", sa.Numeric(18, 10), nullable=False),
        sa.Column("cost_source", sa.Text(), nullable=False),
        sa.Column("exchange_rate_used", sa.Numeric(12, 4), nullable=True),
        sa.Column("cost_rub", sa.Numeric(18, 2), nullable=True),
        check(
            "(payer = 'user' AND user_id IS NOT NULL AND platform_account IS NULL) OR "
            "(payer = 'platform' AND user_id IS NULL AND platform_account IS NOT NULL)",
            "payer_named",
        ),
        check(
            "platform_account IN ('landing_demo', 'help_assistant', 'system')",
            "platform_account_known",
        ),
        check("call_class IN ('essential', 'standard', 'expensive')", "class_known"),
        check("origin IN ('interactive', 'background', 'system')", "origin_known"),
        check("kind IN ('chat', 'embed', 'rerank', 'image')", "kind_known"),
        check("outcome IN ('ok', 'failed')", "outcome_known"),
        check("cost_source IN ('reported', 'priced', 'draft_session')", "source_known"),
        check(f"unit IS NULL OR {UNITS_CHECK}", "unit_known"),
        check(
            "input_tokens >= 0 AND cached_tokens >= 0 AND output_tokens >= 0 AND units >= 0 "
            "AND cost_usd >= 0",
            "amounts_not_negative",
        ),
        check("(exchange_rate_used IS NULL) = (cost_rub IS NULL)", "rubles_with_their_rate"),
        check("length(effect_key) BETWEEN 1 AND 200", "effect_key_length"),
        sa.PrimaryKeyConstraint("id", "created_at", name=op.f("pk_provider_costs")),
        postgresql_partition_by=monthly_partition_range("created_at"),
    )
    op.create_index("ix_provider_costs_user", "provider_costs", ["user_id", "created_at"])
    op.create_index(
        "ix_provider_costs_model", "provider_costs", ["provider", "model", "created_at"]
    )
    # Строки стоимости только добавляются: правок и удалений приложение не делает.
    grant_to_application(scope, "provider_costs", ("SELECT", "INSERT"))
    register_monthly_partitions(POLICY)


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Forget the partition policy and drop the cost rows with their partitions."""
    unregister_monthly_partitions(POLICY.table)
    revoke_from_application(scope, "provider_costs")
    op.drop_table("provider_costs")
