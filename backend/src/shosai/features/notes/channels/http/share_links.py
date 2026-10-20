"""A meeting's share link: `GET`, `PUT` and `DELETE /v1/notes/{id}/share-link` (step 13).

`PUT` turns the link on with its settings or changes them (the token is kept); `DELETE`
turns it off with its comments, so the next link has a new token. Errors:
`meeting_not_found`, `meeting_read_only`, `private_meeting`.
"""

from http import HTTPStatus
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict

from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import Principal, bearer_principal
from shosai.features.notes.application.share_links import ShareLinks
from shosai.features.notes.channels.http.shared_shapes import ShareLinkAnswer, link_out
from shosai.features.notes.domain.sharing import ShareExpiry, ShareSettings


class ShareSettingsIn(BaseModel):
    """What the link's page shows and allows, and how long it works."""

    model_config = ConfigDict(extra="forbid")

    show_transcript: bool = True
    show_names: bool = False
    allow_comments: bool = False
    expiry: ShareExpiry = ShareExpiry.NEVER


def build_share_links_router(links: ShareLinks, ports: PortDirectory) -> APIRouter:
    """The meeting's share link, for whoever may manage the meeting."""
    router = APIRouter(prefix="/v1/notes/{meeting_id}/share-link", tags=["notes"])
    signed_in = bearer_principal(ports)

    @router.get("")
    async def get_share_link(
        principal: Annotated[Principal, Depends(signed_in)], meeting_id: UUID
    ) -> ShareLinkAnswer:
        """The meeting's link; null while it is off."""
        return link_out(await links.link(principal, meeting_id))

    @router.put("")
    async def put_share_link(
        principal: Annotated[Principal, Depends(signed_in)],
        meeting_id: UUID,
        body: ShareSettingsIn,
    ) -> ShareLinkAnswer:
        """Turn the link on with these settings, or change them."""
        settings = ShareSettings(
            show_transcript=body.show_transcript, show_names=body.show_names,
            allow_comments=body.allow_comments, expiry=body.expiry,
        )  # fmt: skip
        return link_out(await links.put(principal, meeting_id, settings))

    @router.delete("", status_code=HTTPStatus.NO_CONTENT)
    async def delete_share_link(
        principal: Annotated[Principal, Depends(signed_in)], meeting_id: UUID
    ) -> Response:
        """Turn the link off; its comments go with it."""
        await links.remove(principal, meeting_id)
        return Response(status_code=HTTPStatus.NO_CONTENT)

    return router
