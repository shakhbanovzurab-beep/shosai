"""The Studio screen's contract (studio plan §3.5): the personal context, prompts, models.

The shapes are the cabinet's: a prompt with its skills in order and the prompt each of the
five roles plays by; the models the person's plan offers and their settings per role. The
limits are the domain's; what a write checks beyond them answers studio's codes.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from shosai.features.studio.application.person_prompts import PersonPromptsState, PromptChanges
from shosai.features.studio.application.person_settings import PersonalContext
from shosai.features.studio.contracts import OfferedModel
from shosai.features.studio.domain.catalogue import SLUG_MAX
from shosai.features.studio.domain.prompts import CONTENT_MAX, CONTEXT_MAX, NAME_MAX, SKILLS_MAX
from shosai.features.studio.domain.roles import (
    TEMPERATURE_MAX,
    TEMPERATURE_MIN,
    ModelCapability,
    PromptRole,
    RoleSettings,
    Tier,
)
from shosai.features.studio.infrastructure.prompt_store import StoredPrompt


class StudioContext(BaseModel):
    """The person's words about themselves; empty with no time before the first save."""

    content: str
    updated_at: datetime | None


class StudioContextUpdate(BaseModel):
    """The context's new text, stored trimmed."""

    model_config = ConfigDict(extra="forbid")

    content: str = Field(max_length=CONTEXT_MAX)


class StudioPrompt(BaseModel):
    """A person's instructions for one role, with installed skills appended in order."""

    id: UUID
    name: str
    role: PromptRole
    content: str
    skill_ids: list[UUID]
    updated_at: datetime


class StudioActivePrompts(BaseModel):
    """The prompt each role plays by; null is the built-in prompt."""

    live_answers: UUID | None
    screenshots: UUID | None
    code: UUID | None
    system_design: UUID | None
    notes: UUID | None


class StudioPrompts(BaseModel):
    """The person's prompts, the last changed first, and the active ones."""

    prompts: list[StudioPrompt]
    active: StudioActivePrompts


class StudioPromptDraft(BaseModel):
    """A new prompt: a name, a role, instructions and installed skills in order."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(max_length=NAME_MAX)
    role: PromptRole
    content: str = Field(default="", max_length=CONTENT_MAX)
    skill_ids: list[UUID] = Field(default_factory=list, max_length=SKILLS_MAX)


class StudioPromptPatch(BaseModel):
    """The fields an edit replaces; a field left out stays."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, max_length=NAME_MAX)
    role: PromptRole | None = None
    content: str | None = Field(default=None, max_length=CONTENT_MAX)
    skill_ids: list[UUID] | None = Field(default=None, max_length=SKILLS_MAX)


class StudioActiveChoice(BaseModel):
    """The prompt a role plays by from now on; null is the built-in prompt."""

    model_config = ConfigDict(extra="forbid")

    role: PromptRole
    prompt_id: UUID | None


class StudioModel(BaseModel):
    """A model the person's plan offers."""

    id: str
    provider: str
    name: str
    tier: Tier
    capabilities: list[ModelCapability]
    supports_temperature: bool
    supports_reasoning: bool
    max_output_tokens: int


class StudioRoleModel(BaseModel):
    """The person's model in a role and how it is called; no model is the role's default."""

    role: PromptRole
    model_id: str | None
    temperature: float
    max_tokens: int
    reasoning: bool


class StudioModels(BaseModel):
    """The models on the person's plan and the settings of the five roles."""

    models: list[StudioModel]
    roles: list[StudioRoleModel]


class StudioRoleModelUpdate(BaseModel):
    """A role's new settings, saved together."""

    model_config = ConfigDict(extra="forbid")

    model_id: str | None = Field(min_length=1, max_length=SLUG_MAX)
    temperature: float = Field(ge=float(TEMPERATURE_MIN), le=float(TEMPERATURE_MAX))
    max_tokens: int
    reasoning: bool


def context_view(context: PersonalContext) -> StudioContext:
    """The contract's context."""
    return StudioContext(content=context.content, updated_at=context.updated_at)


def prompt_view(prompt: StoredPrompt) -> StudioPrompt:
    """The contract's prompt."""
    return StudioPrompt(
        id=prompt.id,
        name=prompt.name,
        role=prompt.role,
        content=prompt.content,
        skill_ids=list(prompt.skill_ids),
        updated_at=prompt.updated_at,
    )


def prompts_view(state: PersonPromptsState) -> StudioPrompts:
    """The contract's prompts and active ones."""
    active = {role.value: prompt_id for role, prompt_id in state.active.items()}
    return StudioPrompts(
        prompts=[prompt_view(prompt) for prompt in state.prompts],
        active=StudioActivePrompts.model_validate(active),
    )


def changes_of(patch: StudioPromptPatch) -> PromptChanges:
    """The domain's changes of a patch."""
    skills = None if patch.skill_ids is None else tuple(patch.skill_ids)
    return PromptChanges(patch.name, patch.role, patch.content, skills)


def model_view(model: OfferedModel) -> StudioModel:
    """The contract's model; its maker is the cabinet's provider."""
    return StudioModel(
        id=model.id,
        provider=model.maker,
        name=model.name,
        tier=model.tier,
        capabilities=sorted(model.capabilities),
        supports_temperature=model.supports_temperature,
        supports_reasoning=model.supports_reasoning,
        max_output_tokens=model.max_output_tokens,
    )


def role_view(role: PromptRole, settings: RoleSettings) -> StudioRoleModel:
    """The contract's settings of a role."""
    return StudioRoleModel(
        role=role,
        model_id=settings.model_id,
        temperature=float(settings.temperature),
        max_tokens=settings.max_tokens,
        reasoning=settings.reasoning,
    )


def settings_of(update: StudioRoleModelUpdate) -> RoleSettings:
    """The domain's settings of an update; the temperature as its decimal text."""
    return RoleSettings(
        update.model_id,
        Decimal(str(update.temperature)),
        update.max_tokens,
        reasoning=update.reasoning,
    )
