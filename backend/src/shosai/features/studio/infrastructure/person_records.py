"""A person's studio tables in their home (studio plan §3.6, ADR 0074).

Every table is personal by nature: row-level security admits the person's own rows only
(ADR 0053), and no foreign key points at `users` — the account registry erases them. The
database keeps the closed sets and lengths, and two composite keys: a prompt's skills and a
role's active prompt belong to the same person as the prompt, and the active prompt's role
is the prompt's own, so a prompt moved to another role must first leave the role it served.
"""

from datetime import datetime
from decimal import Decimal
from typing import Final
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from shosai.core.db.model_base import ModelBase
from shosai.features.studio.domain.catalogue import SLUG_MAX
from shosai.features.studio.domain.prompts import CONTENT_MAX, CONTEXT_MAX, NAME_MAX, SKILLS_MAX
from shosai.features.studio.domain.roles import MAX_TOKENS_CAP, MAX_TOKENS_MIN, PromptRole

ROLES: Final = ", ".join(f"'{role}'" for role in PromptRole)


def created() -> Mapped[datetime]:
    """When the row was written first."""
    return mapped_column(DateTime(timezone=True), server_default=func.now())


def updated() -> Mapped[datetime]:
    """When the row was written last."""
    return mapped_column(DateTime(timezone=True), server_default=func.now())


class ContextRecord(ModelBase):
    """The person's own words about themselves ("About you")."""

    __tablename__ = "user_contexts"
    __table_args__ = (
        CheckConstraint(f"char_length(content) <= {CONTEXT_MAX}", name="content_length"),
    )

    user_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = created()
    updated_at: Mapped[datetime] = updated()


class PromptRecord(ModelBase):
    """A person's prompt for one of the five Studio roles."""

    __tablename__ = "prompt_templates"
    __table_args__ = (
        CheckConstraint(f"role IN ({ROLES})", name="role_known"),
        CheckConstraint(f"char_length(name) BETWEEN 1 AND {NAME_MAX}", name="name_length"),
        CheckConstraint(f"char_length(content) <= {CONTENT_MAX}", name="content_length"),
        # Цели составных ключей навыков промта и активного промта роли.
        UniqueConstraint("user_id", "id", name="uq_prompt_templates_user_id_id"),
        UniqueConstraint("user_id", "id", "role", name="uq_prompt_templates_user_id_id_role"),
        Index("ix_prompt_templates_user_id_updated_at", "user_id", "updated_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(Uuid)
    name: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = created()
    updated_at: Mapped[datetime] = updated()


class PromptSkillRecord(ModelBase):
    """An installed skill a prompt appends, at its position; the skill is agent's row."""

    __tablename__ = "prompt_skills"
    __table_args__ = (
        CheckConstraint(f"position BETWEEN 0 AND {SKILLS_MAX - 1}", name="position_range"),
        ForeignKeyConstraint(
            ("user_id", "prompt_id"),
            ("prompt_templates.user_id", "prompt_templates.id"),
            name="fk_prompt_skills_user_id_prompt_templates",
            ondelete="CASCADE",
        ),
        UniqueConstraint("prompt_id", "skill_id", name="uq_prompt_skills_prompt_id_skill_id"),
        UniqueConstraint("prompt_id", "position", name="uq_prompt_skills_prompt_id_position"),
        # Снятие удалённого навыка со всех промтов человека.
        Index("ix_prompt_skills_user_id_skill_id", "user_id", "skill_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(Uuid)
    prompt_id: Mapped[UUID] = mapped_column(Uuid)
    skill_id: Mapped[UUID] = mapped_column(Uuid)
    position: Mapped[int] = mapped_column(SmallInteger)


class RolePromptRecord(ModelBase):
    """The prompt a role plays by for the person; no row is the built-in prompt."""

    __tablename__ = "role_prompts"
    __table_args__ = (
        CheckConstraint(f"role IN ({ROLES})", name="role_known"),
        ForeignKeyConstraint(
            ("user_id", "prompt_id", "role"),
            ("prompt_templates.user_id", "prompt_templates.id", "prompt_templates.role"),
            name="fk_role_prompts_user_id_prompt_templates",
            ondelete="CASCADE",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    role: Mapped[str] = mapped_column(Text, primary_key=True)
    prompt_id: Mapped[UUID] = mapped_column(Uuid)
    updated_at: Mapped[datetime] = updated()


class RoleModelRecord(ModelBase):
    """The person's model and its settings in one Studio role; no model is the default."""

    __tablename__ = "model_role_assignments"
    __table_args__ = (
        CheckConstraint(f"role IN ({ROLES})", name="role_known"),
        CheckConstraint(
            f"model_id IS NULL OR char_length(model_id) BETWEEN 1 AND {SLUG_MAX}",
            name="model_id_length",
        ),
        CheckConstraint("temperature BETWEEN 0 AND 2", name="temperature_range"),
        CheckConstraint(
            f"max_tokens BETWEEN {MAX_TOKENS_MIN} AND {MAX_TOKENS_CAP}", name="max_tokens_range"
        ),
    )

    user_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    role: Mapped[str] = mapped_column(Text, primary_key=True)
    model_id: Mapped[str | None] = mapped_column(Text)
    temperature: Mapped[Decimal] = mapped_column(Numeric(3, 2))
    max_tokens: Mapped[int] = mapped_column(Integer)
    reasoning: Mapped[bool] = mapped_column(Boolean)
    updated_at: Mapped[datetime] = updated()


PERSON_MODELS: Final = (
    ContextRecord,
    PromptRecord,
    PromptSkillRecord,
    RolePromptRecord,
    RoleModelRecord,
)
