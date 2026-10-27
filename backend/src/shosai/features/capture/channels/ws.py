"""Capture's WebSocket routes on the WS gateway (ADR 0070): Leo's voice mode."""

from fastapi import APIRouter, WebSocket

from shosai.core.web.sockets import SocketGateway
from shosai.features.capture.channels.voice_session import ROUTE, VoiceSessions


def build_voice_router(gateway: SocketGateway, sessions: VoiceSessions) -> APIRouter:
    """`WS /v1/ws/voice`, served by the gateway: origin, capacity, the end's code and the drain."""
    router = APIRouter()

    @router.websocket(ROUTE)
    async def voice(websocket: WebSocket) -> None:
        await gateway.serve(websocket, ROUTE, sessions.serve)

    return router
