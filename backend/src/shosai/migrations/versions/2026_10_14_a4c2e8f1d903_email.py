"""Outgoing mail and unsubscriptions, in every home (F6 step 8a, F6-C10)."""

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

revision: str = "a4c2e8f1d903"
down_revision: str | None = "f2b8d6e3a5c7"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME


def check(table: str, sql: str, name: str) -> sa.CheckConstraint:
    """A check constraint named by the project's convention."""
    return sa.CheckConstraint(sql, name=op.f(f"ck_{table}_{name}"))


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Create the mail and the unsubscriptions."""
    create_messages(scope)
    create_suppressions(scope)


def create_messages(scope: MigrationScope) -> None:
    """The mail with its due, campaign and purge indexes; the purge deletes, so DELETE too."""
    op.create_table(
        "email_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("recipient", sa.Text(), nullable=False),
        sa.Column("locale", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("template", sa.Text(), nullable=False),
        sa.Column("params", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("secrets", sa.LargeBinary(), nullable=True),
        sa.Column("reply_to", sa.Text(), nullable=True),
        sa.Column("unsubscribe_url", sa.Text(), nullable=True),
        sa.Column("campaign_key", sa.Text(), nullable=True),
        sa.Column("message_id", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default="queued", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "run_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("sending_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("smtp_code", sa.Integer(), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        check("email_messages", "kind IN ('account', 'notification', 'newsletter')", "kind_known"),
        check(
            "email_messages", "status IN ('queued', 'sending', 'sent', 'failed')", "status_known"
        ),
        check("email_messages", "jsonb_typeof(params) = 'object'", "params_object"),
        check("email_messages", "attempts >= 0", "attempts_not_negative"),
        check(
            "email_messages",
            "length(recipient) BETWEEN 3 AND 254 AND length(template) BETWEEN 1 AND 64 "
            "AND length(locale) BETWEEN 2 AND 8",
            "lengths",
        ),
        check(
            "email_messages",
            "(status IN ('sent', 'failed')) = (finished_at IS NOT NULL)",
            "finished",
        ),
        check(
            "email_messages", "(status = 'sending') = (sending_until IS NOT NULL)", "sending_leased"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_email_messages")),
    )
    op.create_index(
        "ix_email_messages_due",
        "email_messages",
        ["run_at", "id"],
        postgresql_where=sa.text("status IN ('queued', 'sending')"),
    )
    op.create_index(
        "uq_email_messages_campaign",
        "email_messages",
        ["recipient", "campaign_key"],
        unique=True,
        postgresql_where=sa.text("campaign_key IS NOT NULL"),
    )
    op.create_index(
        "ix_email_messages_finished",
        "email_messages",
        ["finished_at"],
        postgresql_where=sa.text("finished_at IS NOT NULL"),
    )
    grant_to_application(scope, "email_messages", ("SELECT", "INSERT", "UPDATE", "DELETE"))


def create_suppressions(scope: MigrationScope) -> None:
    """The kinds of mail each person unsubscribed from."""
    op.create_table(
        "email_suppressions",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        check("email_suppressions", "kind IN ('notification', 'newsletter')", "kind_suppressible"),
        check("email_suppressions", "source IN ('link', 'draft_link', 'settings')", "source_known"),
        sa.PrimaryKeyConstraint("user_id", "kind", name=op.f("pk_email_suppressions")),
    )
    # Отписку человек может и отменить в настройках: строка удаляется.
    grant_to_application(scope, "email_suppressions", ("SELECT", "INSERT", "DELETE"))


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Drop the unsubscriptions and the mail."""
    revoke_from_application(scope, "email_suppressions")
    op.drop_table("email_suppressions")
    revoke_from_application(scope, "email_messages")
    op.drop_table("email_messages")
