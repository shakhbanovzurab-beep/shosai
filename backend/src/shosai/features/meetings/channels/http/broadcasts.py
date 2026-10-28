"""The host's broadcasts: `/v1/meetings/broadcasts` (MR-D7, meetings A12b).

A paid plan creates a broadcast once per `Idempotency-Key`; only its host starts and ends it.
Errors: `broadcast_not_in_plan` (403), `title_required` and `title_too_long` (422),
`broadcast_not_found` (404), `broadcast_ended` (409), `idempotency_key_reused` (422).
"""

from http import HTTPStatus
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from shosai.core.idempotency.http import IdempotencyKeyHeader
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import Principal, bearer_principal
from shosai.features.meetings.application.broadcasts import Broadcasts, BroadcastView
from shosai.features.meetings.channels.http.broadcast_models import BroadcastOut, NewBroadcast


def build_broadcasts_router(broadcasts: Broadcasts, ports: PortDirectory, origin: str) -> APIRouter:
    """The host's broadcasts."""
    router = APIRouter(prefix="/v1/meetings/broadcasts", tags=["meetings"])
    signed_in = Annotated[Principal, Depends(bearer_principal(ports))]

    def out(view: BroadcastView) -> BroadcastOut:
        return BroadcastOut(
            id=view.id, title=view.title, link=f"{origin.rstrip('/')}/live/{view.invite_token}",
            state=view.state, waiting_room=view.waiting_room,
        )  # fmt: skip

    @router.post("", status_code=HTTPStatus.CREATED)
    async def create_meeting_broadcast(
        principal: signed_in, body: NewBroadcast, key: IdempotencyKeyHeader
    ) -> BroadcastOut:
        """Create a broadcast with its own link; the stage gathers before it starts."""
        view = await broadcasts.create(principal, body.title, key, waiting_room=body.waiting_room)
        return out(view)

    @router.post("/{broadcast_id}/start")
    async def start_meeting_broadcast(principal: signed_in, broadcast_id: UUID) -> BroadcastOut:
        """Put your broadcast on air."""
        return out(await broadcasts.start(principal, broadcast_id))

    @router.post("/{broadcast_id}/end")
    async def end_meeting_broadcast(principal: signed_in, broadcast_id: UUID) -> BroadcastOut:
        """End your broadcast for everyone; its link stops working."""
        return out(await broadcasts.end(principal, broadcast_id))

    return router
