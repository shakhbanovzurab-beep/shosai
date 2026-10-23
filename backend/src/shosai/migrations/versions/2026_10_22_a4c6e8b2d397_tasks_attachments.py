"""A task's attachments and its cover in each home (tasks step 3c; KG-D3, ADR 0064).

An attachment names the object files holds for it, one attachment per held object, and is
deleted with its task. The cover is an attachment of the same task: the pair key holds that,
and the attachment's deletion clears the cover. A deleted attachment, whatever deleted it,
leaves its held object in `task_attachment_releases` by a trigger in the same transaction,
so tasks gives every one back to files. Company isolation covers both tables as the task.
"""

from datetime import datetime

import sqlalchemy as sa
from alembic import op

from shosai.core.db.migration_scope import (
    EVERY_HOME,
    MigrationScope,
    disable_company_isolation,
    enable_company_isolation,
    grant_to_application,
    grant_to_sweeper,
    revoke_from_application,
    revoke_from_sweeper,
    runs_in,
)

revision: str = "a4c6e8b2d397"
down_revision: str | None = "f2b8d4a6c931"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME

TABLES = ("task_attachments", "task_attachment_releases")
RELEASED_FUNCTION = """
CREATE FUNCTION tasks_attachment_released() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog, public AS $$
BEGIN
    INSERT INTO task_attachment_releases (held_object_id, user_id, org_id)
    VALUES (OLD.held_object_id, OLD.user_id, OLD.org_id)
    ON CONFLICT (held_object_id) DO NOTHING;
    RETURN NULL;
END
$$
"""
RELEASED_TRIGGER = """
CREATE TRIGGER task_attachments_released AFTER DELETE ON task_attachments
FOR EACH ROW EXECUTE FUNCTION tasks_attachment_released()
"""


def check(table: str, sql: str, name: str) -> sa.CheckConstraint:
    """A check constraint named by the project's convention."""
    return sa.CheckConstraint(sql, name=op.f(f"ck_{table}_{name}"))


def moment(name: str) -> sa.Column[datetime]:
    """A moment, now by default."""
    return sa.Column(name, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Create attachments, the cover and the queue of held objects to give back."""
    op.create_table(
        "task_attachments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "task_id",
            sa.Uuid(),
            sa.ForeignKey(
                "tasks.id", name=op.f("fk_task_attachments_task_id_tasks"), ondelete="CASCADE"
            ),
            nullable=False,
        ),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=True),
        sa.Column("held_object_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("content_type", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("image", sa.Boolean(), nullable=False),
        sa.Column("added_by", sa.Uuid(), nullable=False),
        moment("added_at"),
        check("task_attachments", "length(name) BETWEEN 1 AND 500", "name_length"),
        check("task_attachments", "length(content_type) BETWEEN 1 AND 255", "type_length"),
        check("task_attachments", "size_bytes >= 0", "size_not_negative"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_task_attachments")),
        sa.UniqueConstraint("held_object_id", name=op.f("uq_task_attachments_held_object_id")),
        sa.UniqueConstraint("task_id", "id", name=op.f("uq_task_attachments_task_id")),
    )
    op.create_index("ix_task_attachments_task_added", "task_attachments", ["task_id", "added_at"])
    op.create_index("ix_task_attachments_user", "task_attachments", ["user_id"])
    op.create_table(
        "task_attachment_releases",
        sa.Column("held_object_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=True),
        moment("created_at"),
        sa.PrimaryKeyConstraint("held_object_id", name=op.f("pk_task_attachment_releases")),
    )
    op.create_index("ix_task_attachment_releases_user", "task_attachment_releases", ["user_id"])
    op.add_column("tasks", sa.Column("cover_attachment_id", sa.Uuid(), nullable=True))
    # Удаление вложения снимает обложку; пара ключей держит обложку вложением той же задачи.
    op.create_foreign_key(
        op.f("fk_tasks_cover_attachment_id_task_attachments"),
        "tasks",
        "task_attachments",
        ["cover_attachment_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        op.f("fk_tasks_cover_of_the_task"),
        "tasks",
        "task_attachments",
        ["id", "cover_attachment_id"],
        ["task_id", "id"],
    )
    for table in TABLES:
        enable_company_isolation(table)
        grant_to_application(scope, table)
    grant_to_sweeper("task_attachment_releases", ("SELECT",))
    op.execute(RELEASED_FUNCTION)
    op.execute(RELEASED_TRIGGER)


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Drop attachments, the cover and the queue."""
    op.execute("DROP TRIGGER task_attachments_released ON task_attachments")
    op.execute("DROP FUNCTION tasks_attachment_released()")
    revoke_from_sweeper("task_attachment_releases")
    for table in reversed(TABLES):
        revoke_from_application(scope, table)
        disable_company_isolation(table)
    op.drop_constraint(op.f("fk_tasks_cover_of_the_task"), "tasks", type_="foreignkey")
    op.drop_constraint(
        op.f("fk_tasks_cover_attachment_id_task_attachments"), "tasks", type_="foreignkey"
    )
    op.drop_column("tasks", "cover_attachment_id")
    op.drop_table("task_attachment_releases")
    op.drop_table("task_attachments")
