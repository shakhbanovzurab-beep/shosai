"""The models a person may choose (`MODEL_CATALOGUE`, studio plan §3.2).

The offer is the snapshot's usable models, frontier ones only on a plan with frontier models,
by maker and name — what Studio's pickers and Settings > Leo list. Whether a person may choose
a model for a role follows the resolution's own rule, so the picker and the answer agree.
"""

from shosai.features.billing.contracts import Capability as PlanCapability
from shosai.features.studio.contracts import OfferedModel, RoutePerson
from shosai.features.studio.domain.catalogue import CatalogueModel
from shosai.features.studio.domain.model_settings import offered
from shosai.features.studio.domain.roles import ModelCapability, ModelRole
from shosai.features.studio.domain.routing import Substitution, refusal
from shosai.features.studio.infrastructure.platform_snapshot import PlatformSnapshot


def frontier_on_plan(person: RoutePerson) -> bool:
    """Whether the person's plan offers frontier models."""
    return PlanCapability.FRONTIER_MODELS in person.entitlements.capabilities


def offer_of(model: CatalogueModel) -> OfferedModel:
    """The contract's view of a catalogue model."""
    return OfferedModel(
        id=model.id,
        maker=model.maker,
        name=model.name,
        tier=model.tier,
        capabilities=model.capabilities,
        supports_temperature=model.supports_temperature,
        supports_reasoning=model.supports_reasoning,
        max_output_tokens=model.output_limit,
    )


class CatalogueOffers:
    """The `MODEL_CATALOGUE` binding over the process's snapshot."""

    def __init__(self, snapshot: PlatformSnapshot) -> None:
        self._snapshot = snapshot

    async def offered(
        self, person: RoutePerson, capability: ModelCapability | None = None
    ) -> tuple[OfferedModel, ...]:
        """The usable models the person's plan offers, optionally only those that read it."""
        catalogue = await self._snapshot.catalogue()
        plan = frontier_on_plan(person)
        models = (offered(model, frontier_on_plan=plan) for model in catalogue.models.values())
        found = [
            model
            for model in models
            if model is not None and (capability is None or capability in model.capabilities)
        ]
        found.sort(key=lambda model: (model.maker.casefold(), model.name.casefold(), model.id))
        return tuple(offer_of(model) for model in found)

    async def refusal(
        self, person: RoutePerson, model_id: str, role: ModelRole
    ) -> Substitution | None:
        """Why the person may not choose the model for the role; none when they may."""
        catalogue = await self._snapshot.catalogue()
        model = catalogue.models.get(model_id)
        return refusal(model, role, frozenset(), frontier_on_plan=frontier_on_plan(person))
