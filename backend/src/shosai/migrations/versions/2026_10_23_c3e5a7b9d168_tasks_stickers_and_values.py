"""Stickers, their states, their places on boards and tasks' values in each home (tasks step 4s;
TK-D12, KG-D4, §3.15).

A sticker belongs to the owner of the boards it is on — a person now, a workspace once
workspace boards come — under company isolation, its states with it in their order. A
board places stickers in order, each shown on its cards or not, and keeps which system
fields its cards show and what its stopwatch does. A task's value of a sticker is one of a
state of that very sticker, a number or a text; it goes with the task, the sticker or the
state. Erasing a person's account keeps their values on workspace tasks as lines of those
tasks' descriptions (`tasks_keep_sticker_values`, §3.15).
"""

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from shosai.core.db.migration_scope import (
    EVERY_HOME,
    FunctionArgument,
    MigrationScope,
    disable_company_isolation,
    disable_user_isolation,
    drop_function,
    enable_company_isolation,
    enable_user_isolation,
    grant_to_application,
    open_function,
    revoke_from_application,
    runs_in,
)

revision: str = "c3e5a7b9d168"
down_revision: str | None = "b7d1f3a9c524"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME

COLORS = "'gray', 'red', 'orange', 'amber', 'green', 'teal', 'blue', 'violet', 'pink'"
KEEP_VALUES = "tasks_keep_sticker_values"
KEEP_VALUES_ARGUMENTS: tuple[FunctionArgument, ...] = ("uuid",)
# Уходя с аккаунтом, поля человека оставляют свои значения на задачах пространств строками
# описания; владелец таблиц видит задачи всех пространств, в обход RLS.
KEEP_VALUES_FUNCTION = """
CREATE FUNCTION tasks_keep_sticker_values(person uuid)
RETURNS integer
LANGUAGE sql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
    WITH kept AS (
        SELECT v.task_id,
               string_agg(
                   s.name || ': ' || coalesce(st.name, trim_scale(v.number)::text, v.text),
                   E'\\n' ORDER BY s.created_at, s.id
               ) AS lines
        FROM task_sticker_values v
        JOIN stickers s ON s.id = v.sticker_id
        LEFT JOIN sticker_states st ON st.id = v.state_id
        WHERE s.user_id = person AND s.org_id IS NULL AND v.org_id IS NOT NULL
        GROUP BY v.task_id
    ), changed AS (
        UPDATE tasks t
        SET description = left(
                CASE WHEN t.description = '' THEN k.lines
                     ELSE t.description || E'\\n\\n' || k.lines END,
                10000
            ),
            updated_at = now()
        FROM kept k
        WHERE t.id = k.task_id
        RETURNING t.id
    )
    SELECT count(*)::integer FROM changed
$$
"""
COMPANY = ("stickers", "sticker_states", "task_sticker_values")
# Новая доска: исполнитель, срок и приоритет видны; секундомер перезапускается и стоит у готового.
SYSTEM_VISIBILITY = sa.text(
    '\'{"assignee": true, "due": true, "priority": true, "recurrence": false, '
    '"stopwatch": false, "timer": false, "time_tracking": false}\'::jsonb'
)
AUTOMATIONS = sa.text(
    '\'{"start_on_arrival": false, "restart_on_move": true, "stop_on_done": true}\'::jsonb'
)


def check(table: str, sql: str, name: str) -> sa.CheckConstraint:
    """A check constraint named by the project's convention."""
    return sa.CheckConstraint(sql, name=op.f(f"ck_{table}_{name}"))


def moment(name: str) -> sa.Column[datetime]:
    """A moment, now by default."""
    return sa.Column(name, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)


def owner() -> tuple[sa.Column[UUID], sa.Column[UUID]]:
    """The person, and the workspace a row belongs to, if any."""
    return (
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=True),
    )


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Create stickers, states, their places, values and the boards' field settings."""
    create_stickers()
    create_board_stickers()
    create_values()
    op.add_column(
        "boards",
        sa.Column(
            "system_stickers", postgresql.JSONB(), nullable=False,
            server_default=SYSTEM_VISIBILITY,
        ),
    )  # fmt: skip
    op.add_column(
        "boards",
        sa.Column(
            "stopwatch_automations", postgresql.JSONB(), nullable=False,
            server_default=AUTOMATIONS,
        ),
    )  # fmt: skip
    for table in COMPANY:
        enable_company_isolation(table)
        grant_to_application(scope, table)
    enable_user_isolation("board_stickers")
    grant_to_application(scope, "board_stickers")
    op.execute(KEEP_VALUES_FUNCTION)
    open_function(KEEP_VALUES, KEEP_VALUES_ARGUMENTS, (scope.application_role,))


def create_stickers() -> None:
    """Stickers and their states in order."""
    op.create_table(
        "stickers",
        sa.Column("id", sa.Uuid(), nullable=False),
        *owner(),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        moment("created_at"),
        check("stickers", "kind IN ('states', 'number', 'text')", "kind_known"),
        check("stickers", "length(name) BETWEEN 1 AND 40", "name_length"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stickers")),
    )
    op.create_index("ix_stickers_user", "stickers", ["user_id"])
    op.create_index(
        "ix_stickers_org", "stickers", ["org_id"], postgresql_where=sa.text("org_id IS NOT NULL")
    )
    op.create_table(
        "sticker_states",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("sticker_id", sa.Uuid(), nullable=False),
        *owner(),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("color", sa.Text(), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        check("sticker_states", "length(name) BETWEEN 1 AND 40", "name_length"),
        check("sticker_states", f"color IN ({COLORS})", "color_known"),
        check("sticker_states", "position BETWEEN 0 AND 19", "position_range"),
        sa.ForeignKeyConstraint(
            ["sticker_id"], ["stickers.id"], name=op.f("fk_sticker_states_sticker_id_stickers"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sticker_states")),
        sa.UniqueConstraint("sticker_id", "id", name=op.f("uq_sticker_states_sticker_state")),
        sa.UniqueConstraint(
            "sticker_id", "position", name=op.f("uq_sticker_states_position"),
            deferrable=True, initially="DEFERRED",
        ),
    )  # fmt: skip


def create_board_stickers() -> None:
    """Where a board shows its stickers."""
    op.create_table(
        "board_stickers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("board_id", sa.Uuid(), nullable=False),
        sa.Column("sticker_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("visible", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        check("board_stickers", "position BETWEEN 0 AND 19", "position_range"),
        sa.ForeignKeyConstraint(
            ["board_id"], ["boards.id"], name=op.f("fk_board_stickers_board_id_boards"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["sticker_id"], ["stickers.id"], name=op.f("fk_board_stickers_sticker_id_stickers"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_board_stickers")),
        sa.UniqueConstraint("board_id", "sticker_id", name=op.f("uq_board_stickers_placed")),
        sa.UniqueConstraint(
            "board_id", "position", name=op.f("uq_board_stickers_position"),
            deferrable=True, initially="DEFERRED",
        ),
    )  # fmt: skip
    op.create_index("ix_board_stickers_sticker", "board_stickers", ["sticker_id"])
    op.create_index("ix_board_stickers_user", "board_stickers", ["user_id"])


def create_values() -> None:
    """Tasks' values of stickers."""
    op.create_table(
        "task_sticker_values",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("sticker_id", sa.Uuid(), nullable=False),
        *owner(),
        sa.Column("state_id", sa.Uuid(), nullable=True),
        sa.Column("number", sa.Numeric(14, 2), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        moment("updated_at"),
        check(
            "task_sticker_values",
            "num_nonnulls(state_id, number, text) = 1",
            "one_value",
        ),
        check(
            "task_sticker_values", "text IS NULL OR length(text) BETWEEN 1 AND 200", "text_length"
        ),
        sa.ForeignKeyConstraint(
            ["task_id"], ["tasks.id"], name=op.f("fk_task_sticker_values_task_id_tasks"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["sticker_id"], ["stickers.id"],
            name=op.f("fk_task_sticker_values_sticker_id_stickers"), ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["sticker_id", "state_id"], ["sticker_states.sticker_id", "sticker_states.id"],
            name=op.f("fk_task_sticker_values_state_of_the_sticker"), ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_task_sticker_values")),
        sa.UniqueConstraint("task_id", "sticker_id", name=op.f("uq_task_sticker_values_value")),
    )  # fmt: skip
    op.create_index("ix_task_sticker_values_sticker", "task_sticker_values", ["sticker_id"])
    op.create_index("ix_task_sticker_values_user", "task_sticker_values", ["user_id"])


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Drop them."""
    drop_function(KEEP_VALUES, KEEP_VALUES_ARGUMENTS)
    revoke_from_application(scope, "board_stickers")
    disable_user_isolation("board_stickers")
    for table in reversed(COMPANY):
        revoke_from_application(scope, table)
        disable_company_isolation(table)
    op.drop_column("boards", "stopwatch_automations")
    op.drop_column("boards", "system_stickers")
    op.drop_table("task_sticker_values")
    op.drop_table("board_stickers")
    op.drop_table("sticker_states")
    op.drop_table("stickers")
