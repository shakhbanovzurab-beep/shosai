"""Usage tombstones keep two past months: the business month spans two UTC ones (billing 7b).

Partitions of `usage_events` are cut on UTC months, while a person's minutes now count in
the business calendar's month (ADR 0058). Europe/Moscow's month starts at 21:00 UTC on the
UTC month's last day, so the previous business month — the oldest whose tombstones still
count — begins in the partition two UTC months back, which a policy of one past month
drops. The policy keeps two, and that partition is created again if it is already gone.
Every home.
"""

import sqlalchemy as sa
from alembic import op

from shosai.core.db.migration_scope import EVERY_HOME, MigrationScope, runs_in
from shosai.core.db.partitions.policy import policies

revision: str = "861ec10acf1d"
down_revision: str | None = "bdeb91c94598"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME

TABLE = "usage_events"
# Партиции режутся по месяцам UTC, как у функции обслуживания.
TWO_MONTHS_BACK = """
DO $$
DECLARE
    month_start timestamptz := date_trunc('month', now() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC'
        - interval '2 months';
    child text := format('usage_events_p%s', to_char(month_start AT TIME ZONE 'UTC', 'YYYYMM'));
BEGIN
    IF to_regclass(child) IS NULL THEN
        EXECUTE format(
            'CREATE TABLE %I (LIKE usage_events INCLUDING DEFAULTS INCLUDING CONSTRAINTS)', child
        );
        EXECUTE format(
            'ALTER TABLE usage_events ATTACH PARTITION %I FOR VALUES FROM (%L) TO (%L)',
            child, month_start, month_start + interval '1 month'
        );
    END IF;
END
$$
"""


def keep_months(months: int) -> sa.Update:
    """The tombstones' policy keeping this many past months."""
    return sa.update(policies).where(policies.c.table_name == TABLE).values(keep_months=months)


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Keep two past months and bring back the older one if the upkeep dropped it."""
    del scope
    op.execute(keep_months(2))
    op.execute(TWO_MONTHS_BACK)


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Keep one past month again; the next upkeep drops the older partition with its rows."""
    del scope
    op.execute(keep_months(1))
