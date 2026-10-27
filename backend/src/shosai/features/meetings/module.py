"""The meetings slice as composition sees it (meetings plan §3.1).

Step A1 published the contract — the ports calendar binds and uses, and the slice's events —
and the domain. Step A2 added LiveKit: the `LIVEKIT_*` settings with their production check,
the SFU behind the `VideoServer` port, opened with the process and closed with it, and its
readiness probe when it is configured. Step A3 added the tables of each home and their
account data handler. Step A4 added the owner's rooms on `/v1/meetings/rooms`, the public
join with its room passes in Valkey and their renewal.
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
from shosai.features.meetings.application.account_rooms import AccountRooms
from shosai.features.meetings.application.joining import JoinDesk
from shosai.features.meetings.application.passes import PassCheck
from shosai.features.meetings.application.removals import Removals
from shosai.features.meetings.application.rooms import RoomBook
from shosai.features.meetings.application.video_server import VideoUnavailableError
from shosai.features.meetings.channels.http.joining import build_joining_router
from shosai.features.meetings.channels.http.rooms import build_rooms_router
from shosai.features.meetings.channels.subscriptions import subscriptions
from shosai.features.meetings.channels.tasks import task_handlers
from shosai.features.meetings.contracts.events import CallEnded, CallStarted, RecordingReady
from shosai.features.meetings.infrastructure.livekit_metrics import LiveKitMetrics
from shosai.features.meetings.infrastructure.livekit_server import open_video_server
from shosai.features.meetings.infrastructure.room_passes import RoomPasses
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
        transactions, ports = services.transactions, services.ports
        book = RoomBook(transactions, (services.effects, ports), server)
        passes = RoomPasses(services.valkey)
        removals = Removals(transactions, server, passes)
        ceiling = services.settings.features.get(
            MeetingsSettings
        ).meetings_room_participants_ceiling
        desk = JoinDesk(transactions, (server, passes, ports), ceiling)
        origin = str(services.settings.email.public_base_url)
        yield FeatureParts(
            http_routers=(
                build_rooms_router((book, removals), ports, origin),
                build_joining_router(
                    desk, PassCheck(transactions, passes), ports, services.rate_limiter
                ),
            ),
            task_handlers=task_handlers(AccountRooms(transactions, server)),
            subscriptions=subscriptions(services.tasks),
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
