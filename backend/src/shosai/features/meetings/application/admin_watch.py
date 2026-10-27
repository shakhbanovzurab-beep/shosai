"""The admin's LiveKit screen: the server, its load and history, rooms and egress (MR-D10).

Everything comes from LiveKit's server API and from Prometheus; nothing from people's rows,
so the screen shows rooms by their LiveKit names and never a meeting's title. A server that
does not answer is `down` and the overview still answers, with no rooms; Prometheus that does
not answer leaves the load, the nodes and the history as "no data". A node Prometheus cannot
scrape makes the server `degraded`. LiveKit tells neither its version, nor a region, nor a
participant's connection quality to its API: those stay unknown.
"""

import asyncio
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Final

from shosai.features.meetings.application.admin_views import (
    DeviceView,
    EgressLine,
    LiveKitHealth,
    LoadView,
    NodeView,
    Overview,
    RoomDetail,
    RoomLine,
    ServerFacts,
    ServerView,
    SessionView,
)
from shosai.features.meetings.application.sfu_metrics import LoadNow, SfuMetrics
from shosai.features.meetings.application.video_server import (
    EgressReport,
    SfuParticipant,
    SfuRoom,
    SfuTrack,
    TrackKind,
    VideoServer,
    VideoUnavailableError,
)
from shosai.features.meetings.contracts import RoomNotFoundError
from shosai.features.meetings.domain import wire

# Сколько последних задач egress показывает экран.
EGRESS_SHOWN: Final = 50
PERCENT: Final = 100
MEBIBYTE: Final = 1024 * 1024
EGRESS_STATES: Final[Mapping[str, str]] = {
    "EGRESS_STARTING": "starting",
    "EGRESS_ACTIVE": "active",
    "EGRESS_ENDING": "ending",
    "EGRESS_COMPLETE": "complete",
    "EGRESS_LIMIT_REACHED": "complete",
    "EGRESS_FAILED": "failed",
    "EGRESS_ABORTED": "failed",
}
RUNNING: Final = frozenset({"starting", "active", "ending"})
CODEC_NAMES: Final[Mapping[str, str]] = {"opus": "Opus", "red": "RED"}


def egress_line(report: EgressReport) -> EgressLine:
    """An egress as the screen lists it; the file's size once it is written."""
    status = EGRESS_STATES.get(report.status, "failed")
    size = report.size_bytes if status == "complete" and report.size_bytes else None
    return EgressLine(
        report.egress_id, report.room_name, status, report.started_at, report.ended_at, size
    )


def codec_of(tracks: Sequence[SfuTrack], kinds: frozenset[TrackKind]) -> str | None:
    """The codec of the first track of these kinds that names one."""
    for track in tracks:
        if track.kind in kinds and track.mime_type:
            name = track.mime_type.partition("/")[2]
            return CODEC_NAMES.get(name.lower(), name.upper())
    return None


def device_of(attributes: Mapping[str, str]) -> DeviceView:
    """The device attributes the join set; an absent one is unknown."""
    return DeviceView(
        os=attributes.get(wire.DEVICE_OS),
        os_version=attributes.get(wire.DEVICE_OS_VERSION),
        client=attributes.get(wire.DEVICE_CLIENT),
        client_version=attributes.get(wire.DEVICE_CLIENT_VERSION),
        browser=attributes.get(wire.DEVICE_BROWSER),
    )


class LiveKitWatch:
    """Reads LiveKit's state for the admin's screen."""

    def __init__(
        self,
        server: VideoServer,
        metrics: SfuMetrics,
        facts: ServerFacts,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._server = server
        self._metrics = metrics
        self._facts = facts
        self._clock = clock

    async def overview(self) -> Overview:
        """The screen now; a server or a Prometheus that does not answer is shown as such."""
        now = self._clock()
        rooms, egress, load, history = await asyncio.gather(
            self._rooms(), self._egress(), self._metrics.now(), self._metrics.history(now)
        )
        held = rooms or []
        lines = sorted(
            (egress_line(report) for report in egress or []),
            key=lambda line: line.started_at or now,
            reverse=True,
        )
        return Overview(
            server=self._server_view(answering=rooms is not None, load=load),
            load=LoadView(
                active_rooms=len(held),
                participants=sum(room.participants for room in held),
                published_tracks=None if load is None else load.published_tracks,
                bandwidth_in_mbps=None if load is None else load.bandwidth_in_mbps,
                bandwidth_out_mbps=None if load is None else load.bandwidth_out_mbps,
                active_egress=sum(line.status in RUNNING for line in lines),
            ),
            history=history,
            nodes=() if load is None else self._nodes(load),
            rooms=[
                RoomLine(room.name, room.created_at, room.participants, room.recording)
                for room in sorted(held, key=lambda room: room.created_at, reverse=True)
            ],
            egress=lines[:EGRESS_SHOWN],
            updated_at=now,
        )

    async def room(self, name: str) -> RoomDetail:
        """A room the SFU holds, with its sessions; `room_not_found` when it holds none."""
        found = await self._server.rooms([name])
        if not found:
            raise RoomNotFoundError
        sessions = await self._server.participants(name)
        tracks = [track for session in sessions for track in session.tracks]
        room = found[0]
        line = RoomLine(
            room.name,
            room.created_at,
            room.participants,
            room.recording,
            video_codec=codec_of(tracks, frozenset({TrackKind.VIDEO, TrackKind.SCREEN})),
            audio_codec=codec_of(tracks, frozenset({TrackKind.AUDIO})),
        )
        return RoomDetail(line, [self._session(session) for session in sessions])

    async def _rooms(self) -> Sequence[SfuRoom] | None:
        try:
            return await self._server.rooms()
        except VideoUnavailableError:
            return None

    async def _egress(self) -> Sequence[EgressReport] | None:
        try:
            return await self._server.egresses(active=False)
        except VideoUnavailableError:
            return None

    def _server_view(self, *, answering: bool, load: LoadNow | None) -> ServerView:
        health = LiveKitHealth.DOWN
        if answering:
            all_up = load is None or all(node.up for node in load.nodes)
            health = LiveKitHealth.HEALTHY if all_up else LiveKitHealth.DEGRADED
        return ServerView(
            url=self._facts.url,
            started_at=None if load is None else load.started_at,
            health=health,
            api_key_configured=self._facts.configured,
        )

    def _nodes(self, load: LoadNow) -> list[NodeView]:
        limit = self._facts.memory_limit_mb
        return [
            NodeView(
                id=node.id,
                cpu_percent=node.cpu_percent,
                memory_percent=(
                    None
                    if node.memory_bytes is None or limit is None
                    else PERCENT * node.memory_bytes / (limit * MEBIBYTE)
                ),
                rooms=node.rooms,
                participants=node.participants,
                serving=node.up,
            )
            for node in load.nodes
        ]

    @staticmethod
    def _session(session: SfuParticipant) -> SessionView:
        return SessionView(
            identity=session.identity,
            name=session.name,
            joined_at=session.joined_at,
            device=device_of(session.attributes),
            tracks=session.tracks,
        )
