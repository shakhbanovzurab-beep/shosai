"""A person's subscription and the plans queued behind it, in each home (billing step 3).

One subscription row per person: the plan in force, its expiry (the authority, never
recomputed), auto-renewal, the trial mark and a version that every change bumps, so a
cached entitlement snapshot of an older version is never read. Queued plans are the
draft's frozen segments: they run one after another from the expiry. The plan is the
EU catalogue's id, without a foreign key across homes. Both tables are personal: the
application reads and writes only the transaction's person; the catalogue learns how
many people hold a plan through `billing_plan_holders`, which returns counts and no rows.
"""

from datetime import datetime

import sqlalchemy as sa
from alembic import op

from shosai.core.db.migration_scope import (
    EVERY_HOME,
    FunctionArgument,
    MigrationScope,
    disable_user_isolation,
    drop_function,
    enable_user_isolation,
    grant_to_application,
    open_function,
    revoke_from_application,
    runs_in,
)

revision: str = "a4c2e8f61b93"
down_revision: str | None = "f1b7c3e9a05d"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME

TABLES = ("subscriptions", "subscription_segments")
HOLDERS = "billing_plan_holders"
HOLDERS_ARGUMENTS: tuple[FunctionArgument, ...] = ("uuid[]",)
# Счётчики держателей тарифа в обход RLS: функция владельца таблиц отдаёт только числа.
HOLDERS_FUNCTION = """
CREATE FUNCTION billing_plan_holders(plans uuid[])
RETURNS TABLE (plan_id uuid, current_holders bigint, referencing_rows bigint)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
    SELECT held.plan_id, count(*) FILTER (WHERE held.current), count(*)
    FROM (
        SELECT s.plan_id, s.expires_at IS NULL OR s.expires_at > now() AS current
        FROM subscriptions s WHERE s.plan_id = ANY(plans)
        UNION ALL
        SELECT q.plan_id, true FROM subscription_segments q WHERE q.plan_id = ANY(plans)
    ) AS held
    GROUP BY held.plan_id
$$
"""


def check(table: str, sql: str, name: str) -> sa.CheckConstraint:
    """A check constraint named by the project's convention."""
    return sa.CheckConstraint(sql, name=op.f(f"ck_{table}_{name}"))


def moment(name: str, *, nullable: bool = False) -> sa.Column[datetime]:
    """A timestamp column; creation and update moments default to now."""
    default = sa.func.now() if name in {"created_at", "updated_at"} else None
    return sa.Column(name, sa.DateTime(timezone=True), server_default=default, nullable=nullable)


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Create the subscriptions and their queued plans, personal by row-level security."""
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("billing_period", sa.Text(), nullable=True),
        moment("started_at"),
        moment("expires_at", nullable=True),
        sa.Column("auto_renew", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("trial", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("version", sa.BigInteger(), server_default="1", nullable=False),
        moment("created_at"),
        moment("updated_at"),
        check("subscriptions", "billing_period IN ('month', 'year')", "period_known"),
        check(
            "subscriptions", "expires_at IS NULL OR expires_at > started_at", "expiry_after_start"
        ),
        check("subscriptions", "NOT (trial AND auto_renew)", "trial_not_renewed"),
        check("subscriptions", "version >= 1", "version_positive"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_subscriptions")),
    )
    op.create_index("uq_subscriptions_user", "subscriptions", ["user_id"], unique=True)
    op.create_table(
        "subscription_segments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("remaining_days", sa.Integer(), nullable=False),
        moment("created_at"),
        check("subscription_segments", "position BETWEEN 1 AND 100", "position_range"),
        check("subscription_segments", "remaining_days BETWEEN 1 AND 36600", "days_range"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_subscription_segments")),
    )
    op.create_index(
        "uq_subscription_segments_position",
        "subscription_segments",
        ["user_id", "position"],
        unique=True,
    )
    for table in TABLES:
        enable_user_isolation(table)
        grant_to_application(scope, table)
    op.execute(HOLDERS_FUNCTION)
    open_function(HOLDERS, HOLDERS_ARGUMENTS, (scope.application_role,))


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Drop the holder counts, the queued plans and the subscriptions."""
    drop_function(HOLDERS, HOLDERS_ARGUMENTS)
    for table in reversed(TABLES):
        revoke_from_application(scope, table)
        disable_user_isolation(table)
        op.drop_table(table)
