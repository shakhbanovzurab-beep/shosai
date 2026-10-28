"""Admin > Platform prompts on the API (`/v1/admin/platform-prompts*`, studio plan §3.5).

Behind the admin's session (ADR 0049). A publish and a restore take an `Idempotency-Key`: a
retry returns the version the first run wrote. Errors are the platform's envelope with studio's
codes (ADR 0008): `platform_prompt_not_english` and `platform_layer_over_budget` (422, with the
field), `nothing_to_publish` (409), `version_not_found` (404), `invalid_cursor` (422).
"""

from http import HTTPStatus
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from shosai.core.idempotency.http import IdempotencyKeyHeader
from shosai.core.idempotency.ledger import EffectKey, fingerprint_of
from shosai.core.pagination.page import Page, PageRequest, page_parameters
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import require_admin
from shosai.features.studio.application.platform_prompts import (
    PUBLISH,
    RESTORE,
    PlatformPrompts,
)
from shosai.features.studio.channels.http.admin_platform_prompts_views import (
    AdminPlatformDraft,
    AdminPlatformDraftPatch,
    AdminPlatformPrompts,
    AdminPlatformVersion,
    AdminPlatformVersionSummary,
    AdminPublish,
    AdminRestore,
    changes_of,
    draft_view,
    state_view,
    summary_of,
    version_view,
)
from shosai.features.studio.channels.http.refusals import refused

VERSIONS_PAGE = Depends(page_parameters(default=20, maximum=100))


class RestoreRequest(BaseModel):
    """What a restore's key is bound to: the version and the comment."""

    version_id: UUID
    comment: str


def admin_key(client_key: str) -> str:
    """The client's key in the one admin's space (ADR 0049)."""
    return f"admin:{client_key}"


def build_admin_platform_prompts_router(
    prompts: PlatformPrompts, ports: PortDirectory
) -> APIRouter:
    """The admin's routes over the platform layer."""
    router = APIRouter(
        prefix="/v1/admin/platform-prompts",
        tags=["admin"],
        dependencies=[Depends(require_admin(ports))],
    )

    @router.get("")
    async def platform_prompts() -> AdminPlatformPrompts:
        """The draft and the live version."""
        return state_view(await prompts.state())

    @router.patch("/draft")
    async def save_draft(body: AdminPlatformDraftPatch) -> AdminPlatformDraft:
        """Replace the given sections of the draft; the last save wins."""
        return draft_view(await prompts.save_draft(changes_of(body)))

    @router.post("/publish", status_code=HTTPStatus.CREATED)
    async def publish(body: AdminPublish, key: IdempotencyKeyHeader) -> AdminPlatformPrompts:
        """Publish the draft as the next version, checked for English and its budget."""
        effect = EffectKey(PUBLISH, admin_key(key), fingerprint_of(body))
        with refused():
            return state_view(await prompts.publish(body.comment, effect))

    @router.get("/versions")
    async def versions(
        page: Annotated[PageRequest, VERSIONS_PAGE],
    ) -> Page[AdminPlatformVersionSummary]:
        """The versions, newest first, without their configs."""
        found, cursor = await prompts.versions(page)
        return Page(items=[summary_of(version) for version in found], next_cursor=cursor)

    @router.get("/versions/{version_id}")
    async def version(version_id: UUID) -> AdminPlatformVersion:
        """One version whole, for the compare dialog."""
        with refused():
            return version_view(await prompts.version(version_id))

    @router.post("/versions/{version_id}/restore", status_code=HTTPStatus.CREATED)
    async def restore(
        version_id: UUID, body: AdminRestore, key: IdempotencyKeyHeader
    ) -> AdminPlatformPrompts:
        """Publish a copy of an old version as the next one; the draft becomes it."""
        request = RestoreRequest(version_id=version_id, comment=body.comment)
        effect = EffectKey(RESTORE, admin_key(key), fingerprint_of(request))
        with refused():
            return state_view(await prompts.restore(version_id, body.comment, effect))

    return router
