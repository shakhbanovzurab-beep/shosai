"""What studio offers other slices (studio plan §3.2, ADR 0074).

`MODEL_ROUTES` answers which model serves a role for a person — their choice within the
plan, else the role's default and fallback — with the call's settings, its class and why a
choice was replaced; billing's frontier allowance is asked inside, so every consumer counts
the same way. `MODEL_CATALOGUE` lists the models a person may choose (Settings > Leo).
`PROMPT_RESOLVER` gives the platform layer and the features' addenda from the published
version, and a person's prompt for a role with its skills and their personal context, read
in the caller's transaction. Built-in prompts and output contracts stay with the consumer.
"""

from dataclasses import dataclass
from http import HTTPStatus
from typing import Final, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.ai.calls import CallClass, ModelRoute
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.homes import Home
from shosai.core.ports.keys import PortKey
from shosai.features.billing.contracts import EntitlementSnapshot, TokenRoute
from shosai.features.studio.domain.platform_layer import PlatformFeature
from shosai.features.studio.domain.prompts import SkillText
from shosai.features.studio.domain.roles import ModelCapability, ModelRole, PromptRole, Tier
from shosai.features.studio.domain.routing import Substitution

__all__ = [
    "MODEL_CATALOGUE",
    "MODEL_ROUTES",
    "PROMPT_RESOLVER",
    "ModelCapability",
    "ModelCatalogue",
    "ModelRole",
    "ModelRoleUnconfiguredError",
    "ModelRoutes",
    "OfferedModel",
    "PlatformFeature",
    "PlatformLayer",
    "PromptResolver",
    "PromptRole",
    "ResolvedRoute",
    "RolePrompt",
    "RoutePerson",
    "SkillText",
    "Substitution",
    "Tier",
    "TokenLimitError",
]


@dataclass(frozen=True, slots=True)
class RoutePerson:
    """Whom a route is for: the caller already holds their plan's snapshot."""

    home: Home
    user_id: UUID
    entitlements: EntitlementSnapshot


@dataclass(frozen=True, slots=True)
class ResolvedRoute:
    """The models a call tries and what it is asked with.

    `model_id` is the catalogue id of the model that answers; `substitution` says why it is
    not the person's choice. `temperature` is None for a model that takes none. `token_route`
    is billing's route of the call's tokens: within the allowance, from packs, or fallen back.
    """

    model_id: str
    route: ModelRoute
    tier: Tier
    call_class: CallClass
    temperature: float | None
    max_tokens: int
    reasoning: bool
    substitution: Substitution | None = None
    token_route: TokenRoute = TokenRoute.WITHIN_ALLOWANCE


@dataclass(frozen=True, slots=True)
class OfferedModel:
    """A model a person may choose."""

    id: str
    maker: str
    name: str
    tier: Tier
    capabilities: frozenset[ModelCapability]
    supports_temperature: bool
    supports_reasoning: bool
    max_output_tokens: int


@dataclass(frozen=True, slots=True)
class PlatformLayer:
    """The published platform layer: its version and English text; empty before a publish."""

    version: int | None
    text: str


@dataclass(frozen=True, slots=True)
class RolePrompt:
    """A person's prompt for a role: their instructions, or none for the built-in prompt,
    and the installed skills it appends in order — third-party text the caller wraps."""

    body: str | None
    skills: tuple[SkillText, ...] = ()


class ModelRoleUnconfiguredError(AppError):
    """The role has no default that can answer: the operator has not configured it."""

    def __init__(self, role: ModelRole) -> None:
        super().__init__(
            "model_role_unconfigured", HTTPStatus.SERVICE_UNAVAILABLE, params={"role": role.value}
        )


class TokenLimitError(AppError):
    """The person's standard tokens are spent: the call stops with the limit that ran out
    (billing BL-D4); a used-up frontier week does not stop, the default answers instead."""

    def __init__(self, limit: str) -> None:
        super().__init__("token_limit", HTTPStatus.PAYMENT_REQUIRED, params={"limit": limit})


class ModelRoutes(Protocol):
    """The model of a role for a person, within their plan and allowance."""

    async def route(
        self,
        session: AsyncSession,
        person: RoutePerson,
        role: ModelRole,
        chosen: str | None = None,
        needs: frozenset[ModelCapability] = frozenset(),
    ) -> ResolvedRoute:
        """The route; `chosen` is Leo's model from Settings > Leo, `needs` what this call
        reads beyond the role (a picture). Raises `ModelRoleUnconfiguredError`, and
        `TokenLimitError` when the person's standard tokens are spent."""
        ...


class ModelCatalogue(Protocol):
    """The models a person may choose."""

    async def offered(
        self, person: RoutePerson, capability: ModelCapability | None = None
    ) -> tuple[OfferedModel, ...]:
        """The usable models the person's plan offers, optionally only those that read it."""
        ...

    async def refusal(
        self, person: RoutePerson, model_id: str, role: ModelRole
    ) -> Substitution | None:
        """Why the person may not choose the model for the role; none when they may."""
        ...


class PromptResolver(Protocol):
    """The platform's and a person's prompts."""

    async def platform_layer(self) -> PlatformLayer:
        """The published layer, read from the process's snapshot."""
        ...

    async def feature_prompt(self, feature: PlatformFeature) -> str:
        """The operator's addendum to a feature's prompt; empty when it is off."""
        ...

    async def role_prompt(
        self, session: AsyncSession, user_id: UUID, role: PromptRole
    ) -> RolePrompt:
        """The person's active prompt for the role with its skills, within the budget."""
        ...

    async def personal_context(
        self, session: AsyncSession, user_id: UUID, role: PromptRole | None = None
    ) -> str:
        """The person's own words for an answer in the role — None is Leo's, which always takes
        them — empty when they wrote none or keep them from the role (ST-D2 as amended)."""
        ...


MODEL_ROUTES: Final = PortKey[ModelRoutes]("studio.model_routes")
MODEL_CATALOGUE: Final = PortKey[ModelCatalogue]("studio.model_catalogue")
PROMPT_RESOLVER: Final = PortKey[PromptResolver]("studio.prompt_resolver")
