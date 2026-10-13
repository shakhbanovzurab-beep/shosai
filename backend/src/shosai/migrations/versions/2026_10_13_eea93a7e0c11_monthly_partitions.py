"""Monthly partitions: the policy of each partitioned table and the function that keeps it."""

import sqlalchemy as sa
from alembic import op

from shosai.core.db.migration_scope import (
    EVERY_HOME,
    MigrationScope,
    grant_to_application,
    quote,
    revoke_from_application,
    run_ddl,
    runs_in,
)

revision: str = "eea93a7e0c11"
down_revision: str | None = "72310e0e62f3"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME

# Функция работает с правами роли миграций (владельца таблиц), но только по политике
# зарегистрированной таблицы. Часы и границы — в UTC при любой зоне сессии. Новая партиция
# создаётся отдельной таблицей и прикрепляется: ATTACH берёт у родителя SHARE UPDATE
# EXCLUSIVE и не останавливает чтение и запись. Удаление ждёт блокировку не дольше 2 с;
# не дождалось — партиция переходит на следующий такт.
MAINTAIN_FUNCTION = """
CREATE FUNCTION {schema}.maintain_monthly_partitions(target text)
RETURNS TABLE (created text[], dropped text[], deferred text[], covered_until timestamptz)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
SET timezone = 'UTC'
SET lock_timeout = '2s'
AS $function$
DECLARE
    policy {schema}.partition_policies%ROWTYPE;
    this_month timestamptz := date_trunc('month', now());
    month_start timestamptz;
    child text;
    child_pattern text := '^' || target || '_p[0-9]{{6}}$';
BEGIN
    created := '{{}}';
    dropped := '{{}}';
    deferred := '{{}}';
    SELECT * INTO policy FROM {schema}.partition_policies WHERE table_name = target;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'table % has no partition policy', target USING ERRCODE = 'P0002';
    END IF;
    FOR step IN 0 .. policy.ahead_months LOOP
        month_start := this_month + make_interval(months => step);
        child := format('%s_p%s', target, to_char(month_start, 'YYYYMM'));
        IF to_regclass(format('{schema}.%I', child)) IS NULL THEN
            EXECUTE format(
                'CREATE TABLE {schema}.%I '
                '(LIKE {schema}.%I INCLUDING DEFAULTS INCLUDING CONSTRAINTS)',
                child, target
            );
            EXECUTE format(
                'ALTER TABLE {schema}.%I ATTACH PARTITION {schema}.%I FOR VALUES FROM (%L) TO (%L)',
                target, child, month_start, month_start + interval '1 month'
            );
            created := created || child;
        END IF;
    END LOOP;
    IF policy.keep_months IS NOT NULL THEN
        FOR child IN
            SELECT partition.relname
            FROM pg_inherits
            JOIN pg_class AS partition ON partition.oid = pg_inherits.inhrelid
            WHERE pg_inherits.inhparent = format('{schema}.%I', target)::regclass
              AND partition.relname ~ child_pattern
              AND to_date(right(partition.relname, 6), 'YYYYMM') + interval '1 month'
                  <= this_month - make_interval(months => policy.keep_months)
            ORDER BY partition.relname
        LOOP
            BEGIN
                EXECUTE format('DROP TABLE {schema}.%I', child);
                dropped := dropped || child;
            EXCEPTION WHEN lock_not_available THEN
                deferred := deferred || child;
            END;
        END LOOP;
    END IF;
    SELECT max(to_date(right(partition.relname, 6), 'YYYYMM')) + interval '1 month'
    INTO covered_until
    FROM pg_inherits
    JOIN pg_class AS partition ON partition.oid = pg_inherits.inhrelid
    WHERE pg_inherits.inhparent = format('{schema}.%I', target)::regclass
      AND partition.relname ~ child_pattern;
    RETURN NEXT;
END
$function$
"""
REVOKE_FROM_PUBLIC = "REVOKE ALL ON FUNCTION %(function)s(text) FROM PUBLIC"
GRANT_EXECUTE = "GRANT EXECUTE ON FUNCTION %(function)s(text) TO %(role)s"
DROP_FUNCTION = "DROP FUNCTION %(function)s(text)"
FUNCTION = "maintain_monthly_partitions"


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Create the partition policies and the upkeep function the application may call."""
    op.create_table(
        "partition_policies",
        sa.Column("table_name", sa.Text(), nullable=False),
        sa.Column("ahead_months", sa.Integer(), nullable=False),
        sa.Column("keep_months", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "table_name ~ '^[a-z][a-z0-9_]{0,54}$'",
            name=op.f("ck_partition_policies_table_name_format"),
        ),
        sa.CheckConstraint(
            "ahead_months BETWEEN 1 AND 12", name=op.f("ck_partition_policies_ahead_bounded")
        ),
        sa.CheckConstraint("keep_months >= 1", name=op.f("ck_partition_policies_keep_positive")),
        sa.PrimaryKeyConstraint("table_name", name=op.f("pk_partition_policies")),
    )
    # Политику пишут только миграции; приложение лишь читает, какие таблицы обслуживать.
    grant_to_application(scope, "partition_policies", ("SELECT",))
    schema = op.get_bind().execute(sa.text("SELECT current_schema()")).scalar_one()
    op.execute(MAINTAIN_FUNCTION.format(schema=quote(schema)))
    run_ddl(REVOKE_FROM_PUBLIC, function=FUNCTION)
    run_ddl(GRANT_EXECUTE, function=FUNCTION, role=scope.application_role)


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Drop the upkeep function and the partition policies."""
    run_ddl(DROP_FUNCTION, function=FUNCTION)
    revoke_from_application(scope, "partition_policies")
    op.drop_table("partition_policies")
