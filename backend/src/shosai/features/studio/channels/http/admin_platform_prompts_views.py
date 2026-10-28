"""The Platform prompts screen's contract (ST-D1, ADR 0074): the trimmed config, its draft,
versions and their summaries.

The config holds the system prompt, the safety rules and blocked topics, and the addenda of
`meeting_summary` and `voice_mode` — no behaviour, confirmations, overrides or placeholders.
Limits are the domain's; what a publish checks beyond them (English, the budget) answers its
own codes.
"""

from collections.abc import Mapping
from datetime import datetime
from types import MappingProxyType
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from shosai.features.studio.application.platform_prompts import Draft, DraftChanges, PromptsState
from shosai.features.studio.domain.platform_layer import (
    FEATURE_PROMPT_MAX,
    RULE_ID_MAX,
    RULE_MAX,
    RULES_LIMIT,
    SYSTEM_PROMPT_MAX,
    TOPIC_MAX,
    TOPICS_LIMIT,
    FeaturePrompt,
    PlatformConfig,
    PlatformFeature,
    SafetyRule,
)
from shosai.features.studio.domain.versions import COMMENT_MAX, Version

Topic = Annotated[str, StringConstraints(min_length=1, max_length=TOPIC_MAX)]


class AdminSafetyRule(BaseModel):
    """One rule of the layer; a disabled rule is kept and not sent."""

    id: str = Field(min_length=1, max_length=RULE_ID_MAX)
    text: str = Field(max_length=RULE_MAX)
    enabled: bool


class AdminSafety(BaseModel):
    """The rules in order and the blocked topics."""

    rules: list[AdminSafetyRule] = Field(max_length=RULES_LIMIT)
    blocked_topics: list[Topic] = Field(max_length=TOPICS_LIMIT)


class AdminFeaturePrompt(BaseModel):
    """The operator's addendum to a feature's prompt."""

    content: str = Field(max_length=FEATURE_PROMPT_MAX)
    enabled: bool


class AdminFeatures(BaseModel):
    """The addenda of the features with their own model call."""

    meeting_summary: AdminFeaturePrompt
    voice_mode: AdminFeaturePrompt


class AdminPlatformConfig(BaseModel):
    """The whole platform layer."""

    system_prompt: str = Field(max_length=SYSTEM_PROMPT_MAX)
    safety: AdminSafety
    features: AdminFeatures


class AdminPlatformDraftPatch(BaseModel):
    """The sections a save replaces whole; a section left out stays."""

    model_config = ConfigDict(extra="forbid")

    system_prompt: str | None = Field(default=None, max_length=SYSTEM_PROMPT_MAX)
    safety: AdminSafety | None = None
    features: AdminFeatures | None = None


class AdminPlatformDraft(BaseModel):
    """The draft; `updated_at` is null before its first save."""

    config: AdminPlatformConfig
    updated_at: datetime | None


class AdminPlatformVersionSummary(BaseModel):
    """A version without its config, for the history list."""

    id: UUID
    number: int
    comment: str
    published_at: datetime
    restored_from: int | None


class AdminPlatformVersion(AdminPlatformVersionSummary):
    """A version whole."""

    config: AdminPlatformConfig


class AdminPlatformPrompts(BaseModel):
    """The draft and the live version, null before the first publish."""

    draft: AdminPlatformDraft
    published: AdminPlatformVersion | None


class AdminPublish(BaseModel):
    """What changed, in the operator's words."""

    model_config = ConfigDict(extra="forbid")

    comment: str = Field(min_length=1, max_length=COMMENT_MAX, pattern=r"\S")


class AdminRestore(BaseModel):
    """An optional comment; the screen words an empty one from `restored_from`."""

    model_config = ConfigDict(extra="forbid")

    comment: str = Field(default="", max_length=COMMENT_MAX)


def config_view(config: PlatformConfig) -> AdminPlatformConfig:
    """The contract's config."""
    features = config.features

    def addendum(feature: PlatformFeature) -> AdminFeaturePrompt:
        prompt = features[feature]
        return AdminFeaturePrompt(content=prompt.content, enabled=prompt.enabled)

    return AdminPlatformConfig(
        system_prompt=config.system_prompt,
        safety=AdminSafety(
            rules=[
                AdminSafetyRule(id=rule.id, text=rule.text, enabled=rule.enabled)
                for rule in config.rules
            ],
            blocked_topics=list(config.blocked_topics),
        ),
        features=AdminFeatures(
            meeting_summary=addendum(PlatformFeature.MEETING_SUMMARY),
            voice_mode=addendum(PlatformFeature.VOICE_MODE),
        ),
    )


def features_of(features: AdminFeatures) -> Mapping[PlatformFeature, FeaturePrompt]:
    """The domain's addenda of the contract's."""
    return MappingProxyType(
        {
            PlatformFeature.MEETING_SUMMARY: FeaturePrompt(
                features.meeting_summary.content, enabled=features.meeting_summary.enabled
            ),
            PlatformFeature.VOICE_MODE: FeaturePrompt(
                features.voice_mode.content, enabled=features.voice_mode.enabled
            ),
        }
    )


def changes_of(patch: AdminPlatformDraftPatch) -> DraftChanges:
    """The domain's changes of a patch."""
    safety = patch.safety
    return DraftChanges(
        system_prompt=patch.system_prompt,
        rules=None
        if safety is None
        else tuple(SafetyRule(rule.id, rule.text, enabled=rule.enabled) for rule in safety.rules),
        blocked_topics=None if safety is None else tuple(safety.blocked_topics),
        features=None if patch.features is None else features_of(patch.features),
    )


def summary_of(version: Version) -> AdminPlatformVersionSummary:
    """The contract's summary of a version."""
    return AdminPlatformVersionSummary(
        id=version.id,
        number=version.number,
        comment=version.comment,
        published_at=version.published_at,
        restored_from=version.restored_from,
    )


def version_view(version: Version) -> AdminPlatformVersion:
    """The contract's whole version."""
    return AdminPlatformVersion(
        **summary_of(version).model_dump(), config=config_view(version.config)
    )


def draft_view(draft: Draft) -> AdminPlatformDraft:
    """The contract's draft."""
    return AdminPlatformDraft(config=config_view(draft.config), updated_at=draft.updated_at)


def state_view(state: PromptsState) -> AdminPlatformPrompts:
    """The contract's state."""
    published = state.published
    return AdminPlatformPrompts(
        draft=draft_view(state.draft),
        published=version_view(published) if published is not None else None,
    )
