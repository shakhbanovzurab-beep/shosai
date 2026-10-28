"""Meetings' broadcasts: the broadcast, its stage, its bans and its chat in each home (A12b).

The draft's columns are kept so its rows move unchanged (DATA_MAPPING §5.21); each row also
carries the owner and the space of the broadcast's room. Row-level security is the rooms'
own: the company rule and, on top of it, a restrictive rule for the application role, so a
broadcast is its owner's within the owner's spaces. A broadcast owns one room and goes with
it; everything else goes with the broadcast. Raised hands and the waiting room are not kept.
"""

from datetime import datetime
from typing import Any, Final

import sqlalchemy as sa
from alembic import op

from shosai.core.db.migration_scope import (
    EVERY_HOME,
    MigrationScope,
    disable_company_isolation,
    enable_company_isolation,
    grant_to_application,
    revoke_from_application,
    run_ddl,
    runs_in,
)

revision: str = "383e717ceccb"
down_revision: str | None = "f7b43274772a"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME

TABLES: Final = ("streams", "stream_members", "stream_bans", "stream_chat_messages")
OWNER_POLICY: Final = "stream_owner"
CREATE_OWNER_POLICY: Final = (
    "CREATE POLICY %(policy)s ON %(table)s AS RESTRICTIVE TO %(role)s "
    "USING (owner_id = (SELECT app_user_id())) WITH CHECK (owner_id = (SELECT app_user_id()))"
)
DROP_POLICY: Final = "DROP POLICY %(policy)s ON %(table)s"
PRINCIPAL: Final = (
    "~ '^(guest-[0-9a-f]{12}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$'"
)


def check(table: str, sql: str, name: str) -> sa.CheckConstraint:
    """A check constraint named by the project's convention."""
    return sa.CheckConstraint(sql, name=op.f(f"ck_{table}_{name}"))


def moment(name: str, *, default_now: bool = False, nullable: bool = False) -> sa.Column[datetime]:
    """A timestamp column, defaulting to now when asked."""
    default = sa.func.now() if default_now else None
    return sa.Column(name, sa.DateTime(timezone=True), server_default=default, nullable=nullable)


def flag(name: str, *, on: bool) -> sa.Column[bool]:
    """A setting that is on or off, with its default."""
    return sa.Column(
        name, sa.Boolean(), server_default=sa.true() if on else sa.false(), nullable=False
    )


def stage_child(table: str) -> tuple[sa.Column[Any], ...]:
    """The broadcast a child row belongs to, deleted with it, and the room's owner and space."""
    link = sa.ForeignKey(
        "streams.id", name=op.f(f"fk_{table}_stream_id_streams"), ondelete="CASCADE"
    )
    return (
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("stream_id", sa.Uuid(), link, nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=True),
    )


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Create the tables and their rules."""
    create_streams()
    create_stage()
    create_chat()
    for table in TABLES:
        enable_company_isolation(table)
        run_ddl(CREATE_OWNER_POLICY, table=table, policy=OWNER_POLICY, role=scope.application_role)
        grant_to_application(scope, table)


def create_streams() -> None:
    """Broadcasts, one per room."""
    table = "streams"
    room = sa.ForeignKey("rooms.id", name=op.f("fk_streams_room_id_rooms"), ondelete="CASCADE")
    op.create_table(
        table,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=True),
        sa.Column("room_id", sa.Uuid(), room, nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("status", sa.Text(), server_default="scheduled", nullable=False),
        moment("started_at", nullable=True),
        moment("ended_at", nullable=True),
        sa.Column("speaker_limit", sa.Integer(), server_default=sa.text("10"), nullable=False),
        flag("registered_only", on=False),
        flag("manual_admit", on=False),
        sa.Column("chat_mode", sa.Text(), server_default="everyone", nullable=False),
        flag("reactions_enabled", on=True),
        flag("requests_enabled", on=True),
        flag("save_chat", on=True),
        sa.Column("stage_mode", sa.Text(), server_default="grid", nullable=False),
        sa.Column("pinned_principal", sa.Text(), nullable=True),
        moment("created_at", default_now=True),
        moment("updated_at", default_now=True),
        check(table, "status IN ('scheduled', 'live', 'ended')", "status_known"),
        check(table, "char_length(title) BETWEEN 1 AND 200", "title_length"),
        check(table, "char_length(description) <= 2000", "description_length"),
        check(table, "speaker_limit BETWEEN 1 AND 20", "speaker_limit_range"),
        check(table, "chat_mode IN ('everyone', 'speakers', 'off')", "chat_mode_known"),
        check(table, "stage_mode IN ('grid', 'spotlight', 'presentation')", "stage_mode_known"),
        check(table, "status = 'scheduled' OR started_at IS NOT NULL", "started_when_live"),
        check(table, "(status = 'ended') = (ended_at IS NOT NULL)", "ended_when_ended"),
        check(table, f"pinned_principal IS NULL OR pinned_principal {PRINCIPAL}", "pinned_shape"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_streams")),
        sa.UniqueConstraint("room_id", name="uq_streams_room_id"),
    )
    op.create_index("ix_streams_owner_created", table, ["owner_id", "created_at"])


def create_stage() -> None:
    """The stage's places and the broadcast's bans."""
    table = "stream_members"
    op.create_table(
        table,
        *stage_child(table),
        sa.Column("principal", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), server_default="speaker", nullable=False),
        flag("on_air", on=True),
        sa.Column("position", sa.Integer(), server_default=sa.text("0"), nullable=False),
        moment("created_at", default_now=True),
        moment("updated_at", default_now=True),
        check(table, "role IN ('host', 'cohost', 'speaker')", "role_known"),
        check(table, f"principal {PRINCIPAL}", "principal_shape"),
        check(table, "char_length(display_name) BETWEEN 1 AND 100", "display_name_length"),
        check(table, "position >= 0", "position_counted"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stream_members")),
        sa.UniqueConstraint("stream_id", "principal", name="uq_stream_members_stream_principal"),
    )
    op.create_index("ix_stream_members_stage", table, ["stream_id", "position"])
    table = "stream_bans"
    op.create_table(
        table,
        *stage_child(table),
        sa.Column("principal", sa.Text(), nullable=False),
        sa.Column("banned_by", sa.Text(), nullable=False),
        moment("created_at", default_now=True),
        moment("updated_at", default_now=True),
        check(table, f"principal {PRINCIPAL}", "principal_shape"),
        check(table, f"banned_by {PRINCIPAL}", "banned_by_shape"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stream_bans")),
        sa.UniqueConstraint("stream_id", "principal", name="uq_stream_bans_stream_principal"),
    )


def create_chat() -> None:
    """The broadcast's chat, numbered within it."""
    table = "stream_chat_messages"
    op.create_table(
        table,
        *stage_child(table),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("principal", sa.Text(), nullable=False),
        sa.Column("author", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        flag("pinned", on=False),
        flag("from_stage", on=False),
        moment("created_at", default_now=True),
        moment("updated_at", default_now=True),
        moment("deleted_at", nullable=True),
        check(table, "seq >= 1", "seq_positive"),
        check(table, f"principal {PRINCIPAL}", "principal_shape"),
        check(table, "char_length(author) BETWEEN 1 AND 100", "author_length"),
        check(table, "char_length(body) BETWEEN 1 AND 2000", "body_length"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stream_chat_messages")),
        sa.UniqueConstraint("stream_id", "seq", name="uq_stream_chat_messages_stream_seq"),
    )


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Drop the tables with their rules."""
    for table in reversed(TABLES):
        revoke_from_application(scope, table)
        run_ddl(DROP_POLICY, table=table, policy=OWNER_POLICY)
        disable_company_isolation(table)
        op.drop_table(table)
