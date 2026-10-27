"""The default and the fallback of each role, and what they must be (ST-D3, ADR 0074).

A default answers whoever chose nothing, or whose choice cannot answer: so it is switched on,
still listed, standard — every plan may use it — and reads what its role needs (Leo's also
reads pictures). A fallback follows the same rules and differs from the default. A model
that is a default or a fallback cannot be switched off, retired or made frontier while it is.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from shosai.features.studio.domain.catalogue import CatalogueModel
from shosai.features.studio.domain.errors import StudioRule, StudioRuleError
from shosai.features.studio.domain.roles import DEFAULT_REQUIRED, ModelRole, Tier


@dataclass(frozen=True, slots=True)
class RoleDefault:
    """The model a role takes when the person's choice does not answer, and its fallback."""

    role: ModelRole
    model_id: str
    fallback_id: str | None = None

    @property
    def model_ids(self) -> tuple[str, ...]:
        """The default, then the fallback when there is one."""
        return (self.model_id,) if self.fallback_id is None else (self.model_id, self.fallback_id)


def check_default_model(role: ModelRole, model: CatalogueModel | None) -> CatalogueModel:
    """The model, if it may be a default or fallback of the role; else the rule it breaks."""
    if model is None or model.retired:
        raise StudioRuleError(StudioRule.MODEL_NOT_FOUND)
    if not model.enabled:
        raise StudioRuleError(StudioRule.MODEL_DISABLED, {"model": model.name})
    if model.tier is not Tier.STANDARD:
        raise StudioRuleError(StudioRule.DEFAULT_NOT_STANDARD, {"model": model.name})
    if not model.can(DEFAULT_REQUIRED[role]):
        raise StudioRuleError(
            StudioRule.MODEL_CANT_DO_ROLE, {"model": model.name, "role": role.value}
        )
    return model


def checked_default(
    role: ModelRole,
    model: CatalogueModel | None,
    fallback_id: str | None = None,
    fallback: CatalogueModel | None = None,
) -> RoleDefault:
    """The role's new default and its optional fallback (asked by id), each checked."""
    chosen = check_default_model(role, model)
    if fallback_id is None:
        return RoleDefault(role, chosen.id)
    if fallback_id == chosen.id:
        raise StudioRuleError(StudioRule.FALLBACK_SAME_AS_DEFAULT)
    return RoleDefault(role, chosen.id, check_default_model(role, fallback).id)


def held_by(model_id: str, defaults: Iterable[RoleDefault]) -> bool:
    """Whether a role's default or fallback is the model."""
    return any(model_id in default.model_ids for default in defaults)
