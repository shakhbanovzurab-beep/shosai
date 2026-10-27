"""Catalogue models and catalogues for studio's tests, and Hypothesis strategies of them."""

from dataclasses import replace
from types import MappingProxyType
from typing import TypedDict, Unpack

from hypothesis import strategies as st

from shosai.features.studio.domain.catalogue import CatalogueModel
from shosai.features.studio.domain.defaults import RoleDefault
from shosai.features.studio.domain.roles import (
    TEXT,
    TEXT_AND_VISION,
    ModelCapability,
    ModelRole,
    Tier,
)
from shosai.features.studio.domain.routing import Catalogue


class ModelChanges(TypedDict, total=False):
    """The fields of a catalogue model a test may set."""

    capabilities: frozenset[ModelCapability]
    tier: Tier
    tier_proposed: Tier | None
    tier_declined: Tier | None
    enabled: bool
    retired: bool
    max_output_tokens: int
    supports_temperature: bool
    supports_reasoning: bool


def model(model_id: str, **changes: Unpack[ModelChanges]) -> CatalogueModel:
    """A usable standard text model, with the changes asked for."""
    base = CatalogueModel(
        id=model_id,
        openrouter_id=f"maker/{model_id}",
        name=model_id.title(),
        maker="Maker",
        context_length=128_000,
        max_output_tokens=16_384,
        capabilities=TEXT,
        supports_temperature=True,
        supports_reasoning=False,
        tier=Tier.STANDARD,
    )
    return replace(base, **changes)


def catalogue(
    models: list[CatalogueModel], defaults: dict[ModelRole, RoleDefault] | None = None
) -> Catalogue:
    """A catalogue of these models and defaults."""
    return Catalogue(
        MappingProxyType({item.id: item for item in models}), MappingProxyType(defaults or {})
    )


capability_sets = st.sampled_from([frozenset[ModelCapability](), TEXT, TEXT_AND_VISION])


@st.composite
def catalogue_models(draw: st.DrawFn, model_id: str) -> CatalogueModel:
    """Any model under this id: any tier, capabilities, switches and limits."""
    return model(
        model_id,
        capabilities=draw(capability_sets),
        tier=draw(st.sampled_from(Tier)),
        enabled=draw(st.booleans()),
        retired=draw(st.booleans()),
        max_output_tokens=draw(st.integers(min_value=256, max_value=200_000)),
        supports_temperature=draw(st.booleans()),
        supports_reasoning=draw(st.booleans()),
    )
