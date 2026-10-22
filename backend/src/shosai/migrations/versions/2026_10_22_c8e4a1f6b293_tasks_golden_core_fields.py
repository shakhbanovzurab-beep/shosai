"""The task's fields of the Kanban golden core (tasks step 3a; TK-D12, ADR 0060).

A start day only with a due day and not after it, a recurrence of a known kind and Leo's
marks from a closed set. One next task per completed recurring task, so a repeated
completion or a redelivery makes it once.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from shosai.core.db.migration_scope import EVERY_HOME, MigrationScope, runs_in

revision: str = "c8e4a1f6b293"
down_revision: str | None = "b3d9e5a7c142"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME

CHECKS = (
    ("range", "starts_on IS NULL OR (due_on IS NOT NULL AND starts_on <= due_on)"),
    (
        "recurrence_known",
        "recurrence IS NULL OR recurrence ->> 'every' IN ('day', 'week', 'month')",
    ),
    ("leo_fields_known", "leo_fields <@ ARRAY['assignee', 'due', 'priority']::text[]"),
)


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Add the start day, the recurrence, Leo's marks and the link to the completed one."""
    op.add_column("tasks", sa.Column("starts_on", sa.Date(), nullable=True))
    op.add_column(
        "tasks", sa.Column("recurrence", postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )
    op.add_column(
        "tasks",
        sa.Column(
            "leo_fields",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
    )
    op.add_column("tasks", sa.Column("recurred_from_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_tasks_recurred_from_id_tasks"),
        "tasks",
        "tasks",
        ["recurred_from_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "uq_tasks_recurred_from",
        "tasks",
        ["recurred_from_id"],
        unique=True,
        postgresql_where=sa.text("recurred_from_id IS NOT NULL"),
    )
    for name, sql in CHECKS:
        op.create_check_constraint(op.f(f"ck_tasks_{name}"), "tasks", sql)


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Drop the golden core's fields of tasks."""
    for name, _ in reversed(CHECKS):
        op.drop_constraint(op.f(f"ck_tasks_{name}"), "tasks", type_="check")
    op.drop_index("uq_tasks_recurred_from", table_name="tasks")
    op.drop_constraint(op.f("fk_tasks_recurred_from_id_tasks"), "tasks", type_="foreignkey")
    op.drop_column("tasks", "recurred_from_id")
    op.drop_column("tasks", "leo_fields")
    op.drop_column("tasks", "recurrence")
    op.drop_column("tasks", "starts_on")
