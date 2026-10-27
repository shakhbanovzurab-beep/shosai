"""The meetings slice as composition sees it (meetings plan §3.1).

Step A1 published the contract — the ports calendar binds and uses, and the slice's events —
and the domain. Step A2 added LiveKit: the `LIVEKIT_*` settings with their production check,
the SFU behind the `VideoServer` port, opened with the process and closed with it, and its
readiness probe when it is configured. Step A3 added the tables of each home and their
account data handler. Step A4 added the owner's rooms on `/v1/meetings/rooms`.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from shosai.core.account_data.handlers import ACCOUNT_DATA_HANDLERS
from shosai.core.features import CoreServices, FeatureModule, FeatureParts
from shosai.core.health.probes import DependencyProbe
from shosai.features.meetings.application.account_data import (
    ACCOUNT_DATA,
    MODELS,
    MeetingsAccountData,
)
from shosai.features.meetings.application.rooms import RoomBook
from shosai.features.meetings.application.video_server import VideoUnavailableError
from shosai.features.meetings.channels.http.rooms import build_rooms_router
from shosai.features.meetings.contracts.events import CallEnded, CallStarted, RecordingReady
from shosai.features.meetings.infrastructure.livekit_metrics import LiveKitMetrics
from shosai.features.meetings.infrastructure.livekit_server import open_video_server
from shosai.features.meetings.settings import (
    LiveKitSettings,
    MeetingsSettings,
    livekit_settings_safe,
)


@asynccontextmanager
async def build_meetings(services: CoreServices) -> AsyncIterator[FeatureParts]:
    """The slice's parts for this process; the SFU's client lives as long as the process."""
    settings = services.settings.features.get(LiveKitSettings)
    async with open_video_server(settings, LiveKitMetrics(services.registry)) as server:
        # Без LiveKit проба не нужна: 503 звонков — настройка, а не авария.
        probes = (
            (DependencyProbe("livekit", server.ping, (VideoUnavailableError,)),)
            if settings.configured
            else ()
        )
        book = RoomBook(services.transactions, (services.effects, services.ports), server)
        origin = str(services.settings.email.public_base_url)
        yield FeatureParts(
            http_routers=(build_rooms_router(book, services.ports, origin),),
            probes=probes,
            provides=(ACCOUNT_DATA_HANDLERS.bind(MeetingsAccountData(services.transactions)),),
        )


MEETINGS = FeatureModule(
    name="meetings",
    build=build_meetings,
    models=MODELS,
    events=(CallStarted, CallEnded, RecordingReady),
    production_checks=(livekit_settings_safe,),
    settings=(LiveKitSettings, MeetingsSettings),
    account_data=(ACCOUNT_DATA,),
)
