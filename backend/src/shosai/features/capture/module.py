"""The capture slice as composition sees it: Leo's voice mode (ADR 0070, LEO-voice step 5).

`WS /v1/ws/voice` on the WS gateway; the minutes of voice conversations for billing
(`MEETING_MINUTES`, beside notes' meetings) and their rows in the registry of a person's data.
Live capture of the desktop clients joins the slice with its own package.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from shosai.core.account_data.handlers import ACCOUNT_DATA_HANDLERS
from shosai.core.features import CoreServices, FeatureModule, FeatureParts
from shosai.features.agent.contracts.voice import VOICE_TURNS
from shosai.features.billing.contracts import MEETING_MINUTES, MINUTES_ALLOWANCE
from shosai.features.capture.application.account_data import ACCOUNT_DATA, CaptureAccountData
from shosai.features.capture.application.voice_minutes import VoiceMinutesCount
from shosai.features.capture.channels.voice_session import VoiceParts, VoiceSessions
from shosai.features.capture.channels.ws import build_voice_router
from shosai.features.capture.infrastructure.voice_metrics import VoiceMetrics
from shosai.features.capture.infrastructure.voice_records import VOICE_MODELS
from shosai.features.capture.settings import CaptureSettings


@asynccontextmanager
async def build(services: CoreServices) -> AsyncIterator[FeatureParts]:
    """The voice route, the minutes' binding and the handler of a person's data."""
    settings = services.settings.features.get(CaptureSettings)
    parts = VoiceParts(
        services.transactions, services.ports, services.locks, services.ai,
        settings.voice_model(), VoiceMetrics(services.registry),
    )  # fmt: skip
    yield FeatureParts(
        ws_routers=(build_voice_router(services.sockets, VoiceSessions(parts)),),
        provides=(
            MEETING_MINUTES.bind(VoiceMinutesCount()),
            ACCOUNT_DATA_HANDLERS.bind(CaptureAccountData(services.transactions)),
        ),
    )


CAPTURE = FeatureModule(
    name="capture",
    build=build,
    models=VOICE_MODELS,
    settings=(CaptureSettings,),
    requires=(VOICE_TURNS, MINUTES_ALLOWANCE),
    account_data=(ACCOUNT_DATA,),
)
