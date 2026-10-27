"""The Decision Layer's tables (decisions step 2; ADR 0069).

In each home, `agent_decisions` and `agent_decision_outcomes`: monthly partitions kept four
months, ids, numbers and codes only, no person's id — so no row-level policy; the
application only inserts, the sweep role reads for the daily reliability pass. In the EU
home, the policies in force (`decision_policies`, one active and one shadow version per
point held by unique indexes) and the fitted threshold revisions (`decision_thresholds`),
platform data without an owner: the application reads, adds and changes a state, never
deletes.
"""

from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from shosai.core.db.migration_scope import (
    EVERY_HOME,
    MigrationScope,
    grant_to_application,
    grant_to_sweeper,
    revoke_from_application,
    revoke_from_sweeper,
    runs_in,
)
from shosai.core.db.partitions.policy import (
    MonthlyPartitions,
    monthly_partition_range,
    register_monthly_partitions,
    unregister_monthly_partitions,
)
from shosai.core.kernel.homes import Home

revision: str = "f27ce6305d53"
down_revision: str | None = "6eef9100b25d"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME

DECISIONS = MonthlyPartitions("agent_decisions", ahead_months=2, keep_months=4)
OUTCOMES = MonthlyPartitions("agent_decision_outcomes", ahead_months=2, keep_months=4)
POINT_FORM = "~ '^[a-z][a-z0-9_]*\\.[a-z][a-z0-9_]*$'"
CODE_FORM = "~ '^[a-z0-9_.,:-]+$'"
SUBJECTS = "'run', 'action', 'text'"
REASONS = (
    "'nothing_to_decide', 'policy_off', 'not_zdr', 'no_consent', 'busy', 'deadline', "
    "'provider_error', 'contract', 'budget', 'judged'"
)
SOURCES = "'rule', 'fallback', 'jev', 'late'"


def check(table: str, sql: str, name: str) -> sa.CheckConstraint:
    """A check constraint named by the project's convention."""
    return sa.CheckConstraint(sql, name=op.f(f"ck_{table}_{name}"))


def column(
    name: str,
    type_: sa.types.TypeEngine[Any] | type[sa.types.TypeEngine[Any]],
    *,
    nullable: bool = False,
    default: str | sa.TextClause | None = None,
) -> sa.Column[Any]:
    """A column; a server default when given."""
    return sa.Column(name, type_, server_default=default, nullable=nullable)


def moment(name: str, *, default_now: bool = False) -> sa.Column[Any]:
    """A timestamp column, now by default when asked."""
    default = sa.text("now()") if default_now else None
    return column(name, sa.DateTime(timezone=True), default=default)


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Create the records in every home and the policies and thresholds in the EU home."""
    create_records()
    for policy in (DECISIONS, OUTCOMES):
        register_monthly_partitions(policy)
        # Только дописываются: приложение не читает, не меняет и не удаляет записи.
        grant_to_application(scope, policy.table, ("INSERT",))
        grant_to_sweeper(policy.table, ("SELECT",))
    if scope.home is Home.EU:
        create_policies()
        grant_to_application(scope, "decision_thresholds", ("SELECT", "INSERT"))
        grant_to_application(scope, "decision_policies", ("SELECT", "INSERT", "UPDATE"))


def create_records() -> None:
    """Decisions and the outcomes reported for their subjects."""
    table = "agent_decisions"
    op.create_table(
        table,
        column("id", sa.Uuid()),
        moment("created_at"),
        column("point", sa.Text()),
        column("version", sa.SmallInteger()),
        column("revision", sa.Integer(), nullable=True),
        column("shadow", sa.Boolean(), default=sa.text("false")),
        column("subject_kind", sa.Text()),
        column("subject_id", sa.Uuid()),
        column("part", sa.Integer(), default="0"),
        column("language", sa.Text()),
        column("facts", postgresql.JSONB()),
        column("state_hash", sa.LargeBinary(), nullable=True),
        column("probabilities", postgresql.JSONB(), default=sa.text("'{}'::jsonb")),
        column("rule_outcome", sa.Text()),
        column("outcome", sa.Text()),
        column("reason", sa.Text()),
        column("source", sa.Text()),
        column("latency_ms", sa.Integer()),
        column("jev_snapshot", sa.Text(), nullable=True),
        column("jev_request_id", sa.Text(), nullable=True),
        check(table, f"point {POINT_FORM}", "point_form"),
        check(table, "version >= 1 AND (revision IS NULL OR revision >= 1)", "versions"),
        check(table, f"subject_kind IN ({SUBJECTS})", "subject_known"),
        check(table, "part >= 0 AND latency_ms >= 0", "counts"),
        check(table, "language ~ '^[a-z]{2,3}(-[A-Za-z]{2,4})?$'", "language_form"),
        check(
            table,
            f"rule_outcome {CODE_FORM} AND outcome {CODE_FORM}"
            " AND length(rule_outcome) <= 640 AND length(outcome) <= 640",
            "outcome_form",
        ),
        check(table, f"reason IN ({REASONS})", "reason_known"),
        check(table, f"source IN ({SOURCES})", "source_known"),
        check(table, "state_hash IS NULL OR octet_length(state_hash) = 16", "state_hash_length"),
        sa.PrimaryKeyConstraint("id", "created_at", name=op.f("pk_agent_decisions")),
        postgresql_partition_by=monthly_partition_range("created_at"),
    )
    op.create_index("ix_agent_decisions_point", table, ["point", "created_at"])
    outcomes = "agent_decision_outcomes"
    op.create_table(
        outcomes,
        column("id", sa.Uuid()),
        moment("created_at"),
        column("point", sa.Text()),
        column("subject_kind", sa.Text()),
        column("subject_id", sa.Uuid()),
        column("part", sa.Integer(), default="0"),
        column("observation", postgresql.JSONB()),
        check(outcomes, f"point {POINT_FORM}", "point_form"),
        check(outcomes, f"subject_kind IN ({SUBJECTS})", "subject_known"),
        check(outcomes, "part >= 0", "part_counted"),
        sa.PrimaryKeyConstraint("id", "created_at", name=op.f("pk_agent_decision_outcomes")),
        postgresql_partition_by=monthly_partition_range("created_at"),
    )
    op.create_index("ix_agent_decision_outcomes_subject", outcomes, ["subject_id"])


def create_policies() -> None:
    """Threshold revisions, then the policies in force that name one."""
    thresholds = "decision_thresholds"
    op.create_table(
        thresholds,
        column("point", sa.Text()),
        column("version", sa.SmallInteger()),
        column("revision", sa.Integer()),
        column("questions_digest", sa.Text()),
        column("cuts", postgresql.JSONB()),
        column("report", postgresql.JSONB()),
        column("passed", sa.Boolean()),
        moment("created_at", default_now=True),
        check(thresholds, f"point {POINT_FORM}", "point_form"),
        check(thresholds, "version >= 1 AND revision >= 1", "versions"),
        check(thresholds, "questions_digest ~ '^[0-9a-f]{16}$'", "digest_form"),
        check(thresholds, "jsonb_typeof(cuts) = 'object'", "cuts_object"),
        sa.PrimaryKeyConstraint(
            "point", "version", "revision", name=op.f("pk_decision_thresholds")
        ),
    )
    policies = "decision_policies"
    op.create_table(
        policies,
        column("point", sa.Text()),
        column("version", sa.SmallInteger()),
        column("state", sa.Text()),
        column("revision", sa.Integer()),
        column("questions_digest", sa.Text()),
        moment("changed_at", default_now=True),
        column("note", sa.Text(), nullable=True),
        check(policies, f"point {POINT_FORM}", "point_form"),
        check(policies, "state IN ('shadow', 'active', 'retired')", "state_known"),
        check(policies, "version >= 1 AND revision >= 1", "versions"),
        check(policies, "questions_digest ~ '^[0-9a-f]{16}$'", "digest_form"),
        check(policies, "note IS NULL OR length(note) <= 500", "note_length"),
        sa.ForeignKeyConstraint(
            ["point", "version", "revision"],
            [f"{thresholds}.point", f"{thresholds}.version", f"{thresholds}.revision"],
            name=op.f("fk_decision_policies_point_decision_thresholds"),
        ),
        sa.PrimaryKeyConstraint("point", "version", name=op.f("pk_decision_policies")),
    )
    op.create_index(
        "uq_decision_policies_active",
        policies,
        ["point"],
        unique=True,
        postgresql_where=sa.text("state = 'active'"),
    )
    op.create_index(
        "uq_decision_policies_shadow",
        policies,
        ["point"],
        unique=True,
        postgresql_where=sa.text("state = 'shadow'"),
    )


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Drop the policies, the thresholds and the records with their partitions and grants."""
    if scope.home is Home.EU:
        for table in ("decision_policies", "decision_thresholds"):
            revoke_from_application(scope, table)
            op.drop_table(table)
    for policy in (OUTCOMES, DECISIONS):
        revoke_from_sweeper(policy.table)
        revoke_from_application(scope, policy.table)
        unregister_monthly_partitions(policy.table)
        op.drop_table(policy.table)
