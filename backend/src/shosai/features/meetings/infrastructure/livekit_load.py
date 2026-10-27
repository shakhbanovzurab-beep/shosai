"""LiveKit's load from Prometheus's HTTP API, for the admin's screen (meetings A8, MR-D10).

Prometheus scrapes LiveKit as the `livekit` job. The names are those of the pinned LiveKit
v1.13: `livekit_room_total` and `livekit_participant_total` per node, `livekit_packet_bytes`
by direction, `livekit_track_published_total` by kind, and the process's own CPU, memory and
start time. A node's CPU is counted against the CPUs its Go runtime may use, which follows the
container's limit. A failed request, a timeout or an answer that is not Prometheus's is "no
data" for the whole screen, logged once per request.
"""

import asyncio
import math
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Final

import httpx
import structlog
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, ValidationError

from shosai.features.meetings.application.sfu_metrics import (
    HISTORY_SPAN,
    HISTORY_STEP,
    LoadNow,
    LoadSample,
    NodeLoad,
)

TIMEOUT: Final = httpx.Timeout(3.0, connect=1.0)
JOB: Final = 'job="livekit"'
UP: Final = f"up{{{JOB}}}"
ROOMS: Final = f"sum by (instance, node_id) (livekit_room_total{{{JOB}}})"
PARTICIPANTS: Final = f"sum by (instance, node_id) (livekit_participant_total{{{JOB}}})"
CPU: Final = (
    f"100 * rate(process_cpu_seconds_total{{{JOB}}}[1m]) / go_sched_gomaxprocs_threads{{{JOB}}}"
)
MEMORY: Final = f"process_resident_memory_bytes{{{JOB}}}"
STARTED: Final = f"min(process_start_time_seconds{{{JOB}}})"
TRACKS: Final = f"sum(livekit_track_published_total{{{JOB}}})"
ALL_PARTICIPANTS: Final = f"sum(livekit_participant_total{{{JOB}}})"
BITS_PER_BYTE: Final = 8
MEGABIT: Final = 1_000_000
log = structlog.stdlib.get_logger(__name__)


def bandwidth(direction: str, window: str) -> str:
    """Megabits a second of LiveKit's traffic in one direction over the window."""
    rate = f'sum(rate(livekit_packet_bytes{{{JOB},direction="{direction}"}}[{window}]))'
    return f"{rate} * {BITS_PER_BYTE} / {MEGABIT}"


class Series(BaseModel):
    """One series of an answer: its labels and its value, or its values over a range."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    metric: dict[str, str] = Field(default_factory=dict)
    value: tuple[float, str] | None = None
    values: list[tuple[float, str]] = Field(default_factory=list)


class Result(BaseModel):
    """The data of a successful answer."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    result: list[Series]


class Answer(BaseModel):
    """Prometheus's answer to a query."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    status: str
    data: Result | None = None


class MetricsUnavailableError(Exception):
    """Prometheus did not answer a query."""


def number(text: str) -> float:
    """A sample's value; NaN and the infinities read as zero."""
    value = float(text)
    return value if math.isfinite(value) else 0.0


def by_instance(series: Sequence[Series]) -> dict[str, Series]:
    """The series keyed by the scraped instance."""
    return {item.metric.get("instance", ""): item for item in series}


def scalar(series: Sequence[Series]) -> float:
    """The value of an aggregate; zero when nothing was scraped yet."""
    first = next((item.value for item in series if item.value is not None), None)
    return 0.0 if first is None else number(first[1])


def instant(item: Series | None) -> float | None:
    """A series' value, None when it is absent."""
    return None if item is None or item.value is None else number(item.value[1])


def nodes_of(answers: Sequence[Sequence[Series]]) -> tuple[NodeLoad, ...]:
    """The nodes Prometheus scrapes, joined by instance; a node down has no load."""
    up, rooms, participants, cpu, memory = (by_instance(answer) for answer in answers)
    nodes = []
    for instance, target in sorted(up.items()):
        if instant(target) != 1:
            nodes.append(NodeLoad(id=instance, up=False))
            continue
        node_id = (rooms.get(instance) or participants.get(instance) or target).metric.get(
            "node_id", instance
        )
        used = instant(memory.get(instance))
        nodes.append(
            NodeLoad(
                id=node_id,
                up=True,
                rooms=int(instant(rooms.get(instance)) or 0),
                participants=int(instant(participants.get(instance)) or 0),
                cpu_percent=instant(cpu.get(instance)),
                memory_bytes=None if used is None else int(used),
            )
        )
    return tuple(nodes)


def samples_of(answers: Sequence[Sequence[Series]]) -> list[LoadSample]:
    """The history's samples at the times participants were counted, oldest first."""
    participants, incoming, outgoing = (
        {at: number(value) for item in answer for at, value in item.values} for answer in answers
    )
    return [
        LoadSample(
            at=datetime.fromtimestamp(at, UTC),
            participants=int(count),
            bandwidth_in_mbps=incoming.get(at, 0.0),
            bandwidth_out_mbps=outgoing.get(at, 0.0),
        )
        for at, count in sorted(participants.items())
    ]


class PrometheusLoad:
    """LiveKit's load through one HTTP client of the process."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def now(self) -> LoadNow | None:
        """The load at this moment; None when Prometheus does not answer or knows no node."""
        queries = (UP, ROOMS, PARTICIPANTS, CPU, MEMORY, STARTED, TRACKS)
        traffic = (bandwidth("incoming", "1m"), bandwidth("outgoing", "1m"))
        try:
            answers = await asyncio.gather(
                *(self._get("query", {"query": query}) for query in (*queries, *traffic))
            )
        except MetricsUnavailableError:
            return None
        if not answers[0]:
            return None
        started = answers[5][0].value if answers[5] else None
        return LoadNow(
            started_at=None if started is None else datetime.fromtimestamp(number(started[1]), UTC),
            published_tracks=int(scalar(answers[6])),
            bandwidth_in_mbps=scalar(answers[7]),
            bandwidth_out_mbps=scalar(answers[8]),
            nodes=nodes_of(answers[:5]),
        )

    async def history(self, until: datetime) -> Sequence[LoadSample]:
        """A sample every 15 minutes over the last 24 hours; empty when Prometheus is down."""
        window = f"{int(HISTORY_STEP.total_seconds())}s"
        span = {
            "start": f"{(until - HISTORY_SPAN).timestamp():.3f}",
            "end": f"{until.timestamp():.3f}",
            "step": window,
        }
        queries = (ALL_PARTICIPANTS, bandwidth("incoming", window), bandwidth("outgoing", window))
        try:
            answers = await asyncio.gather(
                *(self._get("query_range", {"query": query, **span}) for query in queries)
            )
        except MetricsUnavailableError:
            return []
        return samples_of(answers)

    async def _get(self, endpoint: str, params: dict[str, str]) -> list[Series]:
        try:
            response = await self._client.get(f"/api/v1/{endpoint}", params=params)
            response.raise_for_status()
            answer = Answer.model_validate_json(response.content)
        except (httpx.HTTPError, ValidationError) as error:
            log.warning("Prometheus не ответил на запрос нагрузки LiveKit",
                        endpoint=endpoint, error=type(error).__name__)  # fmt: skip
            raise MetricsUnavailableError from None
        if answer.status != "success" or answer.data is None:
            log.warning("Prometheus отказал в запросе нагрузки LiveKit", endpoint=endpoint)
            raise MetricsUnavailableError
        return answer.data.result


@asynccontextmanager
async def open_sfu_metrics(url: HttpUrl) -> AsyncIterator[PrometheusLoad]:
    """LiveKit's load from Prometheus for the life of the process."""
    async with httpx.AsyncClient(base_url=str(url), timeout=TIMEOUT) as client:
        yield PrometheusLoad(client)
