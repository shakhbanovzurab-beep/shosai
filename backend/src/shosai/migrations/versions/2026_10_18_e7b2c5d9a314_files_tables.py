"""Files' tables in each home (files step 2; ADR 0055).

`storage_files` is a shareable resource: company isolation with workspaces' access policy
guarding personal rows (WS-D2); its object key is the full key, legacy keys verbatim, and
several rows may share one (FL-D4). `file_folders`, `uploads` and `storage_usage` are
personal. `object_deletions` holds keys whose last row is gone until the bucket confirms
their deletion; it names keys only. Usage counters can never fall below zero. Whether a
key is still named by any row — of any owner, whatever row-level security shows — is
answered by `files_keys_in_use`, which returns keys and no rows.
"""

from datetime import datetime

import sqlalchemy as sa
from alembic import op

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
    grant_to_sweeper,
    open_function,
    revoke_from_application,
    revoke_from_sweeper,
    runs_in,
)

revision: str = "e7b2c5d9a314"
down_revision: str | None = "d4a8b1f3e602"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME

PURPOSES = (
    "'file_manager', 'recording', 'leo_attachment', 'ticket_attachment', 'workspace_upload', "
    "'app_build'"
)
STATES = "'pending', 'ready', 'claimed', 'rejected', 'expired'"
PERSONAL = ("file_folders", "uploads", "storage_usage")
KEYS_IN_USE = "files_keys_in_use"
KEYS_IN_USE_ARGUMENTS: tuple[FunctionArgument, ...] = ("text[]",)
# Владелец таблиц отвечает, какие ключи ещё названы строками, в обход RLS; строк не отдаёт.
KEYS_IN_USE_FUNCTION = """
CREATE FUNCTION files_keys_in_use(keys text[])
RETURNS SETOF text
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
    SELECT DISTINCT object_key FROM storage_files WHERE object_key = ANY(keys)
$$
"""


def check(table: str, sql: str, name: str) -> sa.CheckConstraint:
    """A check constraint named by the project's convention."""
    return sa.CheckConstraint(sql, name=op.f(f"ck_{table}_{name}"))


def moment(name: str, *, nullable: bool = False) -> sa.Column[datetime]:
    """A timestamp column; creation and update moments default to now."""
    default = sa.func.now() if name in {"created_at", "updated_at", "modified_at"} else None
    return sa.Column(name, sa.DateTime(timezone=True), server_default=default, nullable=nullable)


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Create the folders, files, uploads, usage and pending object deletions."""
    op.create_table(
        "file_folders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("leo", sa.Boolean(), server_default=sa.false(), nullable=False),
        moment("created_at"),
        moment("updated_at"),
        check("file_folders", "length(name) BETWEEN 1 AND 500", "name_length"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_file_folders")),
    )
    op.create_index("ix_file_folders_user", "file_folders", ["user_id"])
    create_files()
    create_uploads()
    op.create_table(
        "storage_usage",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("used_bytes", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("reserved_bytes", sa.BigInteger(), server_default="0", nullable=False),
        moment("over_limit_since", nullable=True),
        sa.Column("reminders_sent", sa.SmallInteger(), server_default="0", nullable=False),
        moment("updated_at"),
        check("storage_usage", "used_bytes >= 0 AND reserved_bytes >= 0", "not_negative"),
        check("storage_usage", "reminders_sent BETWEEN 0 AND 3", "reminders_range"),
        check(
            "storage_usage",
            "over_limit_since IS NOT NULL OR reminders_sent = 0",
            "reminders_while_over",
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_storage_usage")),
    )
    op.create_table(
        "object_deletions",
        sa.Column("object_key", sa.Text(), nullable=False),
        moment("created_at"),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        check("object_deletions", "length(object_key) BETWEEN 1 AND 1024", "key_length"),
        sa.PrimaryKeyConstraint("object_key", name=op.f("pk_object_deletions")),
    )
    enable_company_isolation("storage_files")
    grant_to_application(scope, "storage_files")
    grant_to_sweeper("storage_files", ("SELECT",))
    for table in PERSONAL:
        enable_user_isolation(table)
        grant_to_application(scope, table)
    grant_to_application(scope, "object_deletions", ("SELECT", "INSERT", "UPDATE", "DELETE"))
    op.execute(KEYS_IN_USE_FUNCTION)
    open_function(KEYS_IN_USE, KEYS_IN_USE_ARGUMENTS, (scope.application_role,))


def create_files() -> None:
    """The File Manager's files of people and workspaces."""
    op.create_table(
        "storage_files",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=True),
        sa.Column("access", sa.Text(), nullable=True),
        sa.Column("folder_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("content_type", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("sha256", sa.LargeBinary(), nullable=True),
        sa.Column("starred", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("leo_on", sa.Boolean(), server_default=sa.false(), nullable=False),
        moment("created_at"),
        moment("modified_at"),
        moment("deleted_at", nullable=True),
        check("storage_files", "(org_id IS NULL) = (access IS NULL)", "org_with_access"),
        check(
            "storage_files",
            "access IS NULL OR access IN ('owner', 'selected', 'organization')",
            "access_known",
        ),
        check("storage_files", "org_id IS NULL OR folder_id IS NULL", "folders_personal"),
        check("storage_files", "length(name) BETWEEN 1 AND 500", "name_length"),
        check("storage_files", "length(content_type) BETWEEN 1 AND 255", "type_length"),
        check("storage_files", "size_bytes >= 0", "size_not_negative"),
        check("storage_files", "length(object_key) BETWEEN 1 AND 1024", "key_length"),
        check("storage_files", "sha256 IS NULL OR octet_length(sha256) = 32", "sha256_length"),
        sa.ForeignKeyConstraint(
            ["folder_id"],
            ["file_folders.id"],
            name=op.f("fk_storage_files_folder_id_file_folders"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_storage_files")),
    )
    op.create_index("ix_storage_files_user", "storage_files", ["user_id"])
    op.create_index("ix_storage_files_org", "storage_files", ["org_id"])
    op.create_index("ix_storage_files_folder", "storage_files", ["folder_id"])
    op.create_index("ix_storage_files_object_key", "storage_files", ["object_key"])
    op.create_index(
        "ix_storage_files_hidden",
        "storage_files",
        ["deleted_at"],
        postgresql_where=sa.text("deleted_at IS NOT NULL"),
    )


def create_uploads() -> None:
    """Uploads straight to the bucket, from creation to their claim."""
    op.create_table(
        "uploads",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=True),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("multipart_id", sa.Text(), nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("content_type", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("state", sa.Text(), server_default="pending", nullable=False),
        moment("created_at"),
        moment("expires_at"),
        moment("finished_at", nullable=True),
        check("uploads", f"purpose IN ({PURPOSES})", "purpose_known"),
        check("uploads", f"state IN ({STATES})", "state_known"),
        check("uploads", "size_bytes > 0", "size_positive"),
        check("uploads", "length(filename) BETWEEN 1 AND 255", "filename_length"),
        check("uploads", "length(content_type) BETWEEN 1 AND 255", "type_length"),
        check("uploads", "length(object_key) BETWEEN 1 AND 1024", "key_length"),
        check("uploads", "expires_at > created_at", "expiry_after_creation"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_uploads")),
    )
    op.create_index("ix_uploads_user", "uploads", ["user_id"])
    op.create_index(
        "ix_uploads_open",
        "uploads",
        ["expires_at"],
        postgresql_where=sa.text("state IN ('pending', 'ready')"),
    )


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Drop files' tables and the key check."""
    drop_function(KEYS_IN_USE, KEYS_IN_USE_ARGUMENTS)
    revoke_from_application(scope, "object_deletions")
    op.drop_table("object_deletions")
    for table in reversed(PERSONAL):
        revoke_from_application(scope, table)
        disable_user_isolation(table)
    revoke_from_sweeper("storage_files")
    revoke_from_application(scope, "storage_files")
    disable_company_isolation("storage_files")
    op.drop_table("storage_usage")
    op.drop_table("uploads")
    op.drop_table("storage_files")
    op.drop_table("file_folders")
