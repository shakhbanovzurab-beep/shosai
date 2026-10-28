"""Leo's model for a turn: studio's route of the `leo` role (studio step 11, ADR 0074).

The person's Settings > Leo choice goes to studio as `chosen` (`auto` is none), and a turn with
attachments needs a model that reads pictures. Studio asks billing inside the route: spent
standard tokens are 402 `token_limit`, a used-up frontier week answers with the default. The
route travels with the turn's task, so the worker calls exactly the models admitted here.

Until the operator sets the `leo` role's default in an environment, a turn there answers on
`AGENT_STANDARD_MODEL` as before; studio counts the role as unconfigured, which raises its
ticket. The setting goes once every environment has its defaults (studio plan, step 11).
"""

from typing import Final

import structlog
from pydantic import BaseModel

from shosai.core.ai.calls import CallClass, ModelRef, ModelRoute, Provider
from shosai.core.ai.requests import ReasoningEffort
from shosai.core.db.transactions import HomeTransactions
from shosai.core.ports.directory import PortDirectory
from shosai.features.agent.application.token_admission import standard_tokens
from shosai.features.agent.domain.preferences import AUTO
from shosai.features.billing.contracts import ENTITLEMENTS
from shosai.features.identity.contracts import Principal
from shosai.features.studio.contracts import (
    MODEL_ROUTES,
    ModelCapability,
    ModelRole,
    ModelRoleUnconfiguredError,
    ResolvedRoute,
    RoutePerson,
)

log = structlog.stdlib.get_logger(__name__)
STANDARD_TIER: Final = "standard"
PICTURES = frozenset({ModelCapability.VISION})


class TurnRoute(BaseModel):
    """The models a turn calls, as studio resolved them, and what the call is counted as."""

    primary: str
    fallbacks: tuple[str, ...] = ()
    standard: str | None = None
    call_class: CallClass = CallClass.STANDARD
    tier: str = STANDARD_TIER
    substitution: str | None = None

    @classmethod
    def of(cls, resolved: ResolvedRoute) -> TurnRoute:
        """The task's copy of a resolved route."""
        route = resolved.route
        return cls(
            primary=route.primary.model,
            fallbacks=tuple(model.model for model in route.fallbacks),
            standard=route.standard.model if route.standard is not None else None,
            call_class=resolved.call_class,
            tier=resolved.tier.value,
            substitution=resolved.substitution.value if resolved.substitution else None,
        )

    def model_route(self, reasoning: ReasoningEffort | None) -> ModelRoute:
        """The provider's route; the primary reasons as agent's standard route does."""
        return ModelRoute(
            ModelRef(Provider.OPENROUTER, self.primary),
            tuple(ModelRef(Provider.OPENROUTER, model) for model in self.fallbacks),
            ModelRef(Provider.OPENROUTER, self.standard) if self.standard else None,
            reasoning=reasoning,
        )


def turn_model_route(route: TurnRoute | None, legacy: ModelRoute | None) -> ModelRoute | None:
    """The route a worker calls: studio's from the task, else the legacy standard route. The
    primary reasons as agent's standard route says; the effort judge may raise it per turn."""
    if route is None:
        return legacy
    return route.model_route(legacy.reasoning if legacy is not None else None)


def call_class_of(route: TurnRoute | None) -> CallClass:
    """What the turn's model calls are counted as: expensive for a frontier model."""
    return route.call_class if route is not None else CallClass.STANDARD


def tier_of(route: TurnRoute | None) -> str:
    """The tier a turn's run is recorded and measured in."""
    return route.tier if route is not None else STANDARD_TIER


async def studio_route(
    parts: tuple[PortDirectory, HomeTransactions],
    principal: Principal,
    call: tuple[ModelRole, str | None, frozenset[ModelCapability]],
    *,
    legacy: bool,
) -> tuple[ResolvedRoute | None, str]:
    """Studio's route of a role for the person and billing's route of its tokens; no route is
    the legacy `AGENT_STANDARD_MODEL`, when studio is absent or the role is not configured."""
    ports, transactions = parts
    role, chosen, needs = call
    routes = ports.all(MODEL_ROUTES)
    if not routes:
        return None, (await standard_tokens(ports, principal)).value
    plan = await ports.get(ENTITLEMENTS).snapshot(principal.home, principal.user_id)
    person = RoutePerson(principal.home, principal.user_id, plan)
    try:
        async with transactions.begin(principal.scope(), read_only=True) as session:
            resolved = await routes[0].route(session, person, role, chosen, needs)
    except ModelRoleUnconfiguredError:
        if not legacy:
            raise
        log.warning("Модель роли — AGENT_STANDARD_MODEL: у роли нет умолчания", role=role.value)
        return None, (await standard_tokens(ports, principal)).value
    return resolved, resolved.token_route.value


async def leo_route(
    parts: tuple[PortDirectory, HomeTransactions],
    principal: Principal,
    leo_model: str,
    *,
    pictures: bool,
    legacy: bool,
) -> tuple[TurnRoute | None, str]:
    """Studio's route of Leo's turn, as the task carries it, and its tokens' route."""
    chosen = None if leo_model == AUTO else leo_model
    needs = PICTURES if pictures else frozenset()
    resolved, tokens = await studio_route(
        parts, principal, (ModelRole.LEO, chosen, needs), legacy=legacy
    )
    return (TurnRoute.of(resolved) if resolved is not None else None), tokens
