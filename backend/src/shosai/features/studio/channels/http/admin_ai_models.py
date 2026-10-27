"""Admin > AI models on the API (`/v1/admin/ai-models*`, studio plan §3.5, step 4).

Behind the admin's session (ADR 0049). Errors are the platform's envelope with studio's codes
(ADR 0008): `model_not_found` (404), `model_already_listed` and `no_tier_proposal` (409),
`openrouter_unreachable` (503), `model_not_on_openrouter`, `model_is_default`,
`model_enabled`, `model_disabled`, `default_not_standard`, `model_cant_do_role` and
`fallback_same_as_default` (422).
"""

from http import HTTPStatus

from fastapi import APIRouter, Depends, Response

from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import require_admin
from shosai.features.studio.application.ai_models_screen import AiModelsScreen
from shosai.features.studio.application.catalogue_admin import CatalogueAdmin
from shosai.features.studio.channels.http.admin_ai_models_views import (
    AdminAiModel,
    AdminAiModelAdd,
    AdminAiModels,
    AdminAiModelSwitch,
    AdminConnectionCheck,
    AdminRoleDefault,
    AdminRoleDefaultBody,
    AdminTierDecision,
    check_of,
    default_view,
    leo_default_of,
    model_of,
    screen_of,
)
from shosai.features.studio.channels.http.refusals import refused
from shosai.features.studio.domain.catalogue import CatalogueModel
from shosai.features.studio.domain.roles import ModelRole


def build_admin_ai_models_router(
    parts: tuple[CatalogueAdmin, AiModelsScreen], ports: PortDirectory
) -> APIRouter:
    """The admin's routes over the catalogue, the defaults and the spend."""
    admin, screen = parts
    router = APIRouter(
        prefix="/v1/admin/ai-models", tags=["admin"], dependencies=[Depends(require_admin(ports))]
    )

    async def answered(model: CatalogueModel) -> AdminAiModel:
        """A changed model with its prices and this month's use."""
        leo = leo_default_of(await admin.defaults())
        return model_of(await screen.row(model), leo)

    @router.get("")
    async def ai_models() -> AdminAiModels:
        """The catalogue, the defaults, the month's spend and the OpenRouter balance."""
        return screen_of(await screen.screen())

    @router.post("", status_code=HTTPStatus.CREATED)
    async def add_model(body: AdminAiModelAdd) -> AdminAiModel:
        """List a model OpenRouter lists, switched off, in the tier its price proposes."""
        with refused():
            model = await admin.add(body.openrouter_id, body.tier)
        return await answered(model)

    @router.patch("/{model_id}")
    async def switch_model(model_id: str, body: AdminAiModelSwitch) -> AdminAiModel:
        """Switch a model on or off; a model a default holds stays on."""
        with refused():
            model = await admin.switch(model_id, enabled=body.enabled)
        return await answered(model)

    @router.delete("/{model_id}", status_code=HTTPStatus.NO_CONTENT)
    async def retire_model(model_id: str) -> Response:
        """Take a switched-off model no role uses out of the catalogue."""
        with refused():
            await admin.retire(model_id)
        return Response(status_code=HTTPStatus.NO_CONTENT)

    @router.post("/{model_id}/tier")
    async def decide_tier(model_id: str, body: AdminTierDecision) -> AdminAiModel:
        """Confirm or decline the tier the model's price proposes; it counts from now."""
        with refused():
            model = await admin.decide_tier(model_id, confirm=body.decision == "confirm")
        return await answered(model)

    @router.put("/defaults/{role}")
    async def set_default(role: ModelRole, body: AdminRoleDefaultBody) -> AdminRoleDefault:
        """A role's default and optional fallback: switched on, standard, able to serve it."""
        with refused():
            default = await admin.set_default(role, body.model_id, body.fallback_model_id)
        return default_view(default)

    @router.post("/check")
    async def check_connection() -> AdminConnectionCheck:
        """Ask OpenRouter's balance now and time the answer."""
        return check_of(await screen.check())

    return router
