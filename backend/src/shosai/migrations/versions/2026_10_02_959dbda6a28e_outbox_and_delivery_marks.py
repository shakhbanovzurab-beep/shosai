"""The outbox of domain events and the delivery marks of their consumers."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from shosai.core.db.migration_scope import (
    EVERY_HOME,
    MigrationScope,
    grant_to_application,
    revoke_from_application,
    runs_in,
)

revision: str = "959dbda6a28e"
down_revision: str | None = "e6f66cdc6ea6"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Create the outbox and the delivery marks and open them to the application role."""
    op.create_table(
        "outbox_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("org_id", sa.Uuid(), nullable=True),
        sa.Column("traceparent", sa.Text(), nullable=True),
        sa.Column("request_id", sa.Text(), nullable=True),
        sa.Column(
            "occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "available_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "event_type ~ '^[a-z][a-z0-9_]*\\.[a-z][a-z0-9_]*\\.[a-z][a-z0-9_]*$' "
            "AND length(event_type) <= 64",
            name=op.f("ck_outbox_messages_event_type_format"),
        ),
        sa.CheckConstraint("version >= 1", name=op.f("ck_outbox_messages_version_positive")),
        sa.CheckConstraint(
            "jsonb_typeof(payload) = 'object'", name=op.f("ck_outbox_messages_payload_object")
        ),
        sa.CheckConstraint("attempts >= 0", name=op.f("ck_outbox_messages_attempts_not_negative")),
        sa.CheckConstraint(
            "length(traceparent) <= 128", name=op.f("ck_outbox_messages_traceparent_length")
        ),
        sa.CheckConstraint(
            "length(request_id) <= 64", name=op.f("ck_outbox_messages_request_id_length")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_outbox_messages")),
    )
    op.create_index(
        "ix_outbox_messages_due",
        "outbox_messages",
        ["available_at", "id"],
        postgresql_where=sa.text("published_at IS NULL"),
    )
    op.create_index(
        "ix_outbox_messages_published_at",
        "outbox_messages",
        ["published_at"],
        postgresql_where=sa.text("published_at IS NOT NULL"),
    )
    grant_to_application(scope, "outbox_messages")
    op.create_table(
        "processed_events",
        sa.Column("consumer", sa.Text(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column(
            "processed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("consumer", "event_id", name=op.f("pk_processed_events")),
    )
    op.create_index("ix_processed_events_processed_at", "processed_events", ["processed_at"])
    # Отметку не меняют: её пишут, читают при повторе и удаляют по сроку.
    grant_to_application(scope, "processed_events", ("SELECT", "INSERT", "DELETE"))


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Drop the delivery marks and the outbox."""
    revoke_from_application(scope, "processed_events")
    op.drop_table("processed_events")
    revoke_from_application(scope, "outbox_messages")
    op.drop_table("outbox_messages")
