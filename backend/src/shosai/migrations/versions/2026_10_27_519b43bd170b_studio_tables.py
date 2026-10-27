"""Studio's tables (studio step 2; ADR 0074).

In the EU home the platform's: the catalogue, a default and fallback per role, the platform
layer's draft and its versions. The application may not delete a catalogue row or a role's
default, and may only insert versions: history is never rewritten. In each home a person's:
their context, prompts, a prompt's skills, the active prompt per role and the model settings
per role, every table personal by row-level security, with composite keys that keep a
prompt's skills and a role's active prompt with the prompt's own person and role.
"""

from datetime import datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from shosai.core.db.migration_scope import (
    EVERY_HOME,
    MigrationScope,
    disable_user_isolation,
    enable_user_isolation,
    grant_to_application,
    revoke_from_application,
    runs_in,
)
from shosai.core.kernel.homes import Home

revision: str = "519b43bd170b"
down_revision: str | None = "c4d1f7a9e2b6"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME

TIERS = "'standard', 'frontier'"
MODEL_ROLES = "'leo', 'live_answers', 'screenshots', 'code', 'system_design', 'notes'"
PROMPT_ROLES = "'live_answers', 'screenshots', 'code', 'system_design', 'notes'"
PLATFORM_TABLES = (
    "models_registry",
    "model_defaults",
    "platform_prompt_drafts",
    "platform_prompt_versions",
)
PERSON_TABLES = (
    "user_contexts",
    "prompt_templates",
    "prompt_skills",
    "role_prompts",
    "model_role_assignments",
)


def check(table: str, sql: str, name: str) -> sa.CheckConstraint:
    """A check constraint named by the project's convention."""
    return sa.CheckConstraint(sql, name=op.f(f"ck_{table}_{name}"))


def moment(name: str, *, nullable: bool = False) -> sa.Column[datetime]:
    """A timestamp column; a required one defaults to now."""
    default = None if nullable else sa.func.now()
    return sa.Column(name, sa.DateTime(timezone=True), server_default=default, nullable=nullable)


def catalogue() -> None:
    """The catalogue of models people may be offered."""
    table = "models_registry"
    op.create_table(
        table,
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("openrouter_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("maker", sa.Text(), nullable=False),
        sa.Column("context_length", sa.Integer(), nullable=False),
        sa.Column("max_output_tokens", sa.Integer(), nullable=False),
        sa.Column("capabilities", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("supports_temperature", sa.Boolean(), nullable=False),
        sa.Column("supports_reasoning", sa.Boolean(), nullable=False),
        sa.Column("tier", sa.Text(), nullable=False),
        sa.Column("tier_proposed", sa.Text(), nullable=True),
        moment("tier_proposed_at", nullable=True),
        sa.Column("tier_declined", sa.Text(), nullable=True),
        moment("tier_confirmed_at"),
        sa.Column("enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
        moment("retired_at", nullable=True),
        moment("upstream_missing_since", nullable=True),
        moment("metadata_synced_at"),
        moment("added_at"),
        moment("updated_at"),
        check(table, "char_length(id) <= 64 AND id ~ '^[a-z0-9]+(-[a-z0-9]+)*$'", "id_slug"),
        check(table, "char_length(openrouter_id) BETWEEN 1 AND 128", "openrouter_id"),
        check(table, "char_length(name) <= 256 AND char_length(maker) <= 128", "names"),
        check(table, "context_length >= 0 AND max_output_tokens >= 0", "limits"),
        check(table, "capabilities <@ ARRAY['text', 'vision']::text[]", "capabilities"),
        check(table, f"tier IN ({TIERS})", "tier_known"),
        check(
            table,
            f"tier_proposed IS NULL OR (tier_proposed IN ({TIERS}) AND tier_proposed <> tier)",
            "tier_proposed",
        ),
        check(table, f"tier_declined IS NULL OR tier_declined IN ({TIERS})", "tier_declined"),
        check(table, "(tier_proposed IS NULL) = (tier_proposed_at IS NULL)", "proposal_dated"),
        check(table, "NOT (enabled AND retired_at IS NOT NULL)", "retired_switched_off"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_models_registry")),
        sa.UniqueConstraint("openrouter_id", name=op.f("uq_models_registry_openrouter_id")),
    )


def defaults() -> None:
    """The default and fallback of each role."""
    table = "model_defaults"
    op.create_table(
        table,
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("model_id", sa.Text(), nullable=False),
        sa.Column("fallback_model_id", sa.Text(), nullable=True),
        moment("updated_at"),
        check(table, f"role IN ({MODEL_ROLES})", "role_known"),
        check(
            table,
            "fallback_model_id IS NULL OR fallback_model_id <> model_id",
            "fallback_differs",
        ),
        sa.ForeignKeyConstraint(
            ["model_id"],
            ["models_registry.id"],
            name=op.f("fk_model_defaults_model_id_models_registry"),
        ),
        sa.ForeignKeyConstraint(
            ["fallback_model_id"],
            ["models_registry.id"],
            name=op.f("fk_model_defaults_fallback_model_id_models_registry"),
        ),
        sa.PrimaryKeyConstraint("role", name=op.f("pk_model_defaults")),
    )


def platform_layer() -> None:
    """The platform layer's draft and its published versions."""
    op.create_table(
        "platform_prompt_drafts",
        sa.Column("id", sa.SmallInteger(), nullable=False),
        sa.Column("config", postgresql.JSONB(), nullable=False),
        moment("updated_at"),
        check("platform_prompt_drafts", "id = 1", "one_draft"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_platform_prompt_drafts")),
    )
    table = "platform_prompt_versions"
    op.create_table(
        table,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("config", postgresql.JSONB(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("restored_from", sa.Integer(), nullable=True),
        moment("published_at"),
        check(table, "number > 0", "number_positive"),
        check(table, "char_length(comment) <= 280", "comment_length"),
        check(
            table,
            "restored_from IS NULL OR (restored_from > 0 AND restored_from < number)",
            "restored_earlier",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_platform_prompt_versions")),
        sa.UniqueConstraint("number", name=op.f("uq_platform_prompt_versions_number")),
    )


def contexts_and_prompts() -> None:
    """A person's context and prompts."""
    op.create_table(
        "user_contexts",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        moment("created_at"),
        moment("updated_at"),
        check("user_contexts", "char_length(content) <= 4000", "content_length"),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_user_contexts")),
    )
    table = "prompt_templates"
    op.create_table(
        table,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        moment("created_at"),
        moment("updated_at"),
        check(table, f"role IN ({PROMPT_ROLES})", "role_known"),
        check(table, "char_length(name) BETWEEN 1 AND 80", "name_length"),
        check(table, "char_length(content) <= 20000", "content_length"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_prompt_templates")),
        sa.UniqueConstraint("user_id", "id", name="uq_prompt_templates_user_id_id"),
        sa.UniqueConstraint("user_id", "id", "role", name="uq_prompt_templates_user_id_id_role"),
    )
    op.create_index(
        "ix_prompt_templates_user_id_updated_at", table, ["user_id", "updated_at"], unique=False
    )


def prompt_links() -> None:
    """A prompt's skills and the active prompt of each role."""
    table = "prompt_skills"
    op.create_table(
        table,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("prompt_id", sa.Uuid(), nullable=False),
        sa.Column("skill_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        check(table, "position BETWEEN 0 AND 19", "position_range"),
        sa.ForeignKeyConstraint(
            ["user_id", "prompt_id"],
            ["prompt_templates.user_id", "prompt_templates.id"],
            name="fk_prompt_skills_user_id_prompt_templates",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_prompt_skills")),
        sa.UniqueConstraint("prompt_id", "skill_id", name="uq_prompt_skills_prompt_id_skill_id"),
        sa.UniqueConstraint("prompt_id", "position", name="uq_prompt_skills_prompt_id_position"),
    )
    op.create_index(
        "ix_prompt_skills_user_id_skill_id", table, ["user_id", "skill_id"], unique=False
    )
    table = "role_prompts"
    op.create_table(
        table,
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("prompt_id", sa.Uuid(), nullable=False),
        moment("updated_at"),
        check(table, f"role IN ({PROMPT_ROLES})", "role_known"),
        sa.ForeignKeyConstraint(
            ["user_id", "prompt_id", "role"],
            ["prompt_templates.user_id", "prompt_templates.id", "prompt_templates.role"],
            name="fk_role_prompts_user_id_prompt_templates",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", "role", name=op.f("pk_role_prompts")),
    )


def model_settings() -> None:
    """A person's model and settings per Studio role."""
    table = "model_role_assignments"
    op.create_table(
        table,
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("model_id", sa.Text(), nullable=True),
        sa.Column("temperature", sa.Numeric(3, 2), nullable=False),
        sa.Column("max_tokens", sa.Integer(), nullable=False),
        sa.Column("reasoning", sa.Boolean(), nullable=False),
        moment("updated_at"),
        check(table, f"role IN ({PROMPT_ROLES})", "role_known"),
        check(
            table, "model_id IS NULL OR char_length(model_id) BETWEEN 1 AND 64", "model_id_length"
        ),
        check(table, "temperature BETWEEN 0 AND 2", "temperature_range"),
        check(table, "max_tokens BETWEEN 256 AND 32768", "max_tokens_range"),
        sa.PrimaryKeyConstraint("user_id", "role", name=op.f("pk_model_role_assignments")),
    )


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Create the platform tables in the EU home and a person's tables in each home."""
    if scope.home is Home.EU:
        catalogue()
        defaults()
        platform_layer()
        grant_to_application(scope, "models_registry", ("SELECT", "INSERT", "UPDATE"))
        grant_to_application(scope, "model_defaults", ("SELECT", "INSERT", "UPDATE"))
        grant_to_application(scope, "platform_prompt_drafts", ("SELECT", "INSERT", "UPDATE"))
        grant_to_application(scope, "platform_prompt_versions", ("SELECT", "INSERT"))
    contexts_and_prompts()
    prompt_links()
    model_settings()
    for table in PERSON_TABLES:
        enable_user_isolation(table)
        grant_to_application(scope, table)


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Drop the tables this revision created, in the reverse order."""
    for table in reversed(PERSON_TABLES):
        revoke_from_application(scope, table)
        disable_user_isolation(table)
    op.drop_table("model_role_assignments")
    op.drop_table("role_prompts")
    op.drop_index("ix_prompt_skills_user_id_skill_id", table_name="prompt_skills")
    op.drop_table("prompt_skills")
    op.drop_index("ix_prompt_templates_user_id_updated_at", table_name="prompt_templates")
    op.drop_table("prompt_templates")
    op.drop_table("user_contexts")
    if scope.home is Home.EU:
        for table in reversed(PLATFORM_TABLES):
            revoke_from_application(scope, table)
        op.drop_table("platform_prompt_versions")
        op.drop_table("platform_prompt_drafts")
        op.drop_table("model_defaults")
        op.drop_table("models_registry")
