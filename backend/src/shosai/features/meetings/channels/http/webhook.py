"""LiveKit's webhook: `POST /v1/livekit/webhook` (meetings plan §3.3, an external route).

LiveKit posts every room, participant, track and egress event here from the plane's network.
A webhook is accepted only when its JWT is signed with the API's secret over the body's
SHA-256 (401 `webhook_rejected` otherwise); a room's events fold into its call at once, and
the call's handover runs as a task. A webhook of another kind, or of a room Shosai does not
know, is accepted and ignored. A repeat changes nothing.
"""

from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Header, Request, Response

from shosai.features.meetings.application.calls import Calls
from shosai.features.meetings.application.video_server import VideoServer
from shosai.features.meetings.infrastructure.meetings_metrics import MeetingsMetrics


def build_webhook_router(server: VideoServer, calls: Calls, metrics: MeetingsMetrics) -> APIRouter:
    """The SFU's webhook."""
    router = APIRouter(prefix="/v1/livekit", tags=["meetings"])

    @router.post("/webhook", status_code=HTTPStatus.NO_CONTENT, response_class=Response)
    async def receive_livekit_webhook(
        request: Request, authorization: Annotated[str | None, Header()] = None
    ) -> None:
        """Accept a signed event of the call server."""
        webhook = server.verify_webhook(await request.body(), authorization)
        metrics.received(webhook.kind)
        await calls.on_webhook(webhook)

    return router
