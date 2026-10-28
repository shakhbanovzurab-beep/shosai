"""The meetings slice as composition sees it (meetings plan §3.1).

Step A1 published the contract — the ports calendar binds and uses, and the slice's events —
and the domain. Step A2 added LiveKit: the `LIVEKIT_*` settings with their production check,
the SFU behind the `VideoServer` port, opened with the process and closed with it, and its
readiness probe when it is configured. Step A3 added the tables of each home and their
account data handler. Step A4 added the owner's rooms on `/v1/meetings/rooms`, the public
join with its room passes in Valkey and their renewal, removal with bans, hands and the
account's rooms. Step A5 added LiveKit's webhook, calls and the sweep of each home; A6 the
call's chat; A7 its video recording. Step A8 added the admin's LiveKit screen over LiveKit's
API and Prometheus, A13 Leo's `meetings` toolset, A11b the room's board and A12b broadcasts.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta

from shosai.core.account_data.handlers import ACCOUNT_DATA_HANDLERS
from shosai.core.features import CoreServices, FeatureModule, FeatureParts
from shosai.core.health.probes import DependencyProbe
from shosai.core.idempotency.action_items import ActionItems
from shosai.core.kernel.homes import Home
from shosai.features.meetings.application.account_data import (
    ACCOUNT_DATA,
    MODELS,
    MeetingsAccountData,
)
from shosai.features.meetings.application.account_rooms import AccountRooms
from shosai.features.meetings.application.admin_actions import AdminRoomActions
from shosai.features.meetings.application.admin_views import ServerFacts
from shosai.features.meetings.application.admin_watch import LiveKitWatch
from shosai.features.meetings.application.board import Boards
from shosai.features.meetings.application.broadcast_chat import BroadcastChat
from shosai.features.meetings.application.broadcast_entry import BroadcastDoor
from shosai.features.meetings.application.broadcast_stage import BroadcastStage
from shosai.features.meetings.application.broadcasts import Broadcasts
from shosai.features.meetings.application.calls import Calls
from shosai.features.meetings.application.chat import Chat
from shosai.features.meetings.application.joining import JoinDesk
from shosai.features.meetings.application.passes import PassCheck
from shosai.features.meetings.application.recording import RecordingLimits, Recordings
from shosai.features.meetings.application.removals import Removals
from shosai.features.meetings.application.rooms import RoomBook
from shosai.features.meetings.application.sweep import Sweep
from shosai.features.meetings.application.video_server import VideoUnavailableError
from shosai.features.meetings.channels.agent_specs import SPECS
from shosai.features.meetings.channels.agent_tools import MeetingTools
from shosai.features.meetings.channels.http.admin_livekit import build_admin_livekit_router
from shosai.features.meetings.channels.http.board import build_board_router
from shosai.features.meetings.channels.http.broadcasts import build_broadcasts_router
from shosai.features.meetings.channels.http.chat import build_chat_router
from shosai.features.meetings.channels.http.joining import build_joining_router
from shosai.features.meetings.channels.http.live import build_live_router, build_live_stage_router
from shosai.features.meetings.channels.http.recording import build_recording_router
from shosai.features.meetings.channels.http.rooms import build_rooms_router
from shosai.features.meetings.channels.http.webhook import build_webhook_router
from shosai.features.meetings.channels.subscriptions import subscriptions
from shosai.features.meetings.channels.tasks import PERIODIC_JOBS, task_handlers
from shosai.features.meetings.contracts.events import CallEnded, CallStarted, RecordingReady
from shosai.features.meetings.infrastructure.broadcast_queues import BroadcastQueues
from shosai.features.meetings.infrastructure.livekit_load import open_sfu_metrics
from shosai.features.meetings.infrastructure.livekit_metrics import LiveKitMetrics
from shosai.features.meetings.infrastructure.livekit_server import open_video_server
from shosai.features.meetings.infrastructure.meetings_metrics import MeetingsMetrics
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
    meetings = services.settings.features.get(MeetingsSettings)
    async with (
        open_video_server(settings, LiveKitMetrics(services.registry)) as server,
        open_sfu_metrics(meetings.meetings_prometheus_url) as load,
    ):
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
        metrics = MeetingsMetrics(services.registry)
        calls = Calls(transactions, (services.outbox, services.tasks))
        recordings = Recordings(
            transactions, (server, ports, services.outbox), recording_limits(services)
        )
        sweep = Sweep(transactions, (server, calls, ports, metrics, recordings))
        boards = Boards(transactions, (ports, services.rate_limiter, services.objects))
        desk = JoinDesk(
            transactions, (server, passes, ports), meetings.meetings_room_participants_ceiling
        )
        facts = ServerFacts(
            url=None if settings.livekit_url is None else str(settings.livekit_url),
            configured=settings.configured,
            memory_limit_mb=meetings.meetings_livekit_memory_limit_mb,
        )
        origin = str(services.settings.email.public_base_url)
        queues = BroadcastQueues(services.valkey)
        door = BroadcastDoor(transactions, (desk, server, passes, queues))
        stage = BroadcastStage(transactions, (server, queues))
        broadcast_chat = BroadcastChat(
            transactions, (services.effects, services.rate_limiter, server)
        )
        check = PassCheck(transactions, passes)
        yield FeatureParts(
            http_routers=(
                build_rooms_router((book, removals), ports, origin),
                build_webhook_router(server, (calls, recordings), metrics),
                build_recording_router(recordings, ports),
                build_chat_router(
                    Chat(transactions, (services.effects, services.rate_limiter, server)),
                    PassCheck(transactions, passes),
                ),
                build_joining_router(
                    desk, PassCheck(transactions, passes), ports, services.rate_limiter
                ),
                build_board_router(boards, PassCheck(transactions, passes)),
                build_broadcasts_router(
                    Broadcasts(transactions, (services.effects, ports, server, desk)), ports, origin
                ),
                build_live_router(
                    (door, stage, broadcast_chat), desk, check, (ports, services.rate_limiter)
                ),
                build_live_stage_router((door, stage), desk, check),
                build_admin_livekit_router(
                    LiveKitWatch(server, load, facts),
                    AdminRoomActions(transactions, (server, passes, ports), calls.find),
                    ports,
                ),
            ),
            task_handlers=task_handlers(AccountRooms(transactions, server), calls, sweep, boards),
            agent_tools=MeetingTools(
                transactions, (book, ActionItems(services.effects, services.outbox), server), origin
            ).bound(),
            periodic_jobs=PERIODIC_JOBS,
            subscriptions=subscriptions(services.tasks),
            probes=probes,
            provides=(ACCOUNT_DATA_HANDLERS.bind(MeetingsAccountData(services.transactions)),),
        )


def recording_limits(services: CoreServices) -> RecordingLimits:
    """The platform's recording bounds and the buckets as egress reaches them."""
    meetings = services.settings.features.get(MeetingsSettings)
    endpoints = {
        Home.RU: meetings.meetings_egress_s3_endpoint_ru,
        Home.EU: meetings.meetings_egress_s3_endpoint_eu,
    }
    return RecordingLimits(
        concurrent=meetings.meetings_recordings_concurrent,
        length=timedelta(minutes=meetings.meetings_recording_max_minutes),
        buckets=services.settings.storage,
        endpoints=endpoints,
    )


MEETINGS = FeatureModule(
    name="meetings",
    build=build_meetings,
    models=MODELS,
    events=(CallStarted, CallEnded, RecordingReady),
    production_checks=(livekit_settings_safe,),
    settings=(LiveKitSettings, MeetingsSettings),
    account_data=(ACCOUNT_DATA,),
    agent_tools=SPECS,
)
