"""LiveKit's webhook: `POST /v1/livekit/webhook` (meetings plan §3.3, an external route).

LiveKit posts every room, participant, track and egress event here from the plane's network.
A webhook is accepted only when its JWT is signed with the API's secret over the body's
SHA-256 (401 `webhook_rejected` otherwise). A room's events fold into its call at once, and the
call's handover runs as a task; an egress's report moves its recording. A webhook of another
kind, or of a room Shosai does not know, is accepted and ignored. A repeat changes nothing.
The answer is the draft's: 200 with `{"ok": true}` (the external contract, A16).
"""

from typing import Annotated

from fastapi import APIRouter, Header, Request
from pydantic import BaseModel

from shosai.features.meetings.application.calls import Calls
from shosai.features.meetings.application.recording import Recordings
from shosai.features.meetings.application.video_server import VideoServer
from shosai.features.meetings.infrastructure.meetings_metrics import MeetingsMetrics


class LiveKitWebhookOut(BaseModel):
    """The event is taken; the call server does not send it again."""

    ok: bool = True


def build_webhook_router(
    server: VideoServer, handlers: tuple[Calls, Recordings], metrics: MeetingsMetrics
) -> APIRouter:
    """The SFU's webhook."""
    calls, recordings = handlers
    router = APIRouter(prefix="/v1/livekit", tags=["meetings"])

    # 200 с {"ok": true}, как отвечал черновик: внешний контракт держится буквально (A16, D1).
    @router.post("/webhook")
    async def receive_livekit_webhook(
        request: Request, authorization: Annotated[str | None, Header()] = None
    ) -> LiveKitWebhookOut:
        """Accept a signed event of the call server."""
        webhook = server.verify_webhook(await request.body(), authorization)
        metrics.received(webhook.kind)
        await calls.on_webhook(webhook)
        if webhook.egress is not None:
            found = await calls.find(webhook.egress.room_name or webhook.room_name)
            if found is not None:
                await recordings.on_report(found, webhook.egress)
        return LiveKitWebhookOut()

    return router
