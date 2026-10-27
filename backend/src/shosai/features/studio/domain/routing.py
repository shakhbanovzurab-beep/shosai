"""Which model answers a role for a person, and which follow it (studio plan §3.3, ADR 0074).

The person's choice answers when one rule holds: listed, switched on, able to read what the
role and the call need, and frontier only on a plan with frontier models. Otherwise the
role's default answers, then its fallback, and the reason is kept. A standard model falls
back to the role's standard models; a frontier one never falls back across tiers — its
`standard` is what the kill switch takes. When billing says the frontier week is used up,
the default answers in its place.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from shosai.features.studio.domain.catalogue import CatalogueModel
from shosai.features.studio.domain.defaults import RoleDefault
from shosai.features.studio.domain.roles import REQUIRED, Capability, ModelRole, Tier


class Substitution(StrEnum):
    """Why the person's choice did not answer; the value reaches metrics and the agent."""

    NOT_LISTED = "not_listed"
    DISABLED = "disabled"
    CANT_DO_ROLE = "cant_do_role"
    NOT_ON_PLAN = "not_on_plan"
    FRONTIER_ALLOWANCE_USED = "frontier_allowance_used"


class RoleUnservedError(LookupError):
    """No default or fallback of the role can answer: the role is not configured."""

    def __init__(self, role: ModelRole) -> None:
        super().__init__(role.value)
        self.role = role


@dataclass(frozen=True, slots=True)
class Catalogue:
    """The platform's catalogue and defaults, as one process holds them."""

    models: Mapping[str, CatalogueModel]
    defaults: Mapping[ModelRole, RoleDefault]


@dataclass(frozen=True, slots=True)
class Pick:
    """The model that answers and, when it is not the person's choice, why."""

    model: CatalogueModel
    substitution: Substitution | None = None


@dataclass(frozen=True, slots=True)
class RouteModels:
    """The model that answers, the same-tier models after it, and the kill switch's one."""

    primary: CatalogueModel
    fallbacks: tuple[CatalogueModel, ...]
    standard: CatalogueModel | None


def refusal(
    model: CatalogueModel | None,
    role: ModelRole,
    needs: frozenset[Capability],
    *,
    frontier_on_plan: bool,
) -> Substitution | None:
    """Why the model may not answer the role for this person; none when it may."""
    if model is None or model.retired:
        return Substitution.NOT_LISTED
    if not model.enabled:
        return Substitution.DISABLED
    if not model.can(REQUIRED[role] | needs):
        return Substitution.CANT_DO_ROLE
    if model.tier is Tier.FRONTIER and not frontier_on_plan:
        return Substitution.NOT_ON_PLAN
    return None


def role_models(
    role: ModelRole, needs: frozenset[Capability], catalogue: Catalogue
) -> tuple[CatalogueModel, ...]:
    """The role's default and fallback that can answer this call, in order."""
    default = catalogue.defaults.get(role)
    if default is None:
        return ()
    models = (catalogue.models.get(model_id) for model_id in default.model_ids)
    return tuple(
        model
        for model in models
        if model is not None
        and model.tier is Tier.STANDARD
        and refusal(model, role, needs, frontier_on_plan=False) is None
    )


def default_model(
    role: ModelRole, needs: frozenset[Capability], catalogue: Catalogue
) -> CatalogueModel:
    """The first of the role's defaults that can answer; none is a role not configured."""
    models = role_models(role, needs, catalogue)
    if not models:
        raise RoleUnservedError(role)
    return models[0]


def pick(
    role: ModelRole,
    choice: str | None,
    needs: frozenset[Capability],
    catalogue: Catalogue,
    *,
    frontier_on_plan: bool,
) -> Pick:
    """The person's choice when it may answer, else the role's default with the reason."""
    if choice is None:
        return Pick(default_model(role, needs, catalogue))
    model = catalogue.models.get(choice)
    reason = refusal(model, role, needs, frontier_on_plan=frontier_on_plan)
    if model is not None and reason is None:
        return Pick(model)
    return Pick(default_model(role, needs, catalogue), reason)


def allowance_used(role: ModelRole, needs: frozenset[Capability], catalogue: Catalogue) -> Pick:
    """The default in place of a frontier choice whose week is used up (BL-D4)."""
    return Pick(default_model(role, needs, catalogue), Substitution.FRONTIER_ALLOWANCE_USED)


def route_models(
    chosen: Pick, role: ModelRole, needs: frozenset[Capability], catalogue: Catalogue
) -> RouteModels:
    """The models a call tries: same-tier fallbacks for a standard model, none for frontier."""
    primary = chosen.model
    standard = role_models(role, needs, catalogue)
    if primary.tier is Tier.FRONTIER:
        return RouteModels(primary, (), standard[0] if standard else None)
    after = tuple(model for model in standard if model.id != primary.id)
    return RouteModels(primary, after, None)
