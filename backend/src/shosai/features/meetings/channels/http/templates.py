"""The templates of Leo's write-up: `/v1/meetings/templates` (plan step 7b).

- `GET` lists every template the person may use, shipped first, in one page.
- `POST` makes one of their own (201), once per `Idempotency-Key` when one is sent.
- `PUT /{id}` replaces it, and `DELETE /{id}` deletes it (204).

A shipped template is read-only. Errors: `template_not_found`, `template_builtin_read_only`,
`templates_limit_reached`, the template rules' codes (`template_name_required`, …),
`idempotency_key_reused`.
"""

from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, Response

from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import Principal, bearer_principal
from shosai.features.meetings.application.templates import TemplateRequest, Templates
from shosai.features.meetings.channels.http.folders import OptionalIdempotencyKey
from shosai.features.meetings.channels.http.library_models import (
    TemplateIn,
    TemplateOut,
    TemplatesOut,
    template_out,
)


def request_of(body: TemplateIn) -> TemplateRequest:
    """The service's request for a body."""
    return TemplateRequest(
        name=body.name, description=body.description, icon=body.icon, sections=body.request()
    )


def build_templates_router(templates: Templates, ports: PortDirectory) -> APIRouter:
    """The templates a person may use."""
    router = APIRouter(prefix="/v1/meetings/templates", tags=["meetings"])
    signed_in = bearer_principal(ports)

    @router.get("")
    async def list_templates(principal: Annotated[Principal, Depends(signed_in)]) -> TemplatesOut:
        """The shipped templates, then yours, oldest first."""
        return TemplatesOut(items=[template_out(t) for t in await templates.every(principal)])

    @router.post("", status_code=HTTPStatus.CREATED)
    async def create_template(
        principal: Annotated[Principal, Depends(signed_in)],
        body: TemplateIn,
        idempotency_key: OptionalIdempotencyKey = None,
    ) -> TemplateOut:
        """Make a template of your own."""
        made = await templates.create(principal, request_of(body), idempotency_key)
        return template_out(made)

    @router.put("/{template_id}")
    async def replace_template(
        principal: Annotated[Principal, Depends(signed_in)], template_id: str, body: TemplateIn
    ) -> TemplateOut:
        """Replace a template of yours."""
        return template_out(await templates.replace(principal, template_id, request_of(body)))

    @router.delete("/{template_id}", status_code=HTTPStatus.NO_CONTENT)
    async def delete_template(
        principal: Annotated[Principal, Depends(signed_in)], template_id: str
    ) -> Response:
        """Delete a template of yours."""
        await templates.delete(principal, template_id)
        return Response(status_code=HTTPStatus.NO_CONTENT)

    return router
