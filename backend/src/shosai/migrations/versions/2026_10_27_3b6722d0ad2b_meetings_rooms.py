"""Meetings' rooms, calls, bans, chat, recordings and boards in each home (meetings A3; ADR 0072).

Every table carries the room's owner and space. Row-level security reads them with the
company rule and, on top of it, a restrictive rule for the application role: only the
owner's transaction sees a row, so a room is its owner's within the owner's spaces (inv-14).
The sweep role reads rooms, calls and recordings to find what the sweep must do; the effect
runs as the owner. Two functions of the tables' owner answer a room's id, owner and space —
by its invitation token for the public join, by its LiveKit name for the webhook — and
nothing else.
"""

from datetime import datetime
from typing import Any, Final

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

from shosai.core.db.migration_scope import (
    EVERY_HOME,
    FunctionArgument,
    MigrationScope,
    disable_company_isolation,
    drop_function,
    enable_company_isolation,
    grant_to_application,
    grant_to_sweeper,
    open_function,
    revoke_from_application,
    revoke_from_sweeper,
    run_ddl,
    runs_in,
)

revision: str = "3b6722d0ad2b"
down_revision: str | None = "0748ba07a625"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME

TABLES: Final = (
    "rooms",
    "room_calls",
    "room_bans",
    "room_chat_messages",
    "room_recordings",
    "room_whiteboards",
)
SWEPT: Final = ("rooms", "room_calls", "room_recordings")
OWNER_POLICY: Final = "room_owner"
CREATE_OWNER_POLICY: Final = (
    "CREATE POLICY %(policy)s ON %(table)s AS RESTRICTIVE TO %(role)s "
    "USING (owner_id = (SELECT app_user_id())) WITH CHECK (owner_id = (SELECT app_user_id()))"
)
DROP_POLICY: Final = "DROP POLICY %(policy)s ON %(table)s"
LOOKUP_ARGUMENTS: Final[tuple[FunctionArgument, ...]] = ("text",)
# Владелец таблиц отвечает по токену или имени LiveKit комнатой, её владельцем и пространством.
BY_INVITE: Final = """
CREATE FUNCTION meetings_room_by_token(text)
RETURNS TABLE (room_id uuid, owner_id uuid, org_id uuid)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
    SELECT room.id, room.owner_id, room.org_id FROM rooms AS room WHERE room.invite_token = $1
$$
"""
BY_LIVEKIT_NAME: Final = """
CREATE FUNCTION meetings_room_by_livekit_name(text)
RETURNS TABLE (room_id uuid, owner_id uuid, org_id uuid)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
    SELECT room.id, room.owner_id, room.org_id FROM rooms AS room WHERE room.lk_room_name = $1
$$
"""
LOOKUPS: Final = (
    ("meetings_room_by_token", BY_INVITE),
    ("meetings_room_by_livekit_name", BY_LIVEKIT_NAME),
)
PRINCIPAL: Final = (
    "~ '^(guest-[0-9a-f]{12}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$'"
)
OPEN: Final = sa.text("state = 'open'")
ACTIVE: Final = sa.text("state IN ('starting', 'active', 'ending')")


def check(table: str, sql: str, name: str) -> sa.CheckConstraint:
    """A check constraint named by the project's convention."""
    return sa.CheckConstraint(sql, name=op.f(f"ck_{table}_{name}"))


def moment(name: str, *, default_now: bool = False, nullable: bool = False) -> sa.Column[datetime]:
    """A timestamp column, defaulting to now when asked."""
    default = sa.func.now() if default_now else None
    return sa.Column(name, sa.DateTime(timezone=True), server_default=default, nullable=nullable)


def owned(table: str) -> tuple[sa.Column[Any], ...]:
    """The room a child row belongs to, deleted with it, and the room's owner and space."""
    return (
        sa.Column(
            "room_id",
            sa.Uuid(),
            sa.ForeignKey("rooms.id", name=op.f(f"fk_{table}_room_id_rooms"), ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=True),
    )


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Create the tables, their rules and the two lookups."""
    create_rooms()
    create_calls()
    create_kept()
    for table in TABLES:
        enable_company_isolation(table)
        run_ddl(CREATE_OWNER_POLICY, table=table, policy=OWNER_POLICY, role=scope.application_role)
        grant_to_application(scope, table)
    for table in SWEPT:
        grant_to_sweeper(table, ("SELECT",))
    for name, function in LOOKUPS:
        op.execute(function)
        open_function(name, LOOKUP_ARGUMENTS, (scope.application_role,))


def create_rooms() -> None:
    """Rooms and their bans."""
    op.create_table(
        "rooms",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("lk_room_name", sa.Text(), nullable=False),
        sa.Column("invite_token", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), server_default="open", nullable=False),
        sa.Column("notes_on", sa.Boolean(), server_default=sa.true(), nullable=False),
        moment("closed_at", nullable=True),
        sa.Column("closed_by", sa.Text(), nullable=True),
        sa.Column("event_ref", sa.Text(), nullable=True),
        moment("created_at", default_now=True),
        moment("updated_at", default_now=True),
        check("rooms", "state IN ('open', 'closed')", "state_known"),
        check(
            "rooms",
            "closed_by IS NULL OR closed_by IN ('owner', 'idle', 'admin', 'account')",
            "closer_known",
        ),
        check("rooms", "(state = 'closed') = (closed_at IS NOT NULL)", "closed_with_its_close"),
        check("rooms", "(closed_at IS NULL) = (closed_by IS NULL)", "closer_with_time"),
        check("rooms", "title IS NULL OR char_length(title) BETWEEN 1 AND 200", "title_length"),
        check("rooms", "invite_token ~ '^[A-Za-z0-9_-]{12,64}$'", "invite_token_shape"),
        check("rooms", "lk_room_name ~ '^r-[0-9a-f]{8,64}$'", "lk_room_name_shape"),
        check(
            "rooms",
            "event_ref IS NULL OR char_length(event_ref) BETWEEN 1 AND 200",
            "event_ref_length",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rooms")),
        sa.UniqueConstraint("lk_room_name", name=op.f("uq_rooms_lk_room_name")),
        sa.UniqueConstraint("invite_token", name=op.f("uq_rooms_invite_token")),
    )
    op.create_index(
        "ix_rooms_owner_open", "rooms", ["owner_id", "created_at"], postgresql_where=OPEN
    )
    op.create_index("ix_rooms_open", "rooms", ["created_at", "id"], postgresql_where=OPEN)
    op.create_index(
        "uq_rooms_owner_event",
        "rooms",
        ["owner_id", "event_ref"],
        unique=True,
        postgresql_where=sa.text("event_ref IS NOT NULL"),
    )
    op.create_table(
        "room_bans",
        sa.Column("id", sa.Uuid(), nullable=False),
        *owned("room_bans"),
        sa.Column("principal", sa.Text(), nullable=False),
        sa.Column("banned_by", sa.Text(), nullable=False),
        moment("created_at", default_now=True),
        check("room_bans", f"principal {PRINCIPAL}", "principal_shape"),
        check("room_bans", f"banned_by {PRINCIPAL}", "banned_by_shape"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_room_bans")),
        sa.UniqueConstraint("room_id", "principal", name="uq_room_bans_room_principal"),
    )


def create_calls() -> None:
    """Calls, one per SFU room instance, and their chat."""
    op.create_table(
        "room_calls",
        sa.Column("id", sa.Uuid(), nullable=False),
        *owned("room_calls"),
        sa.Column("lk_room_sid", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), server_default="live", nullable=False),
        moment("started_at"),
        moment("emptied_at", nullable=True),
        moment("ended_at", nullable=True),
        sa.Column("ceiling", sa.Integer(), nullable=False),
        sa.Column("peak_participants", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("meeting_id", sa.Uuid(), nullable=True),
        sa.Column("board_upload_id", sa.Uuid(), nullable=True),
        check("room_calls", "state IN ('live', 'ending', 'ended')", "state_known"),
        check("room_calls", "(state = 'live') = (emptied_at IS NULL)", "emptied_when_finished"),
        check("room_calls", "(state = 'ended') = (ended_at IS NOT NULL)", "ended_when_ended"),
        check("room_calls", "ceiling BETWEEN 2 AND 1000", "ceiling_range"),
        check("room_calls", "peak_participants >= 0", "peak_counted"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_room_calls")),
        sa.UniqueConstraint("lk_room_sid", name=op.f("uq_room_calls_lk_room_sid")),
    )
    op.create_index("ix_room_calls_room", "room_calls", ["room_id", "started_at"])
    op.create_index(
        "ix_room_calls_unended",
        "room_calls",
        ["room_id"],
        postgresql_where=sa.text("state <> 'ended'"),
    )
    op.create_table(
        "room_chat_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "call_id",
            sa.Uuid(),
            sa.ForeignKey(
                "room_calls.id",
                name=op.f("fk_room_chat_messages_call_id_room_calls"),
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=True),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("principal", sa.Text(), nullable=False),
        sa.Column("identity", sa.Text(), nullable=False),
        sa.Column("author", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        moment("sent_at", default_now=True),
        check("room_chat_messages", "seq >= 1", "seq_positive"),
        check("room_chat_messages", f"principal {PRINCIPAL}", "principal_shape"),
        check("room_chat_messages", "char_length(identity) BETWEEN 1 AND 100", "identity_length"),
        check("room_chat_messages", "char_length(author) BETWEEN 1 AND 100", "author_length"),
        check("room_chat_messages", "char_length(body) BETWEEN 1 AND 2000", "body_length"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_room_chat_messages")),
        sa.UniqueConstraint("call_id", "seq", name="uq_room_chat_messages_call_seq"),
    )


def create_kept() -> None:
    """Video recordings and the room's board."""
    table = "room_recordings"
    op.create_table(
        table,
        sa.Column("id", sa.Uuid(), nullable=False),
        *owned(table),
        sa.Column("egress_id", sa.Text(), nullable=True),
        sa.Column("state", sa.Text(), server_default="starting", nullable=False),
        sa.Column("s3_key", sa.Text(), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("held_object_id", sa.Uuid(), nullable=True),
        sa.Column("error_code", sa.Text(), nullable=True),
        moment("started_at", default_now=True),
        moment("ended_at", nullable=True),
        check(
            table,
            "state IN ('starting', 'active', 'ending', 'complete', 'failed')",
            "state_known",
        ),
        check(
            table,
            "error_code IS NULL OR error_code IN ('start_refused', 'egress_failed', "
            "'egress_aborted', 'egress_lost', 'not_adopted')",
            "error_known",
        ),
        check(table, "(state = 'failed') = (error_code IS NOT NULL)", "failed_with_code"),
        check(
            table, "state NOT IN ('complete', 'failed') OR ended_at IS NOT NULL", "ended_when_over"
        ),
        check(table, "size_bytes IS NULL OR size_bytes >= 0", "size_counted"),
        check(table, "duration_seconds IS NULL OR duration_seconds >= 0", "duration_counted"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_room_recordings")),
        sa.UniqueConstraint("egress_id", name=op.f("uq_room_recordings_egress_id")),
    )
    op.create_index(
        "uq_room_recordings_active", table, ["room_id"], unique=True, postgresql_where=ACTIVE
    )
    op.create_index("ix_room_recordings_active", table, ["started_at"], postgresql_where=ACTIVE)
    create_board()


def create_board() -> None:
    """One scene per room, bounded but never parsed."""
    table = "room_whiteboards"
    op.create_table(
        table,
        *owned(table),
        sa.Column("elements", JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("files", JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("updated_by", sa.Text(), nullable=False),
        moment("updated_at", default_now=True),
        check(table, "jsonb_typeof(elements) = 'array'", "elements_list"),
        check(table, "jsonb_typeof(files) = 'object'", "files_map"),
        check(table, "jsonb_array_length(elements) <= 20000", "elements_count"),
        check(table, "octet_length(elements::text) <= 4194304", "elements_size"),
        check(table, "octet_length(files::text) <= 8388608", "files_size"),
        check(table, "version >= 0", "version_counted"),
        check(table, f"updated_by {PRINCIPAL}", "updated_by_shape"),
        sa.PrimaryKeyConstraint("room_id", name=op.f("pk_room_whiteboards")),
    )


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Drop the lookups and the tables with their rules."""
    for name, _function in LOOKUPS:
        drop_function(name, LOOKUP_ARGUMENTS)
    for table in SWEPT:
        revoke_from_sweeper(table)
    for table in reversed(TABLES):
        revoke_from_application(scope, table)
        run_ddl(DROP_POLICY, table=table, policy=OWNER_POLICY)
        disable_company_isolation(table)
        op.drop_table(table)
