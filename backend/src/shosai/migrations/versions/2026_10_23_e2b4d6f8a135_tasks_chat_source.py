"""The chat source of tasks in each home (tasks step 4b; TK-D13, §3.10).

A task Leo made from a team chat's message keeps the chat as it was named, the messenger,
the message's moment and its link where the messenger has one, and the chats' connection
until the chat is disconnected. The check ties them to `source = 'chat'`, which belongs to a
workspace's task made by Leo. A downgrade keeps the chat tasks as hand-made ones without
their chat line.
"""

from typing import Any

import sqlalchemy as sa
from alembic import op

from shosai.core.db.migration_scope import EVERY_HOME, MigrationScope, runs_in

revision: str = "e2b4d6f8a135"
down_revision: str | None = "d9f2b4c6e813"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME

SOURCES_BEFORE = "source IN ('manual', 'meeting', 'hub', 'mail', 'jira')"
SOURCES_AFTER = "source IN ('manual', 'meeting', 'hub', 'mail', 'jira', 'chat')"
CHAT_SOURCE = (
    "(source = 'chat') = (source_chat_messenger IS NOT NULL)"
    " AND (source = 'chat') = (source_chat_title IS NOT NULL)"
    " AND (source = 'chat') = (source_chat_message_at IS NOT NULL)"
    " AND (source = 'chat' OR (source_chat_connection_id IS NULL"
    " AND source_chat_message_url IS NULL))"
    " AND (source <> 'chat' OR (org_id IS NOT NULL AND created_by = 'leo'))"
)
CHECKS = (
    ("chat_source", CHAT_SOURCE),
    (
        "chat_messenger_known",
        "source_chat_messenger IS NULL OR source_chat_messenger IN ('telegram', 'slack')",
    ),
    (
        "chat_title_length",
        "source_chat_title IS NULL OR length(source_chat_title) BETWEEN 1 AND 255",
    ),
    (
        "chat_link_length",
        "source_chat_message_url IS NULL OR length(source_chat_message_url) <= 2048",
    ),
)
COLUMNS = (
    "source_chat_connection_id", "source_chat_messenger", "source_chat_title",
    "source_chat_message_url", "source_chat_message_at",
)  # fmt: skip


def chat_columns() -> tuple[sa.Column[Any], ...]:
    """The chat a task came from, empty on every other task."""
    return (
        sa.Column("source_chat_connection_id", sa.Uuid(), nullable=True),
        sa.Column("source_chat_messenger", sa.Text(), nullable=True),
        sa.Column("source_chat_title", sa.Text(), nullable=True),
        sa.Column("source_chat_message_url", sa.Text(), nullable=True),
        sa.Column("source_chat_message_at", sa.DateTime(timezone=True), nullable=True),
    )


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Add the chat source's columns, its kind and its checks."""
    del scope
    for column in chat_columns():
        op.add_column("tasks", column)
    op.drop_constraint(op.f("ck_tasks_source_known"), "tasks", type_="check")
    op.create_check_constraint(op.f("ck_tasks_source_known"), "tasks", SOURCES_AFTER)
    for name, sql in CHECKS:
        op.create_check_constraint(op.f(f"ck_tasks_{name}"), "tasks", sql)


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Drop them; a chat task stays as a hand-made one."""
    del scope
    for name, _ in reversed(CHECKS):
        op.drop_constraint(op.f(f"ck_tasks_{name}"), "tasks", type_="check")
    op.execute("UPDATE tasks SET source = 'manual' WHERE source = 'chat'")
    op.drop_constraint(op.f("ck_tasks_source_known"), "tasks", type_="check")
    op.create_check_constraint(op.f("ck_tasks_source_known"), "tasks", SOURCES_BEFORE)
    for name in reversed(COLUMNS):
        op.drop_column("tasks", name)
