"""Meetings' tables in each home (meetings step 2; ADR 0056).

`sessions` is the shareable meeting resource: company isolation with workspaces' access
policy guarding personal rows (WS-D2); its children carry `org_id`, so the company policy
covers them too. `transcript_segments` is partitioned by the month of its meeting's start,
which makes `(session_id, seq)` its unique key; its partitions are kept for ever until
the transcript archive (plan step 20). Folders, templates and settings are personal.
`meeting_object_deletions` names keys only. `meetings_shared_meeting(token)` answers,
past row-level security, the meeting and company of the link with that token.
"""

from datetime import datetime
from typing import Final
from uuid import UUID

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

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
from shosai.core.db.partitions.policy import (
    MonthlyPartitions,
    monthly_partition_range,
    register_monthly_partitions,
    unregister_monthly_partitions,
)

revision: str = "a2c7e4f9b318"
down_revision: str | None = "d8b3e6a0f914"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME

TRANSCRIPT: Final = MonthlyPartitions("transcript_segments", ahead_months=2, keep_months=None)
COMPANY: Final = (
    "sessions",
    "transcript_segments",
    "meeting_speakers",
    "meeting_participants",
    "meeting_notes",
    "meeting_findings",
    "meeting_processing_runs",
    "meeting_result_shares",
    "meeting_share_comments",
)
PERSONAL: Final = ("meeting_folders", "meeting_templates", "meeting_settings")
SHARED_MEETING: Final = "meetings_shared_meeting"
SHARED_MEETING_ARGUMENTS: Final[tuple[FunctionArgument, ...]] = ("text",)
# Владелец таблиц отвечает по токену встречей и компанией ссылки; ничего другого не отдаёт.
SHARED_MEETING_FUNCTION: Final = """
CREATE FUNCTION meetings_shared_meeting(text)
RETURNS TABLE (session_id uuid, org_id uuid)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
    SELECT link.session_id, link.org_id FROM meeting_result_shares AS link WHERE link.token = $1
$$
"""
ACCESS: Final = (
    ("(org_id IS NULL) = (access IS NULL)", "org_with_access"),
    ("access IS NULL OR access IN ('owner', 'selected', 'organization')", "access_known"),
)


def check(table: str, sql: str, name: str) -> sa.CheckConstraint:
    """A check constraint named by the project's convention."""
    return sa.CheckConstraint(sql, name=op.f(f"ck_{table}_{name}"))


def moment(name: str, *, nullable: bool = False) -> sa.Column[datetime]:
    """A timestamp column; creation and update moments default to now."""
    default = sa.func.now() if name in {"created_at", "updated_at"} else None
    return sa.Column(name, sa.DateTime(timezone=True), server_default=default, nullable=nullable)


def uuid_column(name: str, *, nullable: bool = False) -> sa.Column[UUID]:
    """A UUID column."""
    return sa.Column(name, sa.Uuid(), nullable=nullable)


def meeting(table: str, *, primary_key: bool = False) -> sa.Column[UUID]:
    """The meeting a child row belongs to, deleted with it."""
    return sa.Column(
        "session_id",
        sa.Uuid(),
        sa.ForeignKey(
            "sessions.id", name=op.f(f"fk_{table}_session_id_sessions"), ondelete="CASCADE"
        ),
        primary_key=primary_key,
        nullable=False,
    )


def owner_columns() -> tuple[sa.Column[UUID], sa.Column[UUID]]:
    """The meeting's owner, denormalised, and its company."""
    return uuid_column("user_id"), uuid_column("org_id", nullable=True)


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Create meetings, transcript, speakers, participants, notes, runs, links and settings."""
    create_personal()
    create_meetings()
    create_transcript()
    create_people()
    create_notes()
    create_runs()
    create_deletions()
    create_links()
    for table in COMPANY:
        enable_company_isolation(table)
        grant_to_application(scope, table)
    for table in PERSONAL:
        enable_user_isolation(table)
        grant_to_application(scope, table)
    grant_to_application(scope, "meeting_object_deletions")
    op.execute(SHARED_MEETING_FUNCTION)
    open_function(SHARED_MEETING, SHARED_MEETING_ARGUMENTS, (scope.application_role,))


def create_personal() -> None:
    """A person's folders, templates and setting."""
    op.create_table(
        "meeting_folders",
        uuid_column("id"),
        uuid_column("user_id"),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("color", sa.Text(), nullable=False),
        moment("created_at"),
        moment("updated_at"),
        check("meeting_folders", "length(name) BETWEEN 1 AND 200", "name_length"),
        check(
            "meeting_folders", "color IN ('green', 'violet', 'red', 'blue', 'amber')", "color_known"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_meeting_folders")),
    )
    op.create_index("ix_meeting_folders_user", "meeting_folders", ["user_id"])
    op.create_table(
        "meeting_templates",
        uuid_column("id"),
        uuid_column("user_id"),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("icon", sa.Text(), nullable=False),
        sa.Column("sections", JSONB(), nullable=False),
        moment("created_at"),
        moment("updated_at"),
        check("meeting_templates", "length(name) BETWEEN 1 AND 120", "name_length"),
        check("meeting_templates", "length(description) BETWEEN 1 AND 300", "description_length"),
        check(
            "meeting_templates",
            "icon IN ('briefcase', 'chart', 'handshake', 'landmark', 'lightbulb', 'magnet', "
            "'phone', 'rocket', 'calendar', 'users')",
            "icon_known",
        ),
        check("meeting_templates", "jsonb_typeof(sections) = 'array'", "sections_array"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_meeting_templates")),
    )
    op.create_index("ix_meeting_templates_user", "meeting_templates", ["user_id"])
    op.create_table(
        "meeting_settings",
        uuid_column("user_id"),
        sa.Column("keep_meetings", sa.Boolean(), server_default=sa.true(), nullable=False),
        moment("updated_at"),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_meeting_settings")),
    )


def create_meetings() -> None:
    """The meetings of people and workspaces."""
    op.create_table(
        "sessions",
        uuid_column("id"),
        *owner_columns(),
        sa.Column("access", sa.Text(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default="active", nullable=False),
        sa.Column("source", sa.Text(), server_default="live", nullable=False),
        moment("started_at"),
        moment("ended_at", nullable=True),
        sa.Column("seconds", sa.Integer(), server_default="0", nullable=False),
        sa.Column("client_device_id", sa.Text(), nullable=True),
        sa.Column("kept", sa.Boolean(), server_default=sa.true(), nullable=False),
        uuid_column("folder_id", nullable=True),
        sa.Column("template_id", sa.Text(), nullable=True),
        sa.Column("line_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("indexed_upto_seq", sa.Integer(), server_default="0", nullable=False),
        sa.Column("notes_revision", sa.Integer(), server_default="0", nullable=False),
        uuid_column("latest_run_id", nullable=True),
        moment("deleted_at", nullable=True),
        moment("created_at"),
        moment("updated_at"),
        *(check("sessions", sql, name) for sql, name in ACCESS),
        check("sessions", "org_id IS NULL OR folder_id IS NULL", "folders_personal"),
        check("sessions", "status IN ('active', 'completed', 'failed')", "status_known"),
        check("sessions", "source IN ('live', 'import')", "source_known"),
        check("sessions", "(status = 'active') = (ended_at IS NULL)", "end_with_status"),
        check("sessions", "ended_at IS NULL OR ended_at >= started_at", "end_after_start"),
        check("sessions", "length(title) BETWEEN 1 AND 256", "title_length"),
        check("sessions", "length(client_device_id) <= 256", "device_length"),
        check("sessions", "length(template_id) BETWEEN 1 AND 128", "template_length"),
        check(
            "sessions",
            "seconds >= 0 AND line_count >= 0 AND indexed_upto_seq >= 0 AND notes_revision >= 0",
            "counters_not_negative",
        ),
        sa.ForeignKeyConstraint(
            ["folder_id"],
            ["meeting_folders.id"],
            name=op.f("fk_sessions_folder_id_meeting_folders"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sessions")),
    )
    op.create_index("ix_sessions_user_started", "sessions", ["user_id", "started_at"])
    op.create_index("ix_sessions_org", "sessions", ["org_id"])
    op.create_index("ix_sessions_folder", "sessions", ["folder_id"])
    active = sa.text("status = 'active'")
    op.create_index("ix_sessions_active", "sessions", ["started_at"], postgresql_where=active)
    op.create_index(
        "ix_sessions_device", "sessions", ["user_id", "client_device_id"], postgresql_where=active
    )
    op.create_index(
        "ix_sessions_hidden",
        "sessions",
        ["deleted_at"],
        postgresql_where=sa.text("deleted_at IS NOT NULL"),
    )


def create_transcript() -> None:
    """Transcript lines by month of their meeting's start."""
    op.create_table(
        "transcript_segments",
        meeting("transcript_segments"),
        sa.Column("seq", sa.Integer(), nullable=False),
        moment("meeting_started_at"),
        uuid_column("org_id", nullable=True),
        moment("started_at"),
        sa.Column("start_ms", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("speaker_idx", sa.SmallInteger(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("origin", sa.Text(), server_default="live", nullable=False),
        uuid_column("run_id", nullable=True),
        moment("created_at"),
        check("transcript_segments", "seq >= 1", "seq_from_one"),
        check("transcript_segments", "start_ms >= 0 AND duration_ms >= 0", "times_not_negative"),
        check("transcript_segments", "length(text) <= 20000", "text_length"),
        check("transcript_segments", "origin IN ('live', 'recording')", "origin_known"),
        check(
            "transcript_segments", "speaker_idx IS NULL OR speaker_idx >= 0", "speaker_not_negative"
        ),
        sa.PrimaryKeyConstraint(
            "session_id", "seq", "meeting_started_at", name="pk_transcript_segments"
        ),
        postgresql_partition_by=monthly_partition_range("meeting_started_at"),
    )
    op.create_index(
        "ix_transcript_segments_order", "transcript_segments", ["session_id", "start_ms", "seq"]
    )
    register_monthly_partitions(TRANSCRIPT)


def create_people() -> None:
    """Speakers by number and participants by address."""
    op.create_table(
        "meeting_speakers",
        uuid_column("id"),
        meeting("meeting_speakers"),
        *owner_columns(),
        sa.Column("idx", sa.SmallInteger(), nullable=False),
        sa.Column("role", sa.Text(), server_default="numbered", nullable=False),
        sa.Column("talk_ms", sa.Integer(), server_default="0", nullable=False),
        uuid_column("person_id", nullable=True),
        check("meeting_speakers", "role IN ('owner', 'other', 'numbered')", "role_known"),
        check("meeting_speakers", "idx >= 0 AND talk_ms >= 0", "numbers_not_negative"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_meeting_speakers")),
    )
    op.create_index(
        "uq_meeting_speakers_number", "meeting_speakers", ["session_id", "idx"], unique=True
    )
    op.create_index("ix_meeting_speakers_user", "meeting_speakers", ["user_id"])
    op.create_table(
        "meeting_participants",
        uuid_column("id"),
        meeting("meeting_participants"),
        *owner_columns(),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("source", sa.Text(), server_default="added", nullable=False),
        moment("created_at"),
        check(
            "meeting_participants",
            "source IN ('added', 'calendar', 'speaker')",
            "source_known",
        ),
        check("meeting_participants", "email IS NOT NULL OR name IS NOT NULL", "someone"),
        check("meeting_participants", "length(email) BETWEEN 3 AND 254", "email_length"),
        check("meeting_participants", "length(name) BETWEEN 1 AND 200", "name_length"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_meeting_participants")),
    )
    op.create_index(
        "uq_meeting_participants_email",
        "meeting_participants",
        ["session_id", "email"],
        unique=True,
        postgresql_where=sa.text("email IS NOT NULL"),
    )
    op.create_index("ix_meeting_participants_session", "meeting_participants", ["session_id"])
    op.create_index("ix_meeting_participants_user", "meeting_participants", ["user_id"])


def create_notes() -> None:
    """A meeting's notes and its findings."""
    op.create_table(
        "meeting_notes",
        meeting("meeting_notes", primary_key=True),
        *owner_columns(),
        sa.Column("my_markdown", sa.Text(), server_default="", nullable=False),
        sa.Column("my_version", sa.Integer(), server_default="0", nullable=False),
        sa.Column("my_client", sa.Text(), nullable=True),
        moment("my_updated_at", nullable=True),
        sa.Column("write_up", JSONB(), nullable=True),
        sa.Column("write_up_template", sa.Text(), nullable=True),
        uuid_column("write_up_run_id", nullable=True),
        sa.Column("write_up_automatic", sa.Boolean(), server_default=sa.true(), nullable=False),
        moment("write_up_written_at", nullable=True),
        sa.Column("map", JSONB(), nullable=True),
        moment("updated_at"),
        check("meeting_notes", "octet_length(my_markdown) <= 262144", "my_notes_size"),
        check("meeting_notes", "my_version >= 0", "version_not_negative"),
        check(
            "meeting_notes",
            "my_client IS NULL OR my_client IN ('web', 'macos', 'windows')",
            "client_known",
        ),
        check(
            "meeting_notes",
            "write_up IS NULL OR jsonb_typeof(write_up) = 'object'",
            "write_up_object",
        ),
        check("meeting_notes", "map IS NULL OR jsonb_typeof(map) = 'object'", "map_object"),
        check("meeting_notes", "length(write_up_template) BETWEEN 1 AND 128", "template_length"),
        sa.PrimaryKeyConstraint("session_id", name=op.f("pk_meeting_notes")),
    )
    op.create_index("ix_meeting_notes_user", "meeting_notes", ["user_id"])
    op.create_table(
        "meeting_findings",
        uuid_column("id"),
        meeting("meeting_findings"),
        *owner_columns(),
        uuid_column("run_id"),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("topic", sa.Text(), nullable=True),
        sa.Column("owner_speaker", sa.SmallInteger(), nullable=True),
        sa.Column("owner_name", sa.Text(), nullable=True),
        sa.Column("due_on", sa.Date(), nullable=True),
        sa.Column("start_ms", sa.Integer(), nullable=False),
        sa.Column("end_ms", sa.Integer(), nullable=False),
        sa.Column("quote", sa.Text(), server_default="", nullable=False),
        moment("created_at"),
        check(
            "meeting_findings",
            "kind IN ('key_point', 'decision', 'action_item', 'promise', 'risk', 'question')",
            "kind_known",
        ),
        check("meeting_findings", "length(text) BETWEEN 1 AND 500", "text_length"),
        check("meeting_findings", "length(topic) BETWEEN 1 AND 80", "topic_length"),
        check("meeting_findings", "length(owner_name) BETWEEN 1 AND 120", "owner_length"),
        check("meeting_findings", "length(quote) <= 300", "quote_length"),
        check("meeting_findings", "0 <= start_ms AND start_ms <= end_ms", "evidence_span"),
        check("meeting_findings", "revision >= 1 AND position >= 0", "order_known"),
        check(
            "meeting_findings", "owner_speaker IS NULL OR owner_speaker >= 0", "owner_not_negative"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_meeting_findings")),
    )
    op.create_index(
        "ix_meeting_findings_revision", "meeting_findings", ["session_id", "revision", "position"]
    )
    op.create_index("ix_meeting_findings_user", "meeting_findings", ["user_id"])


def create_runs() -> None:
    """Post-meeting runs with their stages and transient objects."""
    op.create_table(
        "meeting_processing_runs",
        uuid_column("id"),
        meeting("meeting_processing_runs"),
        *owner_columns(),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), server_default="pending", nullable=False),
        sa.Column("stage_state", JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("audio_key", sa.Text(), nullable=True),
        sa.Column("multipart_id", sa.Text(), nullable=True),
        sa.Column("audio_content_type", sa.Text(), nullable=True),
        sa.Column("audio_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("audio_duration_ms", sa.Integer(), nullable=True),
        sa.Column("audio_lead_ms", sa.Integer(), nullable=True),
        moment("audio_expires_at", nullable=True),
        sa.Column("raw_transcript_key", sa.Text(), nullable=True),
        sa.Column("turns_key", sa.Text(), nullable=True),
        sa.Column("error_code", sa.Text(), nullable=True),
        moment("created_at"),
        moment("updated_at"),
        moment("finished_at", nullable=True),
        check(
            "meeting_processing_runs",
            "source IN ('live', 'import', 'recording', 'regenerate')",
            "source_known",
        ),
        check(
            "meeting_processing_runs",
            "state IN ('pending', 'running', 'succeeded', 'partially_completed', 'failed')",
            "state_known",
        ),
        check("meeting_processing_runs", "length(idempotency_key) BETWEEN 1 AND 200", "key_length"),
        check("meeting_processing_runs", "jsonb_typeof(stage_state) = 'object'", "stages_object"),
        check(
            "meeting_processing_runs",
            "audio_size_bytes IS NULL OR audio_size_bytes >= 0",
            "audio_size_not_negative",
        ),
        check(
            "meeting_processing_runs",
            "audio_duration_ms IS NULL OR audio_duration_ms >= 0",
            "audio_length_not_negative",
        ),
        check(
            "meeting_processing_runs", "length(error_code) BETWEEN 1 AND 64", "error_code_length"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_meeting_processing_runs")),
    )
    op.create_index(
        "uq_meeting_processing_runs_key",
        "meeting_processing_runs",
        ["session_id", "idempotency_key"],
        unique=True,
    )
    op.create_index("ix_meeting_processing_runs_user", "meeting_processing_runs", ["user_id"])
    op.create_index(
        "ix_meeting_processing_runs_open",
        "meeting_processing_runs",
        ["updated_at"],
        postgresql_where=sa.text("state IN ('pending', 'running')"),
    )
    op.create_index(
        "ix_meeting_processing_runs_objects",
        "meeting_processing_runs",
        ["audio_expires_at"],
        postgresql_where=sa.text("audio_key IS NOT NULL OR raw_transcript_key IS NOT NULL"),
    )


def create_deletions() -> None:
    """The keys of transient objects waiting for their deletion."""
    op.create_table(
        "meeting_object_deletions",
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        moment("created_at"),
        check("meeting_object_deletions", "length(object_key) BETWEEN 1 AND 1024", "key_length"),
        sa.PrimaryKeyConstraint("object_key", name=op.f("pk_meeting_object_deletions")),
    )


def create_links() -> None:
    """One share link per meeting and its comments."""
    op.create_table(
        "meeting_result_shares",
        meeting("meeting_result_shares", primary_key=True),
        *owner_columns(),
        sa.Column("token", sa.Text(), nullable=False),
        sa.Column("show_transcript", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("show_names", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("allow_comments", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("expiry", sa.Text(), server_default="never", nullable=False),
        moment("expires_at", nullable=True),
        moment("created_at"),
        moment("updated_at"),
        check("meeting_result_shares", "token ~ '^[A-Za-z0-9_-]{1,64}$'", "token_shape"),
        check("meeting_result_shares", "expiry IN ('never', '7d', '30d', '90d')", "expiry_known"),
        sa.PrimaryKeyConstraint("session_id", name=op.f("pk_meeting_result_shares")),
    )
    op.create_index(
        "uq_meeting_result_shares_token", "meeting_result_shares", ["token"], unique=True
    )
    op.create_index("ix_meeting_result_shares_user", "meeting_result_shares", ["user_id"])
    op.create_table(
        "meeting_share_comments",
        uuid_column("id"),
        uuid_column("session_id"),
        *owner_columns(),
        sa.Column("author", sa.Text(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        moment("created_at"),
        check("meeting_share_comments", "length(text) BETWEEN 1 AND 2000", "text_length"),
        check("meeting_share_comments", "length(author) BETWEEN 1 AND 64", "author_length"),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["meeting_result_shares.session_id"],
            name=op.f("fk_meeting_share_comments_session_id_meeting_result_shares"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_meeting_share_comments")),
    )
    op.create_index(
        "ix_meeting_share_comments_page", "meeting_share_comments", ["session_id", "created_at"]
    )
    op.create_index("ix_meeting_share_comments_user", "meeting_share_comments", ["user_id"])


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Drop meetings' tables, the transcript's partitions and the link lookup."""
    drop_function(SHARED_MEETING, SHARED_MEETING_ARGUMENTS)
    revoke_from_application(scope, "meeting_object_deletions")
    for table in reversed(PERSONAL):
        revoke_from_application(scope, table)
        disable_user_isolation(table)
    for table in reversed(COMPANY):
        revoke_from_application(scope, table)
        disable_company_isolation(table)
    op.drop_table("meeting_share_comments")
    op.drop_table("meeting_result_shares")
    op.drop_table("meeting_object_deletions")
    op.drop_table("meeting_processing_runs")
    op.drop_table("meeting_findings")
    op.drop_table("meeting_notes")
    op.drop_table("meeting_participants")
    op.drop_table("meeting_speakers")
    unregister_monthly_partitions(TRANSCRIPT.table)
    op.drop_table("transcript_segments")
    op.drop_table("sessions")
    op.drop_table("meeting_settings")
    op.drop_table("meeting_templates")
    op.drop_table("meeting_folders")
