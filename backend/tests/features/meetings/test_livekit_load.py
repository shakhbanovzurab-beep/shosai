"""LiveKit's load read from Prometheus's API, and "no data" when it does not answer (A8)."""

import json
from datetime import UTC, datetime

import httpx

from shosai.features.meetings.infrastructure.livekit_load import (
    ALL_PARTICIPANTS,
    CPU,
    MEMORY,
    PARTICIPANTS,
    ROOMS,
    STARTED,
    TRACKS,
    UP,
    PrometheusLoad,
    bandwidth,
)

NOW = datetime(2026, 10, 27, 12, tzinfo=UTC)
AT = NOW.timestamp()
NODE = {"instance": "livekit:6789", "node_id": "ND_a"}
DOWN = {"instance": "livekit-2:6789"}


def vector(*series: tuple[dict[str, str], str]) -> list[dict[str, object]]:
    """An instant answer's series."""
    return [{"metric": labels, "value": [AT, value]} for labels, value in series]


INSTANT = {
    UP: vector((NODE, "1"), (DOWN, "0")),
    ROOMS: vector((NODE, "3")),
    PARTICIPANTS: vector((NODE, "7")),
    CPU: vector((NODE, "41.5")),
    MEMORY: vector((NODE, "201326592")),
    STARTED: vector(({}, f"{AT - 3600}")),
    TRACKS: vector(({}, "9")),
    bandwidth("incoming", "1m"): vector(({}, "2.5")),
    bandwidth("outgoing", "1m"): vector(({}, "NaN")),
}
RANGE = {
    ALL_PARTICIPANTS: [{"metric": {}, "values": [[AT - 900, "4"], [AT, "7"]]}],
    bandwidth("incoming", "900s"): [{"metric": {}, "values": [[AT, "1.25"]]}],
    bandwidth("outgoing", "900s"): [],
}


def answering(request: httpx.Request) -> httpx.Response:
    """Prometheus with the test's series."""
    query = request.url.params["query"]
    table = INSTANT if request.url.path.endswith("/query") else RANGE
    body = {"status": "success", "data": {"resultType": "vector", "result": table[query]}}
    return httpx.Response(200, content=json.dumps(body))


def load_over(handler: httpx.MockTransport) -> PrometheusLoad:
    """The reader over a transport."""
    return PrometheusLoad(httpx.AsyncClient(transport=handler, base_url="http://prometheus:9090"))


async def test_the_load_joins_nodes_by_instance_and_reads_traffic() -> None:
    load = await load_over(httpx.MockTransport(answering)).now()

    assert load is not None
    assert (load.published_tracks, load.bandwidth_in_mbps, load.bandwidth_out_mbps) == (9, 2.5, 0)
    assert load.started_at == datetime.fromtimestamp(AT - 3600, UTC)
    down, up = load.nodes  # по адресу экземпляра
    assert (up.id, up.rooms, up.participants, up.cpu_percent, up.memory_bytes) == (
        "ND_a", 3, 7, 41.5, 201326592,
    )  # fmt: skip
    assert (down.id, down.up, down.cpu_percent) == ("livekit-2:6789", False, None)


async def test_the_history_takes_the_participants_times() -> None:
    samples = await load_over(httpx.MockTransport(answering)).history(NOW)

    assert [(s.participants, s.bandwidth_in_mbps, s.bandwidth_out_mbps) for s in samples] == [
        (4, 0.0, 0.0), (7, 1.25, 0.0),
    ]  # fmt: skip


async def test_prometheus_down_or_failing_is_no_data() -> None:
    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    def failing(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(503, content=b"unavailable")

    def without_livekit(request: httpx.Request) -> httpx.Response:
        del request
        body = {"status": "success", "data": {"resultType": "vector", "result": []}}
        return httpx.Response(200, content=json.dumps(body))

    for handler in (down, failing):
        reader = load_over(httpx.MockTransport(handler))
        assert await reader.now() is None
        assert await reader.history(NOW) == []
    assert await load_over(httpx.MockTransport(without_livekit)).now() is None
