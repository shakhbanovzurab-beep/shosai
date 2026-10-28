"""Settings > Connectors over HTTP: the list, a disconnect, a given secret, a scope picker's
browse and the limits, each on the person's own rows only (connectors plan §3.7)."""

import uuid
from typing import Any

from sqlalchemy import select

from shosai.core.events.records import OutboxMessage
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.connectors.domain.catalogue import App
from shosai.features.connectors.infrastructure.store.records import GrantSecretRecord
from tests.features.billing.people_bench import bearer
from tests.features.connectors.cabinet_bench import GOOD_KEY, CabinetBench, cabinet
from tests.features.connectors.connect_bench import connect_bench
from tests.features.connectors.lifecycle_bench import lifecycle
from tests.features.connectors.transport_bench import transport

__all__ = ["cabinet", "connect_bench", "lifecycle", "transport"]


def someone() -> tuple[Home, uuid.UUID]:
    """A new person in the Russian home."""
    return Home.RU, uuid.uuid4()


async def listed(bench: CabinetBench, person: tuple[Home, uuid.UUID]) -> dict[str, Any]:
    """The person's rows by app."""
    answer = await bench.http.get("/v1/connectors", headers=bearer(person))
    assert answer.status_code == 200
    return {item["id"]: item for item in answer.json()["items"]}


async def test_the_list_shows_offered_apps_and_the_person_s_connections(
    cabinet: CabinetBench,
) -> None:
    person = someone()
    before = await listed(cabinet, person)
    await cabinet.transport.lifecycle.connected(person, App.GOOGLE_CALENDAR)
    alone = await listed(cabinet, person)
    await cabinet.transport.lifecycle.connected(person, App.GOOGLE_DRIVE)
    shared = await listed(cabinet, person)

    assert list(before) == ["google_calendar", "google_drive", "slack", "affinity"]
    assert before["affinity"]["auth"] == "api_key"
    assert before["google_calendar"]["status"] == "not_connected"
    calendar = alone["google_calendar"]
    assert (calendar["status"], calendar["connected"]) == ("connected", True)
    assert calendar["account"] == "anna@example.com"
    assert calendar["category"] == "calendar"
    assert calendar["access_remains_at_provider"] is False
    assert shared["google_calendar"]["access_remains_at_provider"] is True
    assert "token" not in str(shared)


async def test_a_person_sees_and_disconnects_only_their_own(cabinet: CabinetBench) -> None:
    owner, stranger = someone(), someone()
    await cabinet.transport.lifecycle.connected(owner, App.GOOGLE_CALENDAR)

    seen = await listed(cabinet, stranger)
    refused = await cabinet.http.delete("/v1/connectors/google_calendar", headers=bearer(stranger))
    done = await cabinet.http.delete("/v1/connectors/google_calendar", headers=bearer(owner))
    again = await cabinet.http.delete("/v1/connectors/google_calendar", headers=bearer(owner))
    unknown = await cabinet.http.delete("/v1/connectors/nango", headers=bearer(owner))

    assert seen["google_calendar"]["status"] == "not_connected"
    assert (refused.status_code, refused.json()["error"]["code"]) == (404, "not_connected")
    assert done.status_code == 204
    assert (await listed(cabinet, owner))["google_calendar"]["connected"] is False
    assert again.status_code == 404
    assert unknown.json()["error"]["code"] == "unknown_app"
    async with cabinet.transport.lifecycle.connect.homes.transactions.begin(
        TenancyScope(Home.RU), read_only=True
    ) as session:
        types = (await session.execute(select(OutboxMessage.event_type))).scalars().all()
    assert "connectors.connection.revoked" in types


async def test_a_given_key_is_probed_then_kept_encrypted(cabinet: CabinetBench) -> None:
    person = someone()
    path = "/v1/connectors/affinity/credentials"

    rejected = await cabinet.http.post(path, json={"api_key": "bad"}, headers=bearer(person))
    two = await cabinet.http.post(
        path, json={"api_key": GOOD_KEY, "password": "x"}, headers=bearer(person)
    )
    kept = await cabinet.http.post(path, json={"api_key": GOOD_KEY}, headers=bearer(person))
    unoffered = await cabinet.http.post(
        "/v1/connectors/zapier/credentials", json={"webhook_url": "https://hooks.test/1"},
        headers=bearer(person),
    )  # fmt: skip

    assert (rejected.status_code, rejected.json()["error"]["code"]) == (
        422, "credentials_rejected",
    )  # fmt: skip
    assert two.status_code == 422
    assert kept.status_code == 200
    assert (kept.json()["status"], kept.json()["account"]) == ("connected", "team@affinity.test")
    assert (unoffered.status_code, unoffered.json()["error"]["code"]) == (409, "not_offered")
    home, user_id = person
    connect = cabinet.transport.lifecycle.connect
    async with connect.homes.transactions.begin(TenancyScope(home, user_id)) as session:
        sealed = await session.scalar(select(GrantSecretRecord.secret_enc))
    assert sealed is not None
    assert GOOD_KEY.encode() not in sealed
    assert connect.keys.decrypt(sealed) == GOOD_KEY


async def test_a_picker_browses_through_the_person_s_session(cabinet: CabinetBench) -> None:
    person = someone()
    path = "/v1/connectors/google_drive/resources"

    before = await cabinet.http.get(path, params={"kind": "folder"}, headers=bearer(person))
    await cabinet.transport.lifecycle.connected(person, App.GOOGLE_DRIVE)
    page = await cabinet.http.get(
        path, params={"kind": "folder", "parent": "root"}, headers=bearer(person)
    )
    other_kind = await cabinet.http.get(path, params={"kind": "site"}, headers=bearer(person))
    busy = await cabinet.http.get(
        path, params={"kind": "folder", "parent": "busy"}, headers=bearer(person)
    )
    no_browser = await cabinet.http.get(
        "/v1/connectors/google_calendar/resources", params={"kind": "folder"},
        headers=bearer(person),
    )  # fmt: skip

    assert (before.status_code, before.json()["error"]["code"]) == (404, "not_connected")
    assert page.status_code == 200
    assert page.json() == {
        "items": [{
            "id": "f-1", "name": "Bearer access-anna", "kind": "folder", "parent_id": "root",
            "has_children": False, "url": None,
        }],
        "next_cursor": None,
    }  # fmt: skip
    assert other_kind.json()["error"]["code"] == "resources_unsupported"
    assert (busy.status_code, busy.headers["retry-after"]) == (503, "7")
    assert busy.json()["error"]["code"] == "provider_busy"
    assert no_browser.status_code == 404


async def test_connecting_by_a_secret_and_starting_a_flow_are_limited_per_person(
    cabinet: CabinetBench,
) -> None:
    person, other = someone(), someone()
    path = "/v1/connectors/affinity/credentials"

    tries = [
        (await cabinet.http.post(path, json={"api_key": "bad"}, headers=bearer(person))).status_code
        for _ in range(6)
    ]
    others = await cabinet.http.post(path, json={"api_key": "bad"}, headers=bearer(other))
    starts = [
        (await cabinet.http.post(
            "/v1/connectors/google_calendar/authorize", json={}, headers=bearer(person)
        )).status_code
        for _ in range(11)
    ]  # fmt: skip

    assert tries == [422] * 5 + [429]
    assert others.status_code == 422
    assert starts == [200] * 10 + [429]
