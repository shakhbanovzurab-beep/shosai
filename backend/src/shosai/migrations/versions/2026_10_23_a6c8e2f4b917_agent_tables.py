"""Agent's tables in each home (agent step 2; ADR 0068).

Every table is personal by nature: row-level security admits a person's own rows only.
Messages, stored tool results, runs and the action audit are partitioned by month — messages
are kept with their thread, tool results for two months, runs for four, the audit for 12.
The audit is append-only for the application. The sweep role reads threads, runs, actions
and evaluation cases to find what a sweep or a purge must do; the effect then runs as the
person (ADR 0067).
"""

from datetime import datetime
from typing import Any

import sqlalchemy as sa
from alembic import op
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
from shosai.core.db.partitions.policy import (
    MonthlyPartitions,
    monthly_partition_range,
    register_monthly_partitions,
    unregister_monthly_partitions,
)

revision: str = "a6c8e2f4b917"
down_revision: str | None = "e2b4d6f8a135"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME

MESSAGES = MonthlyPartitions("agent_messages", ahead_months=2)
TOOL_RESULTS = MonthlyPartitions("agent_tool_results", ahead_months=2, keep_months=2)
RUNS = MonthlyPartitions("agent_runs", ahead_months=2, keep_months=4)
AUDIT = MonthlyPartitions("agent_audit", ahead_months=2, keep_months=12)
PARTITIONED = (MESSAGES, TOOL_RESULTS, RUNS, AUDIT)
# В порядке ссылок: треды раньше сообщений, действий и оценок, оценки раньше случаев.
TABLES = (
    "agent_threads",
    "agent_messages",
    "agent_tool_results",
    "agent_runs",
    "agent_actions",
    "agent_audit",
    "agent_settings",
    "agent_skills",
    "agent_feedback",
    "agent_eval_cases",
)
SWEPT = ("agent_threads", "agent_runs", "agent_actions", "agent_eval_cases")
EMPTY_JSON_LIST = sa.text("'[]'::jsonb")
EMPTY_UUIDS = sa.text("'{}'::uuid[]")
EMPTY_TEXTS = sa.text("'{}'::text[]")
CODE_FORM = "~ '^[a-z0-9_.:-]{1,64}$'"


def check(table: str, sql: str, name: str) -> sa.CheckConstraint:
    """A check constraint named by the project's convention."""
    return sa.CheckConstraint(sql, name=op.f(f"ck_{table}_{name}"))


def moment(name: str, *, default_now: bool = False, nullable: bool = False) -> sa.Column[datetime]:
    """A timestamp column, defaulting to now when asked."""
    default = sa.func.now() if default_now else None
    return sa.Column(name, sa.DateTime(timezone=True), server_default=default, nullable=nullable)


def uuid(name: str, *, nullable: bool = False) -> sa.Column[Any]:
    """A UUID column."""
    return sa.Column(name, sa.Uuid(), nullable=nullable)


def text(name: str, *, default: str | None = None, nullable: bool = False) -> sa.Column[Any]:
    """A text column, with a server default when given."""
    return sa.Column(name, sa.Text(), server_default=default, nullable=nullable)


def jsonb(name: str, default: sa.TextClause | None = EMPTY_JSON_LIST) -> sa.Column[Any]:
    """A JSONB column, an empty list by default."""
    return sa.Column(name, postgresql.JSONB(), server_default=default, nullable=default is None)


def integer(name: str, *, nullable: bool = False) -> sa.Column[Any]:
    """An integer column; a required one defaults to zero."""
    return sa.Column(
        name, sa.Integer(), server_default=None if nullable else "0", nullable=nullable
    )


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Create threads, messages, tool results, runs, actions, the audit and the person's rows."""
    create_threads()
    create_runs_and_actions()
    create_person_rows()
    for policy in PARTITIONED:
        register_monthly_partitions(policy)
    for table in TABLES:
        enable_user_isolation(table)
        if table == "agent_audit":
            # Журнал только дописывается: приложение не меняет и не удаляет его строки.
            grant_to_application(scope, table, ("SELECT", "INSERT"))
        else:
            grant_to_application(scope, table)
    for table in SWEPT:
        grant_to_sweeper(table, ("SELECT",))


def create_threads() -> None:
    """Threads, their messages and the stored results of tools."""
    op.create_table(
        "agent_threads",
        uuid("id"),
        uuid("user_id"),
        text("scope_kind"),
        uuid("org_id", nullable=True),
        uuid("hub_id", nullable=True),
        text("title"),
        text("title_source", default="question"),
        text("summary", default=""),
        uuid("summary_upto", nullable=True),
        moment("last_activity_at", default_now=True),
        moment("erase_after", nullable=True),
        moment("created_at", default_now=True),
        moment("updated_at", default_now=True),
        check("agent_threads", "scope_kind IN ('personal', 'workspace', 'hub')", "scope_known"),
        check(
            "agent_threads",
            "(org_id IS NOT NULL) = (scope_kind = 'workspace') "
            "AND (hub_id IS NOT NULL) = (scope_kind = 'hub')",
            "scope_names_its_space",
        ),
        check("agent_threads", "char_length(title) BETWEEN 1 AND 120", "title_length"),
        check(
            "agent_threads",
            "title_source IN ('question', 'model', 'person')",
            "title_source_known",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_threads")),
    )
    op.execute(
        "CREATE INDEX ix_agent_threads_scope ON agent_threads "
        "(user_id, scope_kind, org_id, hub_id, last_activity_at DESC, id DESC)"
    )
    op.create_index(
        "ix_agent_threads_erase_after",
        "agent_threads",
        ["erase_after"],
        postgresql_where=sa.text("erase_after IS NOT NULL"),
    )
    create_messages()
    op.create_table(
        "agent_tool_results",
        uuid("id"),
        moment("created_at"),
        uuid("user_id"),
        uuid("run_id"),
        text("tool_name"),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "spaces", postgresql.ARRAY(sa.Uuid()), server_default=EMPTY_UUIDS, nullable=False
        ),
        integer("tokens"),
        check("agent_tool_results", "tokens >= 0", "tokens_not_negative"),
        sa.PrimaryKeyConstraint("id", "created_at", name=op.f("pk_agent_tool_results")),
        postgresql_partition_by=monthly_partition_range("created_at"),
    )
    op.create_index("ix_agent_tool_results_user", "agent_tool_results", ["user_id", "created_at"])


def create_messages() -> None:
    """A thread's rows, in monthly partitions kept with the thread."""
    op.create_table(
        "agent_messages",
        uuid("id"),
        moment("created_at"),
        uuid("thread_id"),
        uuid("user_id"),
        uuid("run_id", nullable=True),
        text("role"),
        text("status", nullable=True),
        text("text", default=""),
        jsonb("tool_calls", None),
        text("tool_call_id", nullable=True),
        text("tool_name", nullable=True),
        jsonb("digest", None),
        uuid("result_id", nullable=True),
        jsonb("attachments"),
        jsonb("steps"),
        jsonb("sources"),
        jsonb("artifacts"),
        sa.Column(
            "action_ids", postgresql.ARRAY(sa.Uuid()), server_default=EMPTY_UUIDS, nullable=False
        ),
        integer("tokens"),
        integer("duration_ms", nullable=True),
        check("agent_messages", "role IN ('user', 'assistant', 'tool', 'server')", "role_known"),
        check(
            "agent_messages",
            "(status IS NULL) = (role <> 'assistant') AND (status IS NULL OR status IN "
            "('done', 'stopped', 'failed'))",
            "answer_has_status",
        ),
        check(
            "agent_messages",
            "(role = 'tool') = (tool_call_id IS NOT NULL AND tool_name IS NOT NULL)",
            "tool_row_names_its_call",
        ),
        check("agent_messages", "tokens >= 0", "tokens_not_negative"),
        sa.ForeignKeyConstraint(
            ["thread_id"],
            ["agent_threads.id"],
            name=op.f("fk_agent_messages_thread_id_agent_threads"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", "created_at", name=op.f("pk_agent_messages")),
        postgresql_partition_by=monthly_partition_range("created_at"),
    )
    op.execute(
        "CREATE INDEX ix_agent_messages_thread ON agent_messages "
        "(thread_id, created_at DESC, id DESC)"
    )


def create_runs_and_actions() -> None:
    """Runs, actions and their audit."""
    op.create_table(
        "agent_runs",
        uuid("id"),
        moment("started_at"),
        uuid("thread_id"),
        uuid("user_id"),
        text("channel"),
        text("status", default="running"),
        text("outcome_code", nullable=True),
        text("model", nullable=True),
        text("tier", nullable=True),
        text("token_route", nullable=True),
        sa.Column("rounds", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column("tool_calls", sa.SmallInteger(), server_default="0", nullable=False),
        integer("input_tokens"),
        integer("cached_tokens"),
        integer("output_tokens"),
        sa.Column("cost_micro_usd", sa.BigInteger(), server_default="0", nullable=False),
        integer("ttft_ms", nullable=True),
        integer("overhead_ms", nullable=True),
        integer("duration_ms", nullable=True),
        jsonb("routing", sa.text("'{}'::jsonb")),
        moment("ended_at", nullable=True),
        check(
            "agent_runs",
            "status IN ('running', 'paused', 'completed', 'failed', 'cancelled')",
            "status_known",
        ),
        check("agent_runs", "channel IN ('web', 'admin')", "channel_known"),
        check(
            "agent_runs", f"outcome_code IS NULL OR outcome_code {CODE_FORM}", "outcome_code_form"
        ),
        check(
            "agent_runs",
            "(status IN ('running', 'paused')) = (ended_at IS NULL)",
            "ended_when_over",
        ),
        sa.PrimaryKeyConstraint("id", "started_at", name=op.f("pk_agent_runs")),
        postgresql_partition_by=monthly_partition_range("started_at"),
    )
    op.execute("CREATE INDEX ix_agent_runs_thread ON agent_runs (thread_id, started_at DESC)")
    op.create_index(
        "ix_agent_runs_live",
        "agent_runs",
        ["status", "started_at"],
        postgresql_where=sa.text("status IN ('running', 'paused')"),
    )
    create_actions()
    create_audit()


def create_audit() -> None:
    """The append-only audit of actions, kept 12 months."""
    op.create_table(
        "agent_audit",
        uuid("id"),
        moment("created_at"),
        uuid("user_id"),
        uuid("action_id"),
        text("item_key", nullable=True),
        text("tool_name", nullable=True),
        text("event"),
        text("via", nullable=True),
        integer("targets", nullable=True),
        text("code", nullable=True),
        check(
            "agent_audit",
            "event IN ('proposed', 'approved', 'rejected', 'expired', 'superseded', 'executed', "
            "'failed', 'outcome_unknown')",
            "event_known",
        ),
        check("agent_audit", f"code IS NULL OR code {CODE_FORM}", "code_form"),
        sa.PrimaryKeyConstraint("id", "created_at", name=op.f("pk_agent_audit")),
        postgresql_partition_by=monthly_partition_range("created_at"),
    )
    op.create_index("ix_agent_audit_action", "agent_audit", ["action_id", "created_at"])
    op.create_index(
        "ix_agent_audit_item",
        "agent_audit",
        ["item_key"],
        postgresql_where=sa.text("item_key IS NOT NULL"),
    )


def create_actions() -> None:
    """The writes Leo proposed, each changed by one conditional update at a time."""
    op.create_table(
        "agent_actions",
        uuid("id"),
        uuid("user_id"),
        uuid("org_id", nullable=True),
        uuid("thread_id", nullable=True),
        uuid("run_id", nullable=True),
        uuid("message_id", nullable=True),
        text("origin"),
        text("origin_key", nullable=True),
        text("status", default="proposed"),
        text("nonce"),
        sa.Column("items", postgresql.JSONB(), nullable=False),
        sa.Column("friction", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column("taint", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column(
            "taint_sources", postgresql.ARRAY(sa.Text()), server_default=EMPTY_TEXTS, nullable=False
        ),
        moment("not_before", nullable=True),
        moment("expires_at"),
        moment("approved_at", nullable=True),
        text("approved_via", nullable=True),
        moment("resolved_at", nullable=True),
        moment("created_at", default_now=True),
        moment("updated_at", default_now=True),
        check(
            "agent_actions",
            "status IN ('proposed', 'approved', 'executing', 'succeeded', 'partially_succeeded', "
            "'failed', 'outcome_unknown', 'rejected', 'expired', 'superseded')",
            "status_known",
        ),
        check("agent_actions", "origin IN ('turn', 'proposal_port')", "origin_known"),
        check(
            "agent_actions", "approved_via IS NULL OR approved_via IN ('web', 'inbox')", "via_known"
        ),
        check("agent_actions", "friction BETWEEN 0 AND 2 AND taint BETWEEN 0 AND 2", "levels"),
        check("agent_actions", "jsonb_array_length(items) BETWEEN 1 AND 20", "items_count"),
        check(
            "agent_actions",
            "(status IN ('proposed', 'approved', 'executing')) = (resolved_at IS NULL)",
            "resolved_when_over",
        ),
        sa.ForeignKeyConstraint(
            ["thread_id"],
            ["agent_threads.id"],
            name=op.f("fk_agent_actions_thread_id_agent_threads"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_actions")),
        sa.UniqueConstraint("user_id", "origin", "origin_key", name="uq_agent_actions_origin_key"),
    )
    op.execute(
        "CREATE INDEX ix_agent_actions_pending ON agent_actions (user_id, created_at DESC) "
        "WHERE status = 'proposed'"
    )
    op.create_index("ix_agent_actions_due", "agent_actions", ["status", "expires_at"])
    op.create_index("ix_agent_actions_resolved", "agent_actions", ["resolved_at"])


def create_person_rows() -> None:
    """Settings > Leo, installed skills, ratings and evaluation cases."""
    op.create_table(
        "agent_settings",
        uuid("user_id"),
        text("leo_model", default="auto"),
        text("response_language", default="auto"),
        text("response_length", default="balanced"),
        sa.Column("web_search", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("voice_mode", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("knowledge_base_search", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "connected_services_search", sa.Boolean(), server_default=sa.true(), nullable=False
        ),
        moment("updated_at", default_now=True),
        check("agent_settings", "char_length(leo_model) BETWEEN 1 AND 200", "leo_model_length"),
        check(
            "agent_settings",
            "char_length(response_language) BETWEEN 2 AND 10",
            "response_language_length",
        ),
        check(
            "agent_settings",
            "response_length IN ('concise', 'balanced', 'detailed')",
            "response_length_known",
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_agent_settings")),
    )
    op.create_table(
        "agent_skills",
        uuid("id"),
        uuid("user_id"),
        text("source"),
        text("repo"),
        text("skill_path", default=""),
        text("ref"),
        text("slug"),
        text("description", default=""),
        text("body"),
        text("source_url", default=""),
        integer("installs", nullable=True),
        sa.Column("has_extra_files", sa.Boolean(), server_default=sa.false(), nullable=False),
        moment("created_at", default_now=True),
        moment("updated_at", default_now=True),
        check("agent_skills", "source IN ('github', 'skills_sh')", "source_known"),
        check("agent_skills", "char_length(repo) BETWEEN 3 AND 140", "repo_length"),
        check("agent_skills", "char_length(skill_path) <= 255", "skill_path_length"),
        check("agent_skills", "char_length(ref) BETWEEN 1 AND 80", "ref_length"),
        check("agent_skills", "char_length(slug) BETWEEN 1 AND 80", "slug_length"),
        check("agent_skills", "char_length(body) BETWEEN 1 AND 24100", "body_length"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_skills")),
        sa.UniqueConstraint("user_id", "repo", "skill_path", name="uq_agent_skills_user_repo_path"),
    )
    op.create_index("ix_agent_skills_user", "agent_skills", ["user_id", "created_at"])
    create_feedback()


def create_feedback() -> None:
    """A rating per answer and the cases the person allowed."""
    op.create_table(
        "agent_feedback",
        uuid("message_id"),
        uuid("user_id"),
        uuid("thread_id"),
        uuid("run_id", nullable=True),
        text("rating"),
        sa.Column("shared", sa.Boolean(), server_default=sa.false(), nullable=False),
        moment("created_at", default_now=True),
        moment("updated_at", default_now=True),
        check("agent_feedback", "rating IN ('useful', 'not_useful')", "rating_known"),
        sa.ForeignKeyConstraint(
            ["thread_id"],
            ["agent_threads.id"],
            name=op.f("fk_agent_feedback_thread_id_agent_threads"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("message_id", name=op.f("pk_agent_feedback")),
    )
    op.create_index("ix_agent_feedback_thread", "agent_feedback", ["thread_id"])
    op.create_table(
        "agent_eval_cases",
        uuid("id"),
        uuid("user_id"),
        uuid("message_id"),
        uuid("thread_id"),
        text("rating"),
        text("language"),
        sa.Column("case", postgresql.JSONB(), nullable=False),
        text("model", nullable=True),
        text("tier", nullable=True),
        sa.Column(
            "toolsets", postgresql.ARRAY(sa.Text()), server_default=EMPTY_TEXTS, nullable=False
        ),
        text("prompt_version"),
        moment("created_at", default_now=True),
        check("agent_eval_cases", "rating IN ('useful', 'not_useful')", "rating_known"),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["agent_feedback.message_id"],
            name=op.f("fk_agent_eval_cases_message_id_agent_feedback"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["thread_id"],
            ["agent_threads.id"],
            name=op.f("fk_agent_eval_cases_thread_id_agent_threads"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_eval_cases")),
        sa.UniqueConstraint("message_id", name="uq_agent_eval_cases_message_id"),
    )
    op.create_index("ix_agent_eval_cases_user", "agent_eval_cases", ["user_id"])
    op.create_index("ix_agent_eval_cases_created", "agent_eval_cases", ["created_at"])


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Drop every agent table with its partitions, policies and grants."""
    for table in SWEPT:
        revoke_from_sweeper(table)
    for table in reversed(TABLES):
        revoke_from_application(scope, table)
        disable_user_isolation(table)
    for policy in PARTITIONED:
        unregister_monthly_partitions(policy.table)
    for table in reversed(TABLES):
        op.drop_table(table)
