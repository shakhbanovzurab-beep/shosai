"""The model of a role for a person (`MODEL_ROUTES`, studio plan §3.3, ADR 0074).

The person's settings of the role are one row read in the caller's transaction; the catalogue
and the defaults are the process's snapshot. The choice answers by the domain's rule, else
the default with the reason, which is counted. Billing is asked inside the route: a frontier
choice whose week is used up gives way to the default, and spent standard tokens stop the
call with `token_limit`. A role whose defaults cannot answer is `model_role_unconfigured`
(503), counted for its ticket. Leo's model is chosen in Settings > Leo and passed as `chosen`;
its call settings are agent's.
"""

import time
from typing import Final

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.ai.calls import CallClass, ModelRef, ModelRoute, Provider
from shosai.core.ai.requests import ReasoningEffort
from shosai.core.ports.directory import PortDirectory
from shosai.features.billing.contracts import TOKEN_ALLOWANCE, ModelTier, TokenLimit, TokenRoute
from shosai.features.studio.application.offers import frontier_on_plan
from shosai.features.studio.contracts import (
    ModelRoleUnconfiguredError,
    ResolvedRoute,
    RoutePerson,
    TokenLimitError,
)
from shosai.features.studio.domain.catalogue import CatalogueModel
from shosai.features.studio.domain.model_settings import call_settings
from shosai.features.studio.domain.roles import (
    LEO_SETTINGS,
    ModelCapability,
    ModelRole,
    PromptRole,
    RoleSettings,
    Tier,
    default_settings,
)
from shosai.features.studio.domain.routing import (
    Catalogue,
    Pick,
    RoleUnservedError,
    allowance_used,
    pick,
    route_models,
)
from shosai.features.studio.infrastructure.person_reads import role_settings
from shosai.features.studio.infrastructure.platform_snapshot import PlatformSnapshot
from shosai.features.studio.infrastructure.route_metrics import RouteMetrics

# Переключатель «Рассуждение» человека: включён — средняя глубина, выключен — минимальная.
REASONING_ON: Final = ReasoningEffort.MEDIUM
REASONING_OFF: Final = ReasoningEffort.MINIMAL
log = structlog.stdlib.get_logger(__name__)


def ref(model: CatalogueModel) -> ModelRef:
    """The provider's name of a catalogue model: studio's models are OpenRouter's."""
    return ModelRef(Provider.OPENROUTER, model.openrouter_id)


def effort(
    model: CatalogueModel, role: ModelRole, settings: RoleSettings
) -> ReasoningEffort | None:
    """The primary's reasoning: the person's switch for a model that reasons; Leo's is agent's."""
    if role is ModelRole.LEO or not model.supports_reasoning:
        return None
    return REASONING_ON if settings.reasoning else REASONING_OFF


class StudioModelRoutes:
    """The `MODEL_ROUTES` binding over the snapshot, billing's allowance and the person's row."""

    def __init__(
        self, snapshot: PlatformSnapshot, ports: PortDirectory, metrics: RouteMetrics
    ) -> None:
        self._snapshot = snapshot
        self._ports = ports
        self._metrics = metrics

    async def route(
        self,
        session: AsyncSession,
        person: RoutePerson,
        role: ModelRole,
        chosen: str | None = None,
        needs: frozenset[ModelCapability] = frozenset(),
    ) -> ResolvedRoute:
        """The route of the role for the person, within their plan and allowance."""
        started = time.perf_counter()
        try:
            return await self._route(session, person, role, (chosen, needs))
        finally:
            self._metrics.resolved(role, time.perf_counter() - started)

    async def _route(
        self,
        session: AsyncSession,
        person: RoutePerson,
        role: ModelRole,
        call: tuple[str | None, frozenset[ModelCapability]],
    ) -> ResolvedRoute:
        chosen, needs = call
        settings = await self._settings(session, person, role)
        choice = chosen if role is ModelRole.LEO else settings.model_id
        catalogue = await self._snapshot.catalogue()
        try:
            picked = pick(role, choice, needs, catalogue, frontier_on_plan=frontier_on_plan(person))
            picked = await self._within_allowance(person, (role, needs), catalogue, picked)
        except RoleUnservedError as error:
            self._metrics.unconfigured(role)
            log.error("У роли нет модели по умолчанию, способной ответить", role=role.value)
            raise ModelRoleUnconfiguredError(role) from error
        if picked.substitution is not None:
            self._metrics.substituted(role, picked.substitution)
        models = route_models(picked, role, needs, catalogue)
        primary = models.primary
        asked = call_settings(primary, settings)
        frontier = primary.tier is Tier.FRONTIER
        return ResolvedRoute(
            model_id=primary.id,
            route=ModelRoute(
                ref(primary),
                tuple(ref(model) for model in models.fallbacks),
                ref(models.standard) if models.standard is not None else None,
                reasoning=effort(primary, role, settings),
            ),
            tier=primary.tier,
            call_class=CallClass.EXPENSIVE if frontier else CallClass.STANDARD,
            temperature=asked.temperature,
            max_tokens=asked.max_tokens,
            reasoning=asked.reasoning,
            substitution=picked.substitution,
        )

    @staticmethod
    async def _settings(
        session: AsyncSession, person: RoutePerson, role: ModelRole
    ) -> RoleSettings:
        """The person's settings of a Studio role, its defaults when unset; Leo's are agent's."""
        if role is ModelRole.LEO:
            return LEO_SETTINGS
        prompt_role = PromptRole(role.value)
        stored = await role_settings(session, person.user_id, prompt_role)
        return stored or default_settings(prompt_role)

    async def _within_allowance(
        self,
        person: RoutePerson,
        call: tuple[ModelRole, frozenset[ModelCapability]],
        catalogue: Catalogue,
        picked: Pick,
    ) -> Pick:
        """The pick billing allows: a used-up frontier week falls back, spent tokens stop."""
        allowance = self._ports.get(TOKEN_ALLOWANCE)
        if picked.model.tier is Tier.FRONTIER:
            frontier = await allowance.decision(person.home, person.user_id, ModelTier.FRONTIER)
            if frontier.route is not TokenRoute.FALL_BACK:
                return picked
            picked = allowance_used(*call, catalogue)
        standard = await allowance.decision(person.home, person.user_id, ModelTier.STANDARD)
        if standard.route is TokenRoute.STOP:
            limit = standard.reason or TokenLimit.STANDARD_DAY
            raise TokenLimitError(limit.value)
        return picked
