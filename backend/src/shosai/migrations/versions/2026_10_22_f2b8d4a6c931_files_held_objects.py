"""Objects files holds for other slices, in each home (files step 8c; ADR 0064).

`held_objects` is a task's attachment's bytes: company isolation admits it where the task
is admitted. `files_keys_in_use` now answers for held objects and their previews as for
file rows, so an object a File Manager file shares with an attachment goes only with its
last holder. Uploads gain the purpose `task_attachment`. The sweep role reads held objects
for inv-11's reconciliation and for previews left to make.
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

revision: str = "f2b8d4a6c931"
down_revision: str | None = "d5f1b8c3e7a4"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME

OLD_PURPOSES = (
    "'file_manager', 'recording', 'leo_attachment', 'ticket_attachment', 'workspace_upload', "
    "'app_build'"
)
PURPOSES = f"{OLD_PURPOSES}, 'task_attachment'"
# Владелец таблиц отвечает, какие ключи ещё названы строками, в обход RLS; строк не отдаёт.
KEYS_IN_USE = """
CREATE OR REPLACE FUNCTION files_keys_in_use(keys text[])
RETURNS SETOF text
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
    SELECT object_key FROM storage_files WHERE object_key = ANY(keys)
    UNION
    SELECT object_key FROM held_objects WHERE object_key = ANY(keys)
    UNION
    SELECT preview_key FROM held_objects WHERE preview_key = ANY(keys)
$$
"""
FILES_KEYS_IN_USE = """
CREATE OR REPLACE FUNCTION files_keys_in_use(keys text[])
RETURNS SETOF text
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
    SELECT DISTINCT object_key FROM storage_files WHERE object_key = ANY(keys)
$$
"""


def check(sql: str, name: str) -> sa.CheckConstraint:
    """A check constraint of `held_objects` named by the project's convention."""
    return sa.CheckConstraint(sql, name=op.f(f"ck_held_objects_{name}"))


def moment(name: str) -> sa.Column[datetime]:
    """The creation moment, now by default."""
    return sa.Column(name, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Create held objects, name their keys in use and allow the new purpose."""
    op.create_table(
        "held_objects",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=True),
        sa.Column("holder", sa.Text(), nullable=False),
        sa.Column("upload_id", sa.Uuid(), nullable=True),
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("preview_key", sa.Text(), nullable=True),
        sa.Column("preview_state", sa.Text(), server_default="none", nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("content_type", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        moment("created_at"),
        check("holder IN ('task_attachment')", "holder_known"),
        check("preview_state IN ('none', 'pending', 'made', 'failed')", "preview_state_known"),
        check("(preview_state = 'made') = (preview_key IS NOT NULL)", "preview_when_made"),
        check("length(filename) BETWEEN 1 AND 500", "filename_length"),
        check("length(content_type) BETWEEN 1 AND 255", "type_length"),
        check("size_bytes >= 0", "size_not_negative"),
        check("length(object_key) BETWEEN 1 AND 1024", "key_length"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_held_objects")),
    )
    op.create_index("ix_held_objects_user", "held_objects", ["user_id"])
    op.create_index(
        "ix_held_objects_org",
        "held_objects",
        ["org_id"],
        postgresql_where=sa.text("org_id IS NOT NULL"),
    )
    op.create_index("ix_held_objects_object_key", "held_objects", ["object_key"])
    op.create_index(
        "ix_held_objects_preview_key",
        "held_objects",
        ["preview_key"],
        postgresql_where=sa.text("preview_key IS NOT NULL"),
    )
    op.create_index(
        "uq_held_objects_upload",
        "held_objects",
        ["upload_id"],
        unique=True,
        postgresql_where=sa.text("upload_id IS NOT NULL"),
    )
    op.create_index(
        "ix_held_objects_preview_pending",
        "held_objects",
        ["created_at"],
        postgresql_where=sa.text("preview_state = 'pending'"),
    )
    enable_company_isolation("held_objects")
    grant_to_application(scope, "held_objects")
    grant_to_sweeper("held_objects", ("SELECT",))
    op.drop_constraint(op.f("ck_uploads_purpose_known"), "uploads", type_="check")
    op.create_check_constraint(
        op.f("ck_uploads_purpose_known"), "uploads", f"purpose IN ({PURPOSES})"
    )
    op.execute(KEYS_IN_USE)


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Drop held objects; the keys in use and the purposes go back to the files' alone."""
    op.execute(FILES_KEYS_IN_USE)
    op.drop_constraint(op.f("ck_uploads_purpose_known"), "uploads", type_="check")
    op.create_check_constraint(
        op.f("ck_uploads_purpose_known"), "uploads", f"purpose IN ({OLD_PURPOSES})"
    )
    revoke_from_sweeper("held_objects")
    revoke_from_application(scope, "held_objects")
    disable_company_isolation("held_objects")
    op.drop_table("held_objects")
