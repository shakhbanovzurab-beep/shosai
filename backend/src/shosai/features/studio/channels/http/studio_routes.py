"""The person's Studio on the API (`/v1/studio/*`, studio plan §3.5).

Behind the person's bearer token; every row is the person's own, so another person's prompt
is `prompt_not_found` on every route. A create takes an `Idempotency-Key`: a retry returns
the prompt the first run wrote. Errors are the platform's envelope with studio's codes
(ADR 0008): `prompt_not_found` (404), `prompt_limit_reached` (409), and 422 for
`prompt_name_required`, `skill_not_installed`, `prompt_over_budget`, `prompt_for_other_role`,
`model_not_on_plan`, `model_cant_do_role` and `max_tokens_range`.
"""

from http import HTTPStatus
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response

from shosai.core.idempotency.http import IdempotencyKeyHeader
from shosai.core.idempotency.ledger import EffectKey, account_key, fingerprint_of
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import Principal, bearer_principal
from shosai.features.studio.application.person_prompts import CREATE, PersonPrompts
from shosai.features.studio.application.person_settings import PersonSettings
from shosai.features.studio.channels.http.refusals import refused
from shosai.features.studio.channels.http.studio_views import (
    StudioActiveChoice,
    StudioContext,
    StudioContextUpdate,
    StudioModels,
    StudioPrompt,
    StudioPromptDraft,
    StudioPromptPatch,
    StudioPrompts,
    StudioRoleModel,
    StudioRoleModelUpdate,
    changes_of,
    context_view,
    model_view,
    prompt_view,
    prompts_view,
    role_view,
    settings_of,
)
from shosai.features.studio.domain.prompts import PromptDraft
from shosai.features.studio.domain.roles import PromptRole


def build_studio_router(
    services: tuple[PersonPrompts, PersonSettings], ports: PortDirectory
) -> APIRouter:
    """The person's routes of Studio."""
    prompts, settings = services
    router = APIRouter(prefix="/v1/studio", tags=["studio"])
    person = Annotated[Principal, Depends(bearer_principal(ports))]

    @router.get("/context")
    async def read_context(principal: person) -> StudioContext:
        """The person's words about themselves."""
        return context_view(await settings.context(principal))

    @router.put("/context")
    async def save_context(body: StudioContextUpdate, principal: person) -> StudioContext:
        """Replace the person's context; it is stored trimmed."""
        with refused():
            return context_view(await settings.save_context(principal, body.content))

    @router.get("/prompts")
    async def list_prompts(principal: person) -> StudioPrompts:
        """The person's prompts, the last changed first, and the prompt each role plays by."""
        return prompts_view(await prompts.state(principal))

    @router.post("/prompts", status_code=HTTPStatus.CREATED)
    async def create_prompt(
        body: StudioPromptDraft, principal: person, key: IdempotencyKeyHeader
    ) -> StudioPrompt:
        """Write a new prompt; a retry with the same key returns the same prompt."""
        draft = PromptDraft(body.name, body.role, body.content, tuple(body.skill_ids))
        effect = EffectKey(CREATE, account_key(principal.user_id, key), fingerprint_of(body))
        with refused():
            return prompt_view(await prompts.create(principal, draft, effect))

    @router.put("/prompts/active")
    async def choose_prompt(body: StudioActiveChoice, principal: person) -> StudioPrompts:
        """Choose the prompt a role plays by; null is the built-in prompt."""
        with refused():
            return prompts_view(await prompts.choose(principal, body.role, body.prompt_id))

    @router.patch("/prompts/{prompt_id}")
    async def edit_prompt(
        prompt_id: UUID, body: StudioPromptPatch, principal: person
    ) -> StudioPrompt:
        """Replace the given fields; a new role leaves the role the prompt served."""
        with refused():
            return prompt_view(await prompts.update(principal, prompt_id, changes_of(body)))

    @router.delete("/prompts/{prompt_id}", status_code=HTTPStatus.NO_CONTENT)
    async def delete_prompt(prompt_id: UUID, principal: person) -> Response:
        """Delete the prompt; a role that played by it goes back to the built-in prompt."""
        with refused():
            await prompts.delete(principal, prompt_id)
        return Response(status_code=HTTPStatus.NO_CONTENT)

    @router.get("/models")
    async def list_models(principal: person) -> StudioModels:
        """The models on the person's plan and the settings of the five roles."""
        found = await settings.models(principal)
        return StudioModels(
            models=[model_view(model) for model in found.models],
            roles=[role_view(role, values) for role, values in found.roles],
        )

    @router.put("/models/roles/{role}")
    async def save_role_model(
        role: PromptRole, body: StudioRoleModelUpdate, principal: person
    ) -> StudioRoleModel:
        """Save which model fills the role and how it is called."""
        with refused():
            return role_view(role, await settings.save_role(principal, role, settings_of(body)))

    return router
