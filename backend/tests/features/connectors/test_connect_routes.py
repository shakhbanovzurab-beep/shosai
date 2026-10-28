"""The connect flow over HTTP: the binder cookie, the relative redirect, the draft's paths."""

import uuid
from collections.abc import AsyncIterator
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest_asyncio

from shosai.core.kernel.homes import Home
from shosai.features.connectors.channels.http.connect_routes import build_connect_router
from tests.core.web.probe_app import build_probe_app, client_of
from tests.features.billing.people_bench import bearer
from tests.features.connectors.connect_bench import ConnectBench, connect_bench

__all__ = ["connect_bench"]


@pytest_asyncio.fixture
async def http(connect_bench: ConnectBench) -> AsyncIterator[httpx.AsyncClient]:
    """The connect routes in the real shell, at Shosai's public address."""
    router = build_connect_router(
        (connect_bench.authorizer, connect_bench.completer), connect_bench.ports
    )
    app = build_probe_app(extra=(router,)).app
    async with client_of(app, base_url="https://shosai.test") as client:
        yield client


async def test_the_popup_flow_sets_the_binder_and_comes_back_relative(
    http: httpx.AsyncClient,
) -> None:
    person = (Home.RU, uuid.uuid4())

    started = await http.post(
        "/v1/connectors/google_calendar/authorize", json={"return": "popup"}, headers=bearer(person)
    )

    assert started.status_code == 200
    cookie = started.headers["set-cookie"]
    assert "HttpOnly" in cookie
    assert "Path=/v1/connectors/oauth" in cookie
    state = parse_qs(urlsplit(started.json()["authorize_url"]).query)["state"][0]
    done = await http.get(
        "/v1/connectors/oauth/google/callback", params={"state": state, "code": "ok:anna"}
    )
    assert done.status_code == 303
    assert done.headers["location"] == "/oauth/callback?connector=google_calendar&status=connected"
    assert "shosai_connect=" in done.headers["set-cookie"]


async def test_a_callback_without_the_binder_is_expired(http: httpx.AsyncClient) -> None:
    person = (Home.RU, uuid.uuid4())
    started = await http.post(
        "/v1/connectors/google_drive/authorize", json={}, headers=bearer(person)
    )
    state = parse_qs(urlsplit(started.json()["authorize_url"]).query)["state"][0]
    http.cookies.clear()

    done = await http.get(
        "/v1/connectors/oauth/google/callback", params={"state": state, "code": "ok:anna"}
    )

    assert done.headers["location"] == "/oauth/callback?status=error&error=authorization_expired"


async def test_a_page_return_stays_in_the_cabinet_and_refuses_another_host(
    http: httpx.AsyncClient,
) -> None:
    person = (Home.RU, uuid.uuid4())
    body = {"return": "page", "return_path": "/app/knowledge-base?tab=sources"}

    started = await http.post(
        "/v1/connectors/google_drive/authorize", json=body, headers=bearer(person)
    )
    refused = await http.post(
        "/v1/connectors/google_drive/authorize",
        json={"return": "page", "return_path": "https://evil.example.com/app"},
        headers=bearer(person),
    )

    state = parse_qs(urlsplit(started.json()["authorize_url"]).query)["state"][0]
    done = await http.get(
        "/v1/connectors/oauth/google/callback", params={"state": state, "code": "ok:anna"}
    )
    assert done.headers["location"].startswith("/app/knowledge-base?tab=sources&connector=")
    assert refused.status_code == 422
    assert refused.json()["error"]["code"] == "return_path_invalid"


async def test_an_unknown_app_a_stranger_and_an_unoffered_app_are_refused(
    http: httpx.AsyncClient,
) -> None:
    person = (Home.RU, uuid.uuid4())

    unknown = await http.post("/v1/connectors/nango/authorize", json={}, headers=bearer(person))
    stranger = await http.post("/v1/connectors/gmail/authorize", json={})
    unoffered = await http.post("/v1/connectors/gmail/authorize", json={}, headers=bearer(person))

    assert (unknown.status_code, unknown.json()["error"]["code"]) == (404, "unknown_app")
    assert stranger.status_code == 401
    assert (unoffered.status_code, unoffered.json()["error"]["code"]) == (409, "not_offered")


async def test_the_draft_s_callback_paths_answer_an_expired_authorization(
    http: httpx.AsyncClient,
) -> None:
    for path in ("/v1/integrations/oauth/slack/callback", "/v1/jira/oauth/callback"):
        done = await http.get(path, params={"state": "draft-state", "code": "draft-code"})

        assert done.status_code == 303
        assert done.headers["location"] == (
            "/oauth/callback?status=error&error=authorization_expired"
        )
