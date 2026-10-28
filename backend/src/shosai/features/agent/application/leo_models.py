"""The models a person may choose for Leo, from studio's catalogue (studio step 11).

The person's plan is billing's snapshot; studio says whether a model may answer the `leo` role
for them — listed, switched on, reading what Leo needs and frontier only on a frontier plan.
"""

from shosai.core.ports.directory import PortDirectory
from shosai.features.billing.contracts import ENTITLEMENTS
from shosai.features.identity.contracts import Principal
from shosai.features.studio.contracts import MODEL_CATALOGUE, ModelRole, RoutePerson


class CatalogueLeoModels:
    """`LeoModels` over studio's `MODEL_CATALOGUE`."""

    def __init__(self, ports: PortDirectory) -> None:
        self._ports = ports

    async def offers(self, principal: Principal, model_id: str) -> bool:
        """True when the catalogue offers the model to the person's plan for Leo."""
        plan = await self._ports.get(ENTITLEMENTS).snapshot(principal.home, principal.user_id)
        person = RoutePerson(principal.home, principal.user_id, plan)
        refusal = await self._ports.get(MODEL_CATALOGUE).refusal(person, model_id, ModelRole.LEO)
        return refusal is None
