"""A task's checklist and its comments in each home (tasks step 3b; TK-D12, ADR 0060).

Both are children of a task, deleted with it, and carry its owner and workspace, so company
isolation covers them as it covers the task. A task holds at most 100 subtasks in an order
kept by fractional keys, unique at commit so a respacing can rewrite them in any order; a
comment is plain text of up to 5 000 characters by its author, paged newest first by its
time-ordered id.
"""

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from alembic import op

from shosai.core.db.migration_scope import (
    EVERY_HOME,
    MigrationScope,
    disable_company_isolation,
    enable_company_isolation,
    grant_to_application,
    revoke_from_application,
    runs_in,
)

revision: str = "d5f1b8c3e7a4"
down_revision: str | None = "c8e4a1f6b293"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME

TABLES = ("task_subtasks", "task_comments")


def check(table: str, sql: str, name: str) -> sa.CheckConstraint:
    """A check constraint named by the project's convention."""
    return sa.CheckConstraint(sql, name=op.f(f"ck_{table}_{name}"))


def moment(name: str, *, nullable: bool = False) -> sa.Column[datetime]:
    """A timestamp column; creation and update moments default to now."""
    default = sa.func.now() if name in {"created_at", "updated_at"} else None
    return sa.Column(name, sa.DateTime(timezone=True), server_default=default, nullable=nullable)


def task_columns(table: str) -> tuple[sa.Column[UUID], ...]:
    """The task a row belongs to, deleted with it, and the task's owner and workspace."""
    return (
        sa.Column(
            "task_id",
            sa.Uuid(),
            sa.ForeignKey("tasks.id", name=op.f(f"fk_{table}_task_id_tasks"), ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=True),
    )


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Create the subtasks and the comments of tasks."""
    op.create_table(
        "task_subtasks",
        sa.Column("id", sa.Uuid(), nullable=False),
        *task_columns("task_subtasks"),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("done", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("rank", sa.Text(collation="C"), nullable=False),
        moment("created_at"),
        moment("updated_at"),
        check("task_subtasks", "length(title) BETWEEN 1 AND 200", "title_length"),
        check(
            "task_subtasks",
            "rank ~ '^[0-9A-Za-z]*[1-9A-Za-z]$' AND length(rank) <= 128",
            "rank_format",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_task_subtasks")),
        sa.UniqueConstraint(
            "task_id",
            "rank",
            name=op.f("uq_task_subtasks_rank"),
            deferrable=True,
            initially="DEFERRED",
        ),
    )
    op.create_index("ix_task_subtasks_user", "task_subtasks", ["user_id"])
    op.create_table(
        "task_comments",
        sa.Column("id", sa.Uuid(), nullable=False),
        *task_columns("task_comments"),
        sa.Column("author_user_id", sa.Uuid(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        moment("created_at"),
        moment("edited_at", nullable=True),
        check("task_comments", "length(body) BETWEEN 1 AND 5000", "body_length"),
        check("task_comments", "edited_at IS NULL OR edited_at >= created_at", "edited_after"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_task_comments")),
    )
    op.create_index("ix_task_comments_task", "task_comments", ["task_id", "id"])
    op.create_index("ix_task_comments_user", "task_comments", ["user_id"])
    for table in TABLES:
        enable_company_isolation(table)
        grant_to_application(scope, table)


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Drop the subtasks and the comments of tasks."""
    for table in reversed(TABLES):
        revoke_from_application(scope, table)
        disable_company_isolation(table)
    op.drop_table("task_comments")
    op.drop_table("task_subtasks")
