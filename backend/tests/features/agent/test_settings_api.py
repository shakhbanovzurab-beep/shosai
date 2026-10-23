"""Settings > Leo on `/v1/agent/settings` and its switches of the native `/v1/auth/me` (step 3)."""

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx
import pytest_asyncio

from shosai.core.kernel.homes import Home
from shosai.core.ports.directory import PortDirectory
from shosai.features.agent.application.preferences import AgentPreferences
from shosai.features.agent.channels.http.settings import build_settings_router
from shosai.features.identity.contracts import AUTHENTICATOR, Principal
from tests.core.web.probe_app import build_probe_app, client_of
from tests.features.billing.people_bench import BearerOfTheTest, bearer
from tests.harness.database_access import DatabaseAccess

DEFAULTS = {
    "leo_model": "auto",
    "response_language": "auto",
    "response_length": "balanced",
    "web_search": True,
    "voice_mode": True,
    "knowledge_base_search": True,
    "connected_services_search": True,
}


@dataclass(frozen=True, slots=True)
class SettingsBench:
    """The route over the slot's homes and the service behind it."""

    http: httpx.AsyncClient
    preferences: AgentPreferences


@pytest_asyncio.fixture
async def bench(homes: DatabaseAccess) -> AsyncIterator[SettingsBench]:
    ports = PortDirectory()
    ports.install([AUTHENTICATOR.bind(BearerOfTheTest())])
    preferences = AgentPreferences(homes.transactions)
    app = build_probe_app(extra=(build_settings_router(preferences, ports),)).app
    async with client_of(app) as http:
        yield SettingsBench(http, preferences)


async def test_a_person_starts_with_everything_on_and_a_change_answers_the_whole(
    bench: SettingsBench,
) -> None:
    person = (Home.RU, uuid.uuid4())

    before = await bench.http.get("/v1/agent/settings", headers=bearer(person))
    changed = await bench.http.patch(
        "/v1/agent/settings", json={"web_search": False}, headers=bearer(person)
    )
    again = await bench.http.patch(
        "/v1/agent/settings",
        json={"response_language": "de", "response_length": "concise"},
        headers=bearer(person),
    )
    other = await bench.http.get("/v1/agent/settings", headers=bearer((Home.RU, uuid.uuid4())))

    assert before.json() == DEFAULTS
    assert changed.json() == DEFAULTS | {"web_search": False}
    assert again.json() == DEFAULTS | {
        "web_search": False,
        "response_language": "de",
        "response_length": "concise",
    }
    assert other.json() == DEFAULTS


async def test_a_model_other_than_auto_a_foreign_language_or_field_is_refused(
    bench: SettingsBench,
) -> None:
    person = (Home.EU, uuid.uuid4())
    refused = [
        await bench.http.patch("/v1/agent/settings", json=body, headers=bearer(person))
        for body in (
            {"leo_model": "openai/gpt-5"},
            {"response_language": "xx"},
            {"web_search": False, "theme": "dark"},
        )
    ]
    after = await bench.http.get("/v1/agent/settings", headers=bearer(person))

    assert [(answer.status_code, answer.json()["error"]["code"]) for answer in refused] == [
        (422, "leo_model_unavailable"),
        (422, "response_language_invalid"),
        (422, "validation_error"),
    ]
    assert after.json() == DEFAULTS


async def test_the_native_me_carries_the_four_switches_by_the_draft_s_names(
    bench: SettingsBench,
) -> None:
    user_id = uuid.uuid4()
    person = Principal(user_id, Home.RU, 0)
    await bench.http.patch(
        "/v1/agent/settings",
        json={"voice_mode": False, "connected_services_search": False},
        headers=bearer((Home.RU, user_id)),
    )

    assert await bench.preferences.native_me(person) == {
        "leo_voice_enabled": False,
        "leo_kb_search_enabled": True,
        "leo_web_search_enabled": True,
        "leo_connector_search_enabled": False,
    }


async def test_a_request_without_a_person_is_refused(bench: SettingsBench) -> None:
    answer = await bench.http.get("/v1/agent/settings")

    assert answer.status_code == 401
