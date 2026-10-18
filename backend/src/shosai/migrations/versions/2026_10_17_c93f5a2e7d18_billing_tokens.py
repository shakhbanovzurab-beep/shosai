"""Tokens: the week's and the day's use per model tier, and the token packs ledger (step 5).

`token_usage` keeps one row per person, tier and period (the Monday week, the UTC day):
the period's start and the tokens counted in it; a row of a newer period replaces the
count, one of an older period changes nothing, so the table never grows past three rows
a person. `premium_credit_ledger` holds token packs: purchases add, a debit takes what a
request used past the weekly allowance, at most once per cost row (unique `cost_id`).
The application never updates a ledger row. Both tables are personal (BL-D4).
"""

import sqlalchemy as sa
from alembic import op

from shosai.core.db.migration_scope import (
    EVERY_HOME,
    MigrationScope,
    disable_user_isolation,
    enable_user_isolation,
    grant_to_application,
    revoke_from_application,
    runs_in,
)

revision: str = "c93f5a2e7d18"
down_revision: str | None = "b7e1d4a90c26"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME


def check(table: str, sql: str, name: str) -> sa.CheckConstraint:
    """A check constraint named by the project's convention."""
    return sa.CheckConstraint(sql, name=op.f(f"ck_{table}_{name}"))


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Create the token use per period and the packs ledger, personal by row-level security."""
    op.create_table(
        "token_usage",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("tier", sa.Text(), nullable=False),
        sa.Column("period", sa.Text(), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("tokens", sa.BigInteger(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        check("token_usage", "tier IN ('standard', 'frontier')", "tier_known"),
        check("token_usage", "period IN ('week', 'day')", "period_known"),
        check("token_usage", "tokens >= 0", "tokens_not_negative"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_token_usage")),
    )
    op.create_index(
        "uq_token_usage_period", "token_usage", ["user_id", "tier", "period"], unique=True
    )
    op.create_table(
        "premium_credit_ledger",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("tokens", sa.BigInteger(), nullable=False),
        sa.Column("cost_id", sa.Uuid(), nullable=True),
        sa.Column("transaction_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        check("premium_credit_ledger", "kind IN ('purchase', 'debit', 'refund')", "kind_known"),
        check(
            "premium_credit_ledger",
            "(kind = 'debit' AND tokens < 0 AND cost_id IS NOT NULL) OR "
            "(kind = 'purchase' AND tokens > 0 AND transaction_id IS NOT NULL) OR "
            "(kind = 'refund' AND tokens < 0 AND transaction_id IS NOT NULL)",
            "entry_shape",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_premium_credit_ledger")),
    )
    op.create_index("ix_premium_credit_ledger_user", "premium_credit_ledger", ["user_id"])
    op.create_index(
        "uq_premium_credit_ledger_cost", "premium_credit_ledger", ["cost_id"], unique=True
    )
    enable_user_isolation("token_usage")
    grant_to_application(scope, "token_usage")
    enable_user_isolation("premium_credit_ledger")
    # Журнал пакетов: строки добавляются и стираются вместе с аккаунтом, но не меняются.
    grant_to_application(scope, "premium_credit_ledger", ("SELECT", "INSERT", "DELETE"))


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Drop the packs ledger and the token use."""
    for table in ("premium_credit_ledger", "token_usage"):
        revoke_from_application(scope, table)
        disable_user_isolation(table)
        op.drop_table(table)
