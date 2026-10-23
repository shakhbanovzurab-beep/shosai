"""Time on a task in each home: the stopwatch's spans, the timer, plan and fact (tasks step 4a;
ADR 0061, §3.9).

A span is a stretch the task's stopwatch ran, in a column of the board where it ran or
unplaced, under company isolation with the task's owner and workspace; a partial unique
index keeps one running span per task. The task's row keeps what its spans sum to — since
when it runs, its closed time in all and per column — written with them under the task's
lock, so a board reads its cards' stopwatches without a subquery each. The timer — a length
with its end, or with what is left while paused — and plan and fact in minutes are columns
of the task, each checked. The boards' stopwatch automations get their shape checked, and a
cleared schedule is SQL NULL, never JSON null, which the old check let through. A task
landing on a person's incoming board starts through `tasks_start_landed`, as the board's
read runs in the person's own scope, where row-level security writes no workspace's rows.
"""

from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from shosai.core.db.migration_scope import (
    EVERY_HOME,
    FunctionArgument,
    MigrationScope,
    disable_company_isolation,
    drop_function,
    enable_company_isolation,
    grant_to_application,
    open_function,
    revoke_from_application,
    runs_in,
)

revision: str = "d9f2b4c6e813"
down_revision: str | None = "c3e5a7b9d168"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME

TIMER_MAX_MS = 365 * 24 * 60 * 60_000
TRACKED_MAX = 6_000_000
AUTOMATION_KEYS = "ARRAY['start_on_arrival', 'restart_on_move', 'stop_on_done']"
START_LANDED = "tasks_start_landed"
START_LANDED_ARGUMENTS: tuple[FunctionArgument, ...] = ("uuid[]", "uuid[]", "timestamptz")
# Доска входящих принимает задачи в чтении, в области самого человека: запуск секундомера
# приземлившейся задачи пространства идёт через владельца таблиц, в обход RLS, и только
# для задач, что пришли этому человеку и лежат в этой колонке его доски.
START_LANDED_FUNCTION = """
CREATE FUNCTION tasks_start_landed(landed_task_ids uuid[], landed_column_ids uuid[],
                                   landed_at timestamptz)
RETURNS integer
LANGUAGE sql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
    WITH started AS (
        INSERT INTO task_clock_spans (id, task_id, user_id, org_id, column_id, started_at)
        SELECT uuidv7(), t.id, t.user_id, t.org_id, landed.column_id, landed_at
        FROM unnest(landed_task_ids, landed_column_ids) AS landed (task_id, column_id)
        JOIN tasks t ON t.id = landed.task_id
        JOIN task_placements p
          ON p.task_id = t.id AND p.user_id = app_user_id() AND p.column_id = landed.column_id
        WHERE t.status <> 'done' AND t.source <> 'jira'
          AND ((t.org_id IS NULL AND t.user_id = app_user_id() AND t.source = 'meeting')
               OR (t.org_id = ANY (app_member_org_ids()) AND t.assignee_user_id = app_user_id()))
        ON CONFLICT (task_id) WHERE stopped_at IS NULL DO NOTHING
        RETURNING task_id
    ), summed AS (
        UPDATE tasks
        SET stopwatch_since = landed_at,
            stopwatch_total_ms = coalesce(stopwatch_total_ms, 0),
            stopwatch_by_column = coalesce(stopwatch_by_column, '{}'::jsonb)
        FROM started
        WHERE tasks.id = started.task_id
        RETURNING 1
    )
    SELECT count(*)::integer FROM summed
$$
"""
# Снятое расписание было JSON null, который проверка пропускала: теперь только объект или NULL.
RECURRENCE_ANY = "recurrence IS NULL OR recurrence ->> 'every' IN ('day', 'week', 'month')"
RECURRENCE_OBJECT = (
    "recurrence IS NULL OR (jsonb_typeof(recurrence) = 'object'"
    " AND recurrence ->> 'every' IN ('day', 'week', 'month'))"
)
CHECKS = (
    (
        "tasks",
        "timer_shape",
        "(timer_length_ms IS NULL AND timer_ends_at IS NULL AND timer_paused_left_ms IS NULL) "
        f"OR (timer_length_ms BETWEEN 60000 AND {TIMER_MAX_MS} "
        "AND num_nonnulls(timer_ends_at, timer_paused_left_ms) = 1)",
    ),
    (
        "tasks",
        "stopwatch_shape",
        "(stopwatch_total_ms IS NULL) = (stopwatch_by_column IS NULL) "
        "AND (stopwatch_since IS NULL OR stopwatch_total_ms IS NOT NULL) "
        "AND (stopwatch_total_ms IS NULL OR stopwatch_total_ms >= 0) "
        "AND (stopwatch_by_column IS NULL OR jsonb_typeof(stopwatch_by_column) = 'object')",
    ),
    ("tasks", "plan_range", f"plan_minutes IS NULL OR plan_minutes BETWEEN 0 AND {TRACKED_MAX}"),
    ("tasks", "fact_range", f"fact_minutes IS NULL OR fact_minutes BETWEEN 0 AND {TRACKED_MAX}"),
    (
        "boards",
        "automations_shape",
        f"stopwatch_automations ?& {AUTOMATION_KEYS} "
        f"AND stopwatch_automations - {AUTOMATION_KEYS} = '{{}}'::jsonb "
        "AND jsonb_typeof(stopwatch_automations -> 'start_on_arrival') = 'boolean' "
        "AND jsonb_typeof(stopwatch_automations -> 'restart_on_move') = 'boolean' "
        "AND jsonb_typeof(stopwatch_automations -> 'stop_on_done') = 'boolean'",
    ),
)
TASK_COLUMNS = (
    "stopwatch_since", "stopwatch_total_ms", "stopwatch_by_column", "timer_length_ms",
    "timer_ends_at", "timer_paused_left_ms", "plan_minutes", "fact_minutes",
)  # fmt: skip


def task_columns() -> tuple[sa.Column[Any], ...]:
    """The task's stopwatch summed from its spans, its timer, plan and fact, all empty at
    first."""
    return (
        sa.Column("stopwatch_since", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stopwatch_total_ms", sa.BigInteger(), nullable=True),
        sa.Column("stopwatch_by_column", postgresql.JSONB(), nullable=True),
        sa.Column("timer_length_ms", sa.BigInteger(), nullable=True),
        sa.Column("timer_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("timer_paused_left_ms", sa.BigInteger(), nullable=True),
        sa.Column("plan_minutes", sa.Integer(), nullable=True),
        sa.Column("fact_minutes", sa.Integer(), nullable=True),
    )


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Create the spans, the tasks' timer, plan and fact, and the automations' check."""
    op.create_table(
        "task_clock_spans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=True),
        sa.Column("column_id", sa.Uuid(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "stopped_at IS NULL OR stopped_at >= started_at",
            name=op.f("ck_task_clock_spans_ordered"),
        ),
        sa.ForeignKeyConstraint(
            ["task_id"], ["tasks.id"], name=op.f("fk_task_clock_spans_task_id_tasks"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_task_clock_spans")),
    )  # fmt: skip
    op.create_index(
        "uq_task_clock_spans_running", "task_clock_spans", ["task_id"], unique=True,
        postgresql_where=sa.text("stopped_at IS NULL"),
    )  # fmt: skip
    op.create_index("ix_task_clock_spans_task", "task_clock_spans", ["task_id", "started_at"])
    op.create_index("ix_task_clock_spans_user", "task_clock_spans", ["user_id"])
    enable_company_isolation("task_clock_spans")
    grant_to_application(scope, "task_clock_spans")
    for column in task_columns():
        op.add_column("tasks", column)
    for table, name, sql in CHECKS:
        op.create_check_constraint(op.f(f"ck_{table}_{name}"), table, sql)
    op.execute("UPDATE tasks SET recurrence = NULL WHERE recurrence = 'null'::jsonb")
    op.drop_constraint(op.f("ck_tasks_recurrence_known"), "tasks", type_="check")
    op.create_check_constraint(op.f("ck_tasks_recurrence_known"), "tasks", RECURRENCE_OBJECT)
    op.execute(START_LANDED_FUNCTION)
    open_function(START_LANDED, START_LANDED_ARGUMENTS, (scope.application_role,))


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Drop them."""
    drop_function(START_LANDED, START_LANDED_ARGUMENTS)
    op.drop_constraint(op.f("ck_tasks_recurrence_known"), "tasks", type_="check")
    op.create_check_constraint(op.f("ck_tasks_recurrence_known"), "tasks", RECURRENCE_ANY)
    for table, name, _ in reversed(CHECKS):
        op.drop_constraint(op.f(f"ck_{table}_{name}"), table, type_="check")
    for name in reversed(TASK_COLUMNS):
        op.drop_column("tasks", name)
    revoke_from_application(scope, "task_clock_spans")
    disable_company_isolation("task_clock_spans")
    op.drop_table("task_clock_spans")
