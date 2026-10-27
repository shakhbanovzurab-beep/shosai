"""Memory's tables in each home (memory step 2; ADR 0071).

`memory_facts` holds facts, candidates and ended facts with their vector — `halfvec(1024)`
from the `vector` extension, stored `PLAIN` so a row never goes to TOAST — and the person's
switch and summary sit beside it. Every table is personal by row-level security. The sweep
role reads facts and summaries to find what the daily upkeep must do; the effect runs as the
person (ADR 0067).
"""

from datetime import datetime
from typing import Any

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import HALFVEC
from sqlalchemy.dialects import postgresql

from shosai.core.db.migration_scope import (
    EVERY_HOME,
    MigrationScope,
    disable_user_isolation,
    enable_user_isolation,
    grant_to_application,
    grant_to_sweeper,
    revoke_from_application,
    revoke_from_sweeper,
    runs_in,
)

revision: str = "e8bc01bd5bb4"
down_revision: str | None = "173ed4677079"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME

TABLES = ("memory_facts", "memory_settings", "memory_summaries")
SWEPT = ("memory_facts", "memory_summaries")
KINDS = "'preference', 'fact', 'relationship', 'goal', 'procedure'"
SOURCES = "'user_statement', 'meeting', 'team_chat', 'settings', 'user_edit', 'imported'"
STATUSES = "'candidate', 'active', 'forgotten'"
REASONS = "'forgot', 'turned_down', 'expired', 'forgot_all'"
CURRENT = sa.text("status = 'active' AND valid_to IS NULL")
PENDING = sa.text("status = 'candidate' AND valid_to IS NULL")
# Расширение удаляется, только если его создала эта роль: поставленное владельцем сервера
# (тестовые базы, управляемый PostgreSQL) остаётся, и схема возвращается к исходной.
DROP_OWN_EXTENSION = """
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_extension AS e JOIN pg_roles AS r ON r.oid = e.extowner
        WHERE e.extname = 'vector' AND r.rolname = current_user
    ) THEN
        DROP EXTENSION vector;
    END IF;
END
$$
"""


def check(table: str, sql: str, name: str) -> sa.CheckConstraint:
    """A check constraint named by the project's convention."""
    return sa.CheckConstraint(sql, name=op.f(f"ck_{table}_{name}"))


def moment(name: str, *, default_now: bool = False, nullable: bool = False) -> sa.Column[datetime]:
    """A timestamp column, defaulting to now when asked."""
    default = sa.func.now() if default_now else None
    return sa.Column(name, sa.DateTime(timezone=True), server_default=default, nullable=nullable)


def flag(name: str, *, default: bool = False) -> sa.Column[Any]:
    """A boolean column with its default."""
    return sa.Column(
        name, sa.Boolean(), server_default=sa.true() if default else sa.false(), nullable=False
    )


def fact_checks() -> tuple[sa.CheckConstraint, ...]:
    """The rules a fact's columns keep together."""
    table = "memory_facts"
    return (
        check(table, f"kind IN ({KINDS})", "kind_known"),
        check(table, f"source_kind IN ({SOURCES})", "source_known"),
        check(table, f"status IN ({STATUSES})", "status_known"),
        check(table, "sensitivity IN ('normal', 'sensitive')", "sensitivity_known"),
        check(table, "source_taint IN ('none', 'external')", "source_taint_known"),
        check(table, f"ended_reason IS NULL OR ended_reason IN ({REASONS})", "ended_reason_known"),
        check(table, "char_length(statement) BETWEEN 1 AND 500", "statement_length"),
        check(table, "confidence BETWEEN 0 AND 1", "confidence_range"),
        check(table, "confirmations >= 0", "confirmations_counted"),
        check(table, "NOT pinned OR status = 'active'", "pinned_when_active"),
        check(
            table,
            "(status = 'forgotten') = (ended_reason IS NOT NULL AND ended_at IS NOT NULL)",
            "ended_when_forgotten",
        ),
        check(table, "superseded_by IS NULL OR valid_to IS NOT NULL", "superseded_closed"),
        check(table, "(embedding IS NULL) = (embedding_model IS NULL)", "embedding_with_model"),
    )


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Create the extension, the facts, the switch and the summary."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    create_facts()
    op.create_table(
        "memory_settings",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        flag("enabled", default=True),
        moment("changed_at", default_now=True),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_memory_settings")),
    )
    op.create_table(
        "memory_summaries",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "sections", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False
        ),
        sa.Column(
            "suggestions", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False
        ),
        sa.Column("language", sa.Text(), nullable=False),
        sa.Column("facts_digest", sa.Text(), server_default="", nullable=False),
        moment("written_at", nullable=True),
        flag("stale"),
        check("memory_summaries", "char_length(language) BETWEEN 2 AND 10", "language_length"),
        check("memory_summaries", "jsonb_typeof(sections) = 'array'", "sections_list"),
        check("memory_summaries", "jsonb_typeof(suggestions) = 'array'", "suggestions_list"),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_memory_summaries")),
    )
    for table in TABLES:
        enable_user_isolation(table)
        grant_to_application(scope, table)
    for table in SWEPT:
        grant_to_sweeper(table, ("SELECT",))


def create_facts() -> None:
    """Facts, candidates and ended facts with their vectors, and the paths they are read by."""
    op.create_table(
        "memory_facts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=True),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column(
            "subject_refs",
            postgresql.ARRAY(sa.Uuid()),
            server_default=sa.text("'{}'::uuid[]"),
            nullable=False,
        ),
        sa.Column("source_kind", sa.Text(), nullable=False),
        sa.Column(
            "source_ref", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("thread_id", sa.Uuid(), nullable=True),
        sa.Column("confidence", sa.Double(), server_default=sa.text("1"), nullable=False),
        sa.Column("sensitivity", sa.Text(), server_default="normal", nullable=False),
        flag("explicit"),
        flag("confirmed"),
        sa.Column("source_taint", sa.Text(), server_default="none", nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("ended_reason", sa.Text(), nullable=True),
        moment("ended_at", nullable=True),
        moment("valid_from", default_now=True),
        moment("valid_to", nullable=True),
        sa.Column("superseded_by", sa.Uuid(), nullable=True),
        sa.Column("replaces", sa.Uuid(), nullable=True),
        flag("pinned"),
        sa.Column("confirmations", sa.Integer(), server_default=sa.text("0"), nullable=False),
        moment("last_confirmed_at", default_now=True),
        sa.Column("embedding", HALFVEC(1024), nullable=True),
        sa.Column("embedding_model", sa.Text(), nullable=True),
        moment("erase_after", nullable=True),
        moment("created_at", default_now=True),
        moment("updated_at", default_now=True),
        *fact_checks(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_memory_facts")),
    )
    # Вектор строки всегда в самой строке: без TOAST скан фактов человека читает только кучу.
    op.execute("ALTER TABLE memory_facts ALTER COLUMN embedding SET STORAGE PLAIN")
    op.create_index(
        "ix_memory_facts_current", "memory_facts", ["user_id"], postgresql_where=CURRENT
    )
    op.create_index(
        "ix_memory_facts_listing", "memory_facts", ["user_id", "status", "created_at", "id"]
    )
    op.create_index(
        "ix_memory_facts_thread_pending", "memory_facts", ["thread_id"], postgresql_where=PENDING
    )
    op.create_index(
        "ix_memory_facts_erase_after",
        "memory_facts",
        ["erase_after"],
        postgresql_where=sa.text("erase_after IS NOT NULL"),
    )
    op.create_index(
        "ix_memory_facts_forgotten",
        "memory_facts",
        ["ended_at"],
        postgresql_where=sa.text("status = 'forgotten'"),
    )
    op.create_index(
        "ix_memory_facts_superseded",
        "memory_facts",
        ["valid_to"],
        postgresql_where=sa.text("valid_to IS NOT NULL"),
    )


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Drop the tables, and the extension when this role created it."""
    for table in SWEPT:
        revoke_from_sweeper(table)
    for table in reversed(TABLES):
        revoke_from_application(scope, table)
        disable_user_isolation(table)
        op.drop_table(table)
    op.execute(DROP_OWN_EXTENSION)
