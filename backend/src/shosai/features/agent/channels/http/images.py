"""`GET /v1/admin/agent/images/{image_id}`: the operator's picture through a short link.

The panel's `<img>` asks the API with the admin's session; the answer is a 302 to a 15-minute
link of the EU bucket — the API never streams the bytes — and is never cached. A picture whose
thread is gone is 404 `image_not_found`.
"""

from http import HTTPStatus
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from starlette.responses import RedirectResponse

from shosai.core.kernel.errors import AppError
from shosai.features.agent.application.platform_images import PlatformImages
from shosai.features.agent.channels.http.callers import Mount
from shosai.features.identity.contracts import Principal


def build_images_router(images: PlatformImages, mount: Mount) -> APIRouter:
    """The operator's pictures, under the operator's mount only."""
    router = APIRouter(prefix=f"{mount.prefix}/images", tags=list(mount.tags))
    caller = Annotated[Principal, Depends(mount.caller)]

    @router.get(
        "/{image_id}",
        status_code=HTTPStatus.FOUND,
        response_class=RedirectResponse,
        responses={HTTPStatus.NOT_FOUND: {"description": "No such picture of the operator."}},
    )
    async def image(principal: caller, image_id: UUID) -> RedirectResponse:
        """A redirect to a 15-minute link of the picture."""
        link = await images.link(principal.scope(), image_id)
        if link is None:
            raise AppError("image_not_found", HTTPStatus.NOT_FOUND)
        return RedirectResponse(
            link, status_code=HTTPStatus.FOUND, headers={"Cache-Control": "no-store"}
        )

    return router
