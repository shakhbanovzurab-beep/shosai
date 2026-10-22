"""Tasks' tables in each home (tasks step 2; ADR 0059).

`tasks` is the shareable resource `task`: company isolation with workspaces' access policy
guarding personal rows, its assignee the named reader and its meeting the parent (TK-D2).
`meeting_task_sets` carries the meeting's workspace, so company isolation covers it too.
Boards, their columns, where tasks sit and a person's settings are personal by nature.
The sweep role reads `tasks` for the access policy's hourly self-test (inv-14). Titles are
found by trigrams (`pg_trgm`, created by identity's revision `62331a1a0c29`).
"""

from datetime import datetime

import sqlalchemy as sa
from alembic import op

from shosai.core.db.migration_scope import (
    EVERY_HOME,
    MigrationScope,
    disable_company_isolation,
    disable_user_isolation,
    enable_company_isolation,
    enable_user_isolation,
    grant_to_application,
    grant_to_sweeper,
    revoke_from_application,
    revoke_from_sweeper,
    runs_in,
)

revision: str = "b3d9e5a7c142"
down_revision: str | None = "7df9c7f7dc2e"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME

STATUSES = "'todo', 'in_progress', 'done'"
PRIORITIES = "'high', 'medium', 'low'"
SOURCES = "'manual', 'meeting', 'hub', 'mail', 'jira'"
CREATORS = "'person', 'leo', 'meeting', 'sync'"
ICONS = (
    "'briefcase', 'home', 'user', 'heart', 'graduation-cap', 'plane', 'shopping-cart', "
    "'dumbbell', 'rocket', 'book'"
)
OPEN = "status <> 'done'"
COMPANY = ("tasks", "meeting_task_sets")
PERSONAL = ("boards", "board_columns", "task_placements", "task_settings")


def check(table: str, sql: str, name: str) -> sa.CheckConstraint:
    """A check constraint named by the project's convention."""
    return sa.CheckConstraint(sql, name=op.f(f"ck_{table}_{name}"))


def moment(name: str, *, nullable: bool = False) -> sa.Column[datetime]:
    """A timestamp column; creation, update and placing moments default to now."""
    default = sa.func.now() if name in {"created_at", "updated_at", "placed_at"} else None
    return sa.Column(name, sa.DateTime(timezone=True), server_default=default, nullable=nullable)


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Create tasks, the meetings' sets, boards, columns, placements and settings."""
    create_tasks()
    op.create_table(
        "meeting_task_sets",
        sa.Column("meeting_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        moment("touched_at", nullable=True),
        moment("meeting_gone_at", nullable=True),
        moment("created_at"),
        moment("updated_at"),
        check("meeting_task_sets", "revision >= 0", "revision_not_negative"),
        sa.PrimaryKeyConstraint("meeting_id", name=op.f("pk_meeting_task_sets")),
    )
    op.create_index("ix_meeting_task_sets_user", "meeting_task_sets", ["user_id"])
    op.create_index(
        "ix_meeting_task_sets_org",
        "meeting_task_sets",
        ["org_id"],
        postgresql_where=sa.text("org_id IS NOT NULL"),
    )
    create_boards()
    create_placements()
    for table in COMPANY:
        enable_company_isolation(table)
        grant_to_application(scope, table)
    grant_to_sweeper("tasks", ("SELECT",))
    for table in PERSONAL:
        enable_user_isolation(table)
        grant_to_application(scope, table)


def create_tasks() -> None:
    """The one store of tasks, personal and of workspaces."""
    op.create_table(
        "tasks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=True),
        sa.Column("access", sa.Text(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("status", sa.Text(), server_default="todo", nullable=False),
        sa.Column("priority", sa.Text(), nullable=True),
        sa.Column("due_on", sa.Date(), nullable=True),
        moment("completed_at", nullable=True),
        sa.Column("assignee_user_id", sa.Uuid(), nullable=True),
        sa.Column("assignee_name", sa.Text(), nullable=True),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("source", sa.Text(), server_default="manual", nullable=False),
        sa.Column("source_meeting_id", sa.Uuid(), nullable=True),
        sa.Column("source_finding_id", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.Text(), server_default="person", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        moment("created_at"),
        moment("updated_at"),
        check("tasks", "(org_id IS NULL) = (access IS NULL)", "org_with_access"),
        check(
            "tasks",
            "access IS NULL OR access IN ('owner', 'selected', 'organization')",
            "access_known",
        ),
        check("tasks", "length(title) BETWEEN 1 AND 200", "title_length"),
        check("tasks", "length(description) <= 10000", "description_length"),
        check("tasks", f"status IN ({STATUSES})", "status_known"),
        check("tasks", f"priority IS NULL OR priority IN ({PRIORITIES})", "priority_known"),
        check("tasks", "(status = 'done') = (completed_at IS NOT NULL)", "done_when_completed"),
        check("tasks", "assignee_user_id IS NULL OR org_id IS NOT NULL", "member_in_workspace"),
        check(
            "tasks",
            "assignee_name IS NULL OR (assignee_user_id IS NULL"
            " AND length(assignee_name) BETWEEN 1 AND 80)",
            "name_without_member",
        ),
        check("tasks", "project_id IS NULL OR org_id IS NOT NULL", "project_in_workspace"),
        check("tasks", f"source IN ({SOURCES})", "source_known"),
        check("tasks", "(source = 'meeting') = (source_meeting_id IS NOT NULL)", "meeting_source"),
        check(
            "tasks",
            "source_finding_id IS NULL OR source_meeting_id IS NOT NULL",
            "finding_of_meeting",
        ),
        check("tasks", f"created_by IN ({CREATORS})", "creator_known"),
        check("tasks", "version >= 1", "version_positive"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tasks")),
    )
    index_tasks()


def index_tasks() -> None:
    """The ways tasks are reached: by owner, workspace, assignee, meeting, project and title."""
    op.create_index("ix_tasks_user", "tasks", ["user_id"])
    op.create_index(
        "ix_tasks_org", "tasks", ["org_id"], postgresql_where=sa.text("org_id IS NOT NULL")
    )
    op.create_index(
        "ix_tasks_open_user_due", "tasks", ["user_id", "due_on"], postgresql_where=sa.text(OPEN)
    )
    op.create_index(
        "ix_tasks_open_org_due",
        "tasks",
        ["org_id", "due_on"],
        postgresql_where=sa.text("status <> 'done' AND org_id IS NOT NULL"),
    )
    op.create_index(
        "ix_tasks_open_assignee_due",
        "tasks",
        ["assignee_user_id", "due_on"],
        postgresql_where=sa.text("status <> 'done' AND assignee_user_id IS NOT NULL"),
    )
    op.create_index(
        "uq_tasks_meeting_finding",
        "tasks",
        ["source_meeting_id", "source_finding_id"],
        unique=True,
        postgresql_where=sa.text("source_meeting_id IS NOT NULL"),
    )
    op.create_index(
        "ix_tasks_project",
        "tasks",
        ["project_id"],
        postgresql_where=sa.text("project_id IS NOT NULL"),
    )
    op.create_index(
        "ix_tasks_title_trgm",
        "tasks",
        ["title"],
        postgresql_using="gin",
        postgresql_ops={"title": "gin_trgm_ops"},
    )


def create_boards() -> None:
    """A person's boards and their columns."""
    op.create_table(
        "boards",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("icon", sa.Text(), nullable=False),
        sa.Column("revision", sa.BigInteger(), server_default="1", nullable=False),
        moment("created_at"),
        moment("updated_at"),
        check("boards", "length(name) BETWEEN 1 AND 60", "name_length"),
        check("boards", f"icon IN ({ICONS})", "icon_known"),
        check("boards", "revision >= 1", "revision_positive"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_boards")),
    )
    op.create_index("ix_boards_user", "boards", ["user_id", "created_at"])
    op.create_table(
        "board_columns",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("board_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        check("board_columns", "length(title) BETWEEN 1 AND 60", "title_length"),
        check("board_columns", f"kind IN ({STATUSES})", "kind_known"),
        check("board_columns", "position BETWEEN 0 AND 19", "position_range"),
        sa.ForeignKeyConstraint(
            ["board_id"],
            ["boards.id"],
            name=op.f("fk_board_columns_board_id_boards"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_board_columns")),
        sa.UniqueConstraint(
            "board_id",
            "position",
            name=op.f("uq_board_columns_position"),
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.UniqueConstraint("board_id", "id", name=op.f("uq_board_columns_board_column")),
    )
    op.create_index("ix_board_columns_user", "board_columns", ["user_id"])


def create_placements() -> None:
    """Where tasks sit on a person's boards, and the board incoming work lands on."""
    op.create_table(
        "task_placements",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("board_id", sa.Uuid(), nullable=False),
        sa.Column("column_id", sa.Uuid(), nullable=False),
        sa.Column("rank", sa.Text(collation="C"), nullable=False),
        moment("placed_at"),
        check(
            "task_placements",
            "rank ~ '^[0-9A-Za-z]*[1-9A-Za-z]$' AND length(rank) <= 128",
            "rank_format",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.id"],
            name=op.f("fk_task_placements_task_id_tasks"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["board_id"],
            ["boards.id"],
            name=op.f("fk_task_placements_board_id_boards"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["board_id", "column_id"],
            ["board_columns.board_id", "board_columns.id"],
            name=op.f("fk_task_placements_board_id_board_columns"),
        ),
        sa.PrimaryKeyConstraint("user_id", "task_id", name=op.f("pk_task_placements")),
        sa.UniqueConstraint(
            "board_id",
            "column_id",
            "rank",
            name=op.f("uq_task_placements_rank"),
            deferrable=True,
            initially="DEFERRED",
        ),
    )
    op.create_index("ix_task_placements_task", "task_placements", ["task_id"])
    op.create_table(
        "task_settings",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("incoming_board_id", sa.Uuid(), nullable=True),
        moment("updated_at"),
        sa.ForeignKeyConstraint(
            ["incoming_board_id"],
            ["boards.id"],
            name=op.f("fk_task_settings_incoming_board_id_boards"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_task_settings")),
    )
    op.create_index(
        "ix_task_settings_incoming_board",
        "task_settings",
        ["incoming_board_id"],
        postgresql_where=sa.text("incoming_board_id IS NOT NULL"),
    )


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Drop tasks' tables."""
    for table in reversed(PERSONAL):
        revoke_from_application(scope, table)
        disable_user_isolation(table)
    revoke_from_sweeper("tasks")
    for table in reversed(COMPANY):
        revoke_from_application(scope, table)
        disable_company_isolation(table)
    op.drop_table("task_settings")
    op.drop_table("task_placements")
    op.drop_table("board_columns")
    op.drop_table("boards")
    op.drop_table("meeting_task_sets")
    op.drop_table("tasks")
