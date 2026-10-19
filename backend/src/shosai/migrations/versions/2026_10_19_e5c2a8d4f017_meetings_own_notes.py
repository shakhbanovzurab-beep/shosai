"""Each person's own notes on a meeting, in a table of their own (every home, meetings step 7b).

Whoever may read a meeting keeps notes of their own on it; nobody else reads them, not even
the meeting's owner. `meeting_own_notes` holds one row per meeting and person, personal by
nature: row-level security admits a row to its writer only. The owner's notes kept so far
in `meeting_notes` move into it as the owner's rows, and those columns go. A downgrade
brings the owner's rows back and drops the others: the former shape had room for one
person's notes only.
"""

from typing import Final

import sqlalchemy as sa
from alembic import op

from shosai.core.db.migration_scope import (
    EVERY_HOME,
    MigrationScope,
    disable_user_isolation,
    enable_user_isolation,
    grant_to_application,
    revoke_from_application,
    runs_in,
)

revision: str = "e5c2a8d4f017"
down_revision: str | None = "d9f3b7a1c246"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME

TABLE: Final = "meeting_own_notes"
MOVE_IN: Final = """
INSERT INTO meeting_own_notes (id, session_id, user_id, markdown, version, client, updated_at)
SELECT gen_random_uuid(), notes.session_id, meeting.user_id, notes.my_markdown,
       GREATEST(notes.my_version, 1), COALESCE(notes.my_client, 'web'), notes.my_updated_at
FROM meeting_notes AS notes JOIN sessions AS meeting ON meeting.id = notes.session_id
WHERE notes.my_updated_at IS NOT NULL
"""
MOVE_BACK: Final = """
UPDATE meeting_notes AS notes
SET my_markdown = own.markdown, my_version = own.version, my_client = own.client,
    my_updated_at = own.updated_at
FROM meeting_own_notes AS own JOIN sessions AS meeting ON meeting.id = own.session_id
WHERE own.session_id = notes.session_id AND own.user_id = meeting.user_id
"""
FORMER_CHECKS: Final = (
    ("my_notes_size", "octet_length(my_markdown) <= 262144"),
    ("version_not_negative", "my_version >= 0"),
    ("client_known", "my_client IS NULL OR my_client IN ('web', 'macos', 'windows')"),
)


def check(name: str, sql: str) -> sa.CheckConstraint:
    """A check of the new table, named by the project's convention."""
    return sa.CheckConstraint(sql, name=op.f(f"ck_{TABLE}_{name}"))


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Create the table, move the owners' notes into it, drop the former columns."""
    op.create_table(
        TABLE,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("markdown", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("client", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        check("size", "octet_length(markdown) <= 262144"),
        check("version_positive", "version >= 1"),
        check("client_known", "client IN ('web', 'macos', 'windows')"),
        sa.ForeignKeyConstraint(
            ["session_id"], ["sessions.id"], name=op.f(f"fk_{TABLE}_session_id_sessions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{TABLE}")),
    )  # fmt: skip
    op.create_index("uq_meeting_own_notes_person", TABLE, ["session_id", "user_id"], unique=True)
    op.create_index("ix_meeting_own_notes_user", TABLE, ["user_id"])
    enable_user_isolation(TABLE)
    grant_to_application(scope, TABLE)
    op.execute(MOVE_IN)
    for name, _ in FORMER_CHECKS:
        op.drop_constraint(op.f(f"ck_meeting_notes_{name}"), "meeting_notes", type_="check")
    for column in ("my_markdown", "my_version", "my_client", "my_updated_at"):
        op.drop_column("meeting_notes", column)


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Bring the owners' notes back into `meeting_notes` and drop the table."""
    op.add_column(
        "meeting_notes", sa.Column("my_markdown", sa.Text(), server_default="", nullable=False)
    )
    op.add_column(
        "meeting_notes", sa.Column("my_version", sa.Integer(), server_default="0", nullable=False)
    )
    op.add_column("meeting_notes", sa.Column("my_client", sa.Text(), nullable=True))
    op.add_column(
        "meeting_notes", sa.Column("my_updated_at", sa.DateTime(timezone=True), nullable=True)
    )
    for name, sql in FORMER_CHECKS:
        op.create_check_constraint(op.f(f"ck_meeting_notes_{name}"), "meeting_notes", sql)
    op.execute(MOVE_BACK)
    revoke_from_application(scope, TABLE)
    disable_user_isolation(TABLE)
    op.drop_index("ix_meeting_own_notes_user", table_name=TABLE)
    op.drop_index("uq_meeting_own_notes_person", table_name=TABLE)
    op.drop_table(TABLE)
