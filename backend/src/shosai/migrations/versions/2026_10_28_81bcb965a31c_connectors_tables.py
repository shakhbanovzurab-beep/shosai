"""Connectors' tables (connectors step 2; ADR 0075).

In each home: a provider account's grant, its secrets in a table of their own, and the apps
on it. A personal row is its person's alone — the company policy and a restrictive policy
that admits a row without a company only to its person; a workspace's installation follows
the company policy. Connections sit on a grant of the same person through a composite key;
the database keeps the closed sets, the problem that comes exactly with `needs_reconnect`,
one account per app per person, and the partial index of the keep-alive's due rows. The
sweep role reads grants and secrets for the keep-alive and the key rotation.
"""

from datetime import datetime
from typing import Final

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from shosai.core.db.migration_scope import (
    EVERY_HOME,
    MigrationScope,
    disable_company_isolation,
    enable_company_isolation,
    grant_to_application,
    grant_to_sweeper,
    revoke_from_application,
    revoke_from_sweeper,
    run_ddl,
    runs_in,
)

revision: str = "81bcb965a31c"
down_revision: str | None = "383e717ceccb"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME

TABLES: Final = ("connector_grants", "connector_grant_secrets", "connections")
SWEPT: Final = ("connector_grants", "connector_grant_secrets")
PROVIDERS: Final = (
    "'google', 'microsoft', 'yandex', 'mailru', 'caldav', 'notion', 'atlassian', 'dropbox', "
    "'github', 'gitlab', 'slack', 'hubspot', 'attio', 'affinity', 'zapier'"
)
APPS: Final = (
    "'gmail', 'google_calendar', 'google_drive', 'outlook', 'outlook_calendar', "
    "'yandex_mail', 'yandex_calendar', 'yandex_disk', 'mailru_mail', 'caldav', 'notion', "
    "'confluence', 'jira', 'dropbox', 'github', 'gitlab', 'slack', 'hubspot', 'attio', "
    "'affinity', 'zapier'"
)
AUTH_KINDS: Final = "'oauth2', 'app_password', 'api_key', 'webhook_url'"
PROBLEMS: Final = (
    "'refresh_refused', 'grant_revoked', 'scope_missing', 'admin_consent_required', "
    "'imap_disabled', 'provider_subscription_required', 'credentials_rejected'"
)
PERSONAL_POLICY: Final = "personal_rows_own"
# Строка без компании — личный грант человека: её видит и пишет только он сам (CN-D3).
CREATE_PERSONAL_POLICY: Final = (
    "CREATE POLICY %(policy)s ON %(table)s AS RESTRICTIVE TO %(role)s "
    "USING (org_id IS NOT NULL OR user_id = (SELECT app_user_id())) "
    "WITH CHECK (org_id IS NOT NULL OR user_id = (SELECT app_user_id()))"
)
DROP_POLICY: Final = "DROP POLICY %(policy)s ON %(table)s"


def check(table: str, sql: str, name: str) -> sa.CheckConstraint:
    """A check constraint named by the project's convention."""
    return sa.CheckConstraint(sql, name=op.f(f"ck_{table}_{name}"))


def moment(name: str, *, nullable: bool = False) -> sa.Column[datetime]:
    """A timestamp column; a required one defaults to now."""
    default = None if nullable else sa.func.now()
    return sa.Column(name, sa.DateTime(timezone=True), server_default=default, nullable=nullable)


def problem_checks(table: str, statuses: str) -> tuple[sa.CheckConstraint, ...]:
    """The closed sets of status and problem, and the problem that comes with waiting."""
    return (
        check(table, f"status IN ({statuses})", "status_known"),
        check(table, f"problem IS NULL OR problem IN ({PROBLEMS})", "problem_known"),
        check(
            table, "(status = 'needs_reconnect') = (problem IS NOT NULL)", "problem_when_waiting"
        ),
    )


def grants() -> None:
    """Provider accounts' consents."""
    table = "connector_grants"
    op.create_table(
        table,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=True),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("client_key", sa.Text(), nullable=False),
        sa.Column("auth_kind", sa.Text(), nullable=False),
        sa.Column("external_account_id", sa.Text(), nullable=False),
        sa.Column("account_label", sa.Text(), nullable=True),
        sa.Column(
            "granted_scopes", postgresql.ARRAY(sa.Text()), server_default="{}", nullable=False
        ),
        sa.Column("provider_meta", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("status", sa.Text(), server_default="active", nullable=False),
        sa.Column("problem", sa.Text(), nullable=True),
        sa.Column("consecutive_failures", sa.Integer(), server_default="0", nullable=False),
        moment("last_failure_at", nullable=True),
        moment("created_at"),
        moment("updated_at"),
        check(table, f"provider IN ({PROVIDERS})", "provider_known"),
        check(table, f"auth_kind IN ({AUTH_KINDS})", "auth_kind_known"),
        *problem_checks(table, "'active', 'needs_reconnect', 'revoking'"),
        check(table, "client_key ~ '^[a-z][a-z0-9_]{1,31}$'", "client_key_format"),
        check(
            table, "char_length(external_account_id) BETWEEN 1 AND 255",
            "external_account_id_length",
        ),
        check(
            table, "account_label IS NULL OR char_length(account_label) <= 320",
            "account_label_length",
        ),
        check(table, "consecutive_failures >= 0", "failures_counted"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_connector_grants")),
        sa.UniqueConstraint("id", "user_id", name="uq_connector_grants_id_user_id"),
    )  # fmt: skip
    op.create_index(
        "uq_connector_grants_personal_account", table,
        ["user_id", "provider", "client_key", "external_account_id"],
        unique=True, postgresql_where=sa.text("org_id IS NULL"),
    )  # fmt: skip
    op.create_index(
        "uq_connector_grants_workspace_account", table,
        ["org_id", "provider", "external_account_id"],
        unique=True, postgresql_where=sa.text("org_id IS NOT NULL"),
    )  # fmt: skip


def secrets() -> None:
    """A grant's ciphertexts and refresh lease."""
    table = "connector_grant_secrets"
    op.create_table(
        table,
        sa.Column("grant_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=True),
        sa.Column("access_token_enc", sa.LargeBinary(), nullable=True),
        sa.Column("refresh_token_enc", sa.LargeBinary(), nullable=True),
        sa.Column("secret_enc", sa.LargeBinary(), nullable=True),
        moment("expires_at", nullable=True),
        sa.Column("refresh_generation", sa.Integer(), server_default="0", nullable=False),
        moment("refreshing_until", nullable=True),
        moment("refreshed_at", nullable=True),
        moment("keepalive_at", nullable=True),
        check(
            table,
            "access_token_enc IS NOT NULL OR refresh_token_enc IS NOT NULL "
            "OR secret_enc IS NOT NULL",
            "something_held",
        ),
        check(table, "refresh_generation >= 0", "generation_counted"),
        sa.ForeignKeyConstraint(
            ["grant_id", "user_id"], ["connector_grants.id", "connector_grants.user_id"],
            name="fk_connector_grant_secrets_grant", ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("grant_id", name=op.f("pk_connector_grant_secrets")),
    )  # fmt: skip
    op.create_index(
        "ix_connector_grant_secrets_keepalive_at", table, ["keepalive_at"],
        postgresql_where=sa.text("keepalive_at IS NOT NULL"),
    )  # fmt: skip


def connections() -> None:
    """Apps on grants."""
    table = "connections"
    op.create_table(
        table,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=True),
        sa.Column("app", sa.Text(), nullable=False),
        sa.Column("grant_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.Text(), server_default="active", nullable=False),
        sa.Column("problem", sa.Text(), nullable=True),
        moment("last_used_at", nullable=True),
        moment("connected_at"),
        moment("created_at"),
        moment("updated_at"),
        check(table, f"app IN ({APPS})", "app_known"),
        *problem_checks(table, "'active', 'needs_reconnect'"),
        sa.ForeignKeyConstraint(
            ["grant_id", "user_id"], ["connector_grants.id", "connector_grants.user_id"],
            name="fk_connections_grant",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_connections")),
    )  # fmt: skip
    op.create_index(
        "uq_connections_personal_app", table, ["user_id", "app"],
        unique=True, postgresql_where=sa.text("org_id IS NULL"),
    )  # fmt: skip
    op.create_index(
        "uq_connections_workspace_app", table, ["org_id", "app", "grant_id"],
        unique=True, postgresql_where=sa.text("org_id IS NOT NULL"),
    )  # fmt: skip
    op.create_index("ix_connections_grant_id", table, ["grant_id"])


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Create the tables and their row-level security in each home."""
    grants()
    secrets()
    connections()
    for table in TABLES:
        enable_company_isolation(table)
        run_ddl(
            CREATE_PERSONAL_POLICY, table=table, policy=PERSONAL_POLICY,
            role=scope.application_role,
        )  # fmt: skip
        grant_to_application(scope, table)
    for table in SWEPT:
        grant_to_sweeper(table, ("SELECT",))


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Drop the tables this revision created, in the reverse order."""
    for table in reversed(SWEPT):
        revoke_from_sweeper(table)
    for table in reversed(TABLES):
        revoke_from_application(scope, table)
        run_ddl(DROP_POLICY, table=table, policy=PERSONAL_POLICY)
        disable_company_isolation(table)
        op.drop_table(table)
