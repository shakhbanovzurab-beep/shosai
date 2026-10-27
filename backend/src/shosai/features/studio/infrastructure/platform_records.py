"""Studio's platform tables, in the EU home only (studio plan §3.6, ADR 0005, ADR 0074).

The catalogue's rows are never deleted — costs and people's choices name a model softly —
so the application may insert and update them but not delete; a model leaves by being
retired, which also switches it off. A role's default and fallback point at the catalogue
and differ. The platform layer has one draft and numbered versions the application may only
insert: history is never rewritten.
"""

from datetime import datetime
from typing import Any, Final
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    Text,
    Uuid,
    false,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from shosai.core.db.model_base import ModelBase, table_info
from shosai.core.kernel.homes import Home
from shosai.features.studio.domain.catalogue import SLUG_MAX
from shosai.features.studio.domain.roles import ModelCapability, ModelRole, Tier
from shosai.features.studio.domain.versions import COMMENT_MAX

EU_ONLY: Final = table_info(homes=(Home.EU,))
TIERS: Final = ", ".join(f"'{tier}'" for tier in Tier)
ROLES: Final = ", ".join(f"'{role}'" for role in ModelRole)
CAPABILITIES: Final = ", ".join(f"'{capability}'" for capability in ModelCapability)
OPENROUTER_ID_MAX: Final = 128
NAME_MAX: Final = 256
MAKER_MAX: Final = 128


class CatalogueRecord(ModelBase):
    """A model of the catalogue."""

    __tablename__ = "models_registry"
    __table_args__ = (
        CheckConstraint(
            f"char_length(id) <= {SLUG_MAX} AND id ~ '^[a-z0-9]+(-[a-z0-9]+)*$'", name="id_slug"
        ),
        CheckConstraint(
            f"char_length(openrouter_id) BETWEEN 1 AND {OPENROUTER_ID_MAX}", name="openrouter_id"
        ),
        CheckConstraint(
            f"char_length(name) <= {NAME_MAX} AND char_length(maker) <= {MAKER_MAX}", name="names"
        ),
        CheckConstraint("context_length >= 0 AND max_output_tokens >= 0", name="limits"),
        CheckConstraint(f"capabilities <@ ARRAY[{CAPABILITIES}]::text[]", name="capabilities"),
        CheckConstraint(f"tier IN ({TIERS})", name="tier_known"),
        CheckConstraint(
            f"tier_proposed IS NULL OR (tier_proposed IN ({TIERS}) AND tier_proposed <> tier)",
            name="tier_proposed",
        ),
        CheckConstraint(
            f"tier_declined IS NULL OR tier_declined IN ({TIERS})", name="tier_declined"
        ),
        CheckConstraint(
            "(tier_proposed IS NULL) = (tier_proposed_at IS NULL)", name="proposal_dated"
        ),
        CheckConstraint("NOT (enabled AND retired_at IS NOT NULL)", name="retired_switched_off"),
        {"info": EU_ONLY},
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    openrouter_id: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text)
    maker: Mapped[str] = mapped_column(Text)
    context_length: Mapped[int] = mapped_column(Integer)
    max_output_tokens: Mapped[int] = mapped_column(Integer)
    capabilities: Mapped[list[str]] = mapped_column(ARRAY(Text))
    supports_temperature: Mapped[bool] = mapped_column(Boolean)
    supports_reasoning: Mapped[bool] = mapped_column(Boolean)
    tier: Mapped[str] = mapped_column(Text)
    tier_proposed: Mapped[str | None] = mapped_column(Text)
    tier_proposed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    tier_declined: Mapped[str | None] = mapped_column(Text)
    tier_confirmed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    enabled: Mapped[bool] = mapped_column(Boolean, server_default=false())
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    upstream_missing_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RoleDefaultRecord(ModelBase):
    """The default and the fallback of one role."""

    __tablename__ = "model_defaults"
    __table_args__ = (
        CheckConstraint(f"role IN ({ROLES})", name="role_known"),
        CheckConstraint(
            "fallback_model_id IS NULL OR fallback_model_id <> model_id",
            name="fallback_differs",
        ),
        {"info": EU_ONLY},
    )

    role: Mapped[str] = mapped_column(Text, primary_key=True)
    model_id: Mapped[str] = mapped_column(Text, ForeignKey("models_registry.id"))
    fallback_model_id: Mapped[str | None] = mapped_column(Text, ForeignKey("models_registry.id"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PlatformDraftRecord(ModelBase):
    """The operator's draft of the platform layer: one row."""

    __tablename__ = "platform_prompt_drafts"
    __table_args__ = (CheckConstraint("id = 1", name="one_draft"), {"info": EU_ONLY})

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    config: Mapped[dict[str, Any]] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PlatformVersionRecord(ModelBase):
    """A published version of the platform layer; the application only inserts them."""

    __tablename__ = "platform_prompt_versions"
    __table_args__ = (
        CheckConstraint("number > 0", name="number_positive"),
        CheckConstraint(f"char_length(comment) <= {COMMENT_MAX}", name="comment_length"),
        CheckConstraint(
            "restored_from IS NULL OR (restored_from > 0 AND restored_from < number)",
            name="restored_earlier",
        ),
        {"info": EU_ONLY},
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    number: Mapped[int] = mapped_column(Integer, unique=True)
    config: Mapped[dict[str, Any]] = mapped_column(JSONB)
    comment: Mapped[str] = mapped_column(Text)
    restored_from: Mapped[int | None] = mapped_column(Integer)
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


PLATFORM_MODELS: Final = (
    CatalogueRecord,
    RoleDefaultRecord,
    PlatformDraftRecord,
    PlatformVersionRecord,
)
