"""Accounts, their consent journal and pending registrations, in every home (identity step 2)."""

from datetime import datetime

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

revision: str = "e8a142594282"
down_revision: str | None = "0dee1c02fdf7"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME

ACCOUNT_STATES = (
    "'active', 'frozen', 'banned', 'deletion_scheduled', 'deleting', 'transferring', 'deleted'"
)
CONSENT_KINDS = "'personal_data', 'cross_border', 'marketing', 'improve_models', 'share_location'"


def check(table: str, sql: str, name: str) -> sa.CheckConstraint:
    """A check constraint named by the project's convention."""
    return sa.CheckConstraint(sql, name=op.f(f"ck_{table}_{name}"))


def moment(name: str, *, default_now: bool = False, nullable: bool = False) -> sa.Column[datetime]:
    """A timestamp column with a time zone."""
    default = sa.func.now() if default_now else None
    return sa.Column(name, sa.DateTime(timezone=True), server_default=default, nullable=nullable)


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Create the accounts, the consent journal and the pending registrations."""
    create_users(scope)
    create_consents(scope)
    create_pending(scope)


def create_users(scope: MigrationScope) -> None:
    """The accounts; never deleted by the application, anonymised on erasure."""
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=True),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("work_role", sa.Text(), nullable=True),
        sa.Column("country", sa.Text(), nullable=True),
        sa.Column("language", sa.Text(), nullable=False),
        sa.Column("timezone", sa.Text(), nullable=True),
        sa.Column("avatar_key", sa.Text(), nullable=True),
        sa.Column("state", sa.Text(), server_default="active", nullable=False),
        sa.Column("token_version", sa.Integer(), server_default="0", nullable=False),
        moment("email_verified_at", nullable=True),
        moment("last_login_at", nullable=True),
        moment("created_at", default_now=True),
        moment("updated_at", default_now=True),
        check("users", f"state IN ({ACCOUNT_STATES})", "state_known"),
        check("users", "length(email) BETWEEN 3 AND 254", "email_length"),
        check("users", "length(full_name) BETWEEN 1 AND 80", "full_name_length"),
        check(
            "users",
            "display_name IS NULL OR length(display_name) BETWEEN 1 AND 80",
            "display_name_length",
        ),
        check("users", "country IS NULL OR country ~ '^[A-Z]{2}$'", "country_code"),
        check("users", "token_version >= 0", "token_version_not_negative"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )
    op.create_index("uq_users_email", "users", ["email"], unique=True)
    grant_to_application(scope, "users", ("SELECT", "INSERT", "UPDATE"))


def create_consents(scope: MigrationScope) -> None:
    """The append-only consent journal; erasure removes it with the account."""
    op.create_table(
        "user_consents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("granted", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("ip", postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        moment("recorded_at", default_now=True),
        check("user_consents", f"kind IN ({CONSENT_KINDS})", "kind_known"),
        check(
            "user_consents",
            "source IN ('registration', 'settings', 'migration')",
            "source_known",
        ),
        check(
            "user_consents", "user_agent IS NULL OR length(user_agent) <= 512", "user_agent_length"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_consents_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_consents")),
    )
    op.create_index("ix_user_consents_current", "user_consents", ["user_id", "kind", "recorded_at"])
    # Журнал только дополняется; удаление — вместе с аккаунтом по каскаду.
    grant_to_application(scope, "user_consents", ("SELECT", "INSERT"))


def create_pending(scope: MigrationScope) -> None:
    """Registrations waiting for their code; deleted on verification and after expiry."""
    op.create_table(
        "pending_registrations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("email_hmac", sa.LargeBinary(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("country", sa.Text(), nullable=False),
        sa.Column("language", sa.Text(), nullable=False),
        sa.Column("consent_cross_border", sa.Boolean(), nullable=False),
        sa.Column("consent_marketing", sa.Boolean(), nullable=False),
        sa.Column("consent_ip", postgresql.INET(), nullable=True),
        sa.Column("consent_user_agent", sa.Text(), nullable=True),
        sa.Column("code_hash", sa.LargeBinary(), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("resends", sa.Integer(), server_default="0", nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        moment("last_sent_at"),
        moment("expires_at"),
        moment("created_at", default_now=True),
        check("pending_registrations", "attempts BETWEEN 0 AND 5", "attempts_bounded"),
        check("pending_registrations", "resends BETWEEN 0 AND 3", "resends_bounded"),
        check("pending_registrations", "length(email_hmac) = 32", "email_hmac_length"),
        check("pending_registrations", "country ~ '^[A-Z]{2}$'", "country_code"),
        check("pending_registrations", "length(full_name) BETWEEN 1 AND 80", "full_name_length"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pending_registrations")),
    )
    op.create_index("ix_pending_registrations_expires", "pending_registrations", ["expires_at"])
    grant_to_application(scope, "pending_registrations", ("SELECT", "INSERT", "UPDATE", "DELETE"))


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Drop the pending registrations, the consent journal and the accounts."""
    for table in ("pending_registrations", "user_consents", "users"):
        revoke_from_application(scope, table)
        op.drop_table(table)
