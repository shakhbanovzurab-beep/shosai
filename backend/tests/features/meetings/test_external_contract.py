"""The slice's external routes against the draft's contract (meetings A16, D1).

The draft's baseline names five external routes of the rooms slice (S06): four invitation
links already sent in mail and chats, and LiveKit's webhook. The webhook is served by the API
where the SFU posts it; the four links are answered by the edge, which sends each to the
room's or the broadcast's page in the cabinet. Meetings has no WebSocket of its own: the call
runs on LiveKit, so there are no frames to hold to the draft's catalogue.
"""

import re
from collections.abc import Sequence
from pathlib import Path
from typing import Final

from prometheus_client import CollectorRegistry
from shosai_contracts import (
    Candidate,
    CompatClass,
    Scope,
    check,
    load_baseline,
    parse_routes,
    render_text,
)
from shosai_contracts.inputs import BaselineOperation
from shosai_contracts.jsonvalue import Json

from shosai.core.ports.directory import PortDirectory
from shosai.features.meetings.application.recording import Recordings
from shosai.features.meetings.channels.http.webhook import build_webhook_router
from shosai.features.meetings.infrastructure.meetings_metrics import MeetingsMetrics
from tests.composition.public_routes import route_snapshot
from tests.core.web.probe_app import build_probe_app
from tests.features.meetings.room_bench import SfuDouble
from tests.features.meetings.test_calls_and_sweep import LIMITS, SentTasks, calls_of, outbox_of
from tests.harness.database_access import DatabaseAccess

ROOMS_SLICE: Final = "S06"
EXTERNAL: Final = Scope(slices=frozenset({ROOMS_SLICE}), classes=frozenset({CompatClass.EXTERNAL}))
EDGE: Final = (
    Path(__file__).parents[4] / "deploy/staging/nginx/templates/conf.d/shosai.conf.template"
)
REDIRECT: Final = re.compile(r'location ~ "([^"]+)" \{(?:[^{}]*?)return 302 (\S+);', re.DOTALL)
TOKEN: Final = "AbCdEf123456_-xy"
PAGES: Final = {
    "/meet/": "/app/meet/",
    "/j/": "/app/meet/",
    "/rooms/join/": "/app/meet/",
    "/live/": "/app/live/",
}


def external_routes() -> Sequence[BaselineOperation]:
    """The rooms slice's external routes in the draft's baseline."""
    return [
        operation
        for operation in load_baseline().operations
        if operation.slice_id == ROOMS_SLICE and operation.compat_class is CompatClass.EXTERNAL
    ]


def edge_answer(path: str) -> str | None:
    """Where the edge's redirects send a path; None when no redirect takes it."""
    for pattern, target in REDIRECT.findall(EDGE.read_text(encoding="utf-8")):
        found = re.fullmatch(pattern, path)
        if found:
            return str(target).replace("$1", found.group(1))
    return None


def test_the_draft_names_four_links_and_the_webhook() -> None:
    assert sorted((operation.method, operation.path) for operation in external_routes()) == [
        ("GET", "/j/{token}"), ("GET", "/live/{token}"), ("GET", "/meet/{token}"),
        ("GET", "/rooms/join/{token}"), ("POST", "/v1/livekit/webhook"),
    ]  # fmt: skip


def test_the_webhook_is_served_where_livekit_posts_it(homes: DatabaseAccess) -> None:
    server, metrics = SfuDouble(), MeetingsMetrics(CollectorRegistry())
    recordings = Recordings(
        homes.transactions, (server, PortDirectory(), outbox_of(), metrics), LIMITS
    )
    calls = calls_of(homes, SentTasks())
    router = build_webhook_router(server, (calls, recordings), metrics)
    app = build_probe_app(extra=(router,)).app
    routes: list[Json] = list(route_snapshot(app))
    candidate = Candidate(openapi=app.openapi(), routes=parse_routes(routes, "probe"))
    scope = Scope(EXTERNAL.slices, EXTERNAL.classes, path_prefixes=("/v1/",))

    report = check(load_baseline(), candidate, scope)

    assert report.is_compatible, render_text(report, scope)
    assert not report.unserved


def test_the_edge_sends_every_link_to_its_page_in_the_cabinet() -> None:
    links = [operation.path for operation in external_routes() if operation.method == "GET"]

    answers = {path: edge_answer(path.replace("{token}", TOKEN)) for path in links}

    assert answers == {path: f"{PAGES[path.removesuffix('{token}')]}{TOKEN}" for path in links}
    assert edge_answer("/meet/short") is None
    assert edge_answer(f"/meet/{TOKEN}/extra") is None
