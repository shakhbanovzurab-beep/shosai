"""Admin > Platform prompts on the API: the draft, publish once per key, versions by cursor,
restore, and the published layer the consumers read (ST-D1, ADR 0074, step 6)."""

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest_asyncio
from prometheus_client import CollectorRegistry

from shosai.core.idempotency.ledger import EffectLedger
from shosai.core.idempotency.metrics import EffectKeyMetrics
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import ADMIN_COOKIE, ADMIN_GATE
from shosai.features.studio.application.platform_prompts import PlatformPrompts
from shosai.features.studio.application.platform_reader import PlatformPromptReader
from shosai.features.studio.channels.http.admin_platform_prompts import (
    build_admin_platform_prompts_router,
)
from shosai.features.studio.domain.platform_layer import PlatformFeature
from shosai.features.studio.infrastructure.platform_snapshot import PlatformSnapshot
from tests.core.web.probe_app import build_probe_app, client_of
from tests.features.billing.catalogue_bench import ADMIN_SESSION, BenchGate
from tests.harness.database_access import DatabaseAccess

BASE = "/v1/admin/platform-prompts"
SAFETY = {
    "rules": [{"id": "r1", "text": "Cite your sources.", "enabled": True}],
    "blocked_topics": [],
}


@pytest_asyncio.fixture
async def admin(homes: DatabaseAccess) -> AsyncIterator[httpx.AsyncClient]:
    """The admin's client over the slot's EU home."""
    snapshot = PlatformSnapshot(homes.transactions, CollectorRegistry())
    effects = EffectLedger(EffectKeyMetrics(CollectorRegistry()))
    prompts = PlatformPrompts(homes.transactions, (effects, snapshot))
    ports = PortDirectory()
    ports.install([ADMIN_GATE.bind(BenchGate())])
    app = build_probe_app(extra=(build_admin_platform_prompts_router(prompts, ports),)).app
    async with client_of(app) as client:
        client.cookies.set(ADMIN_COOKIE, ADMIN_SESSION)
        yield client


async def publish(admin: httpx.AsyncClient, key: str, comment: str = "Tone.") -> httpx.Response:
    """A publish with its key."""
    return await admin.post(
        f"{BASE}/publish", json={"comment": comment}, headers={"Idempotency-Key": key}
    )


async def drafted(admin: httpx.AsyncClient, prompt: str) -> None:
    """A draft with this system prompt and one rule."""
    reply = await admin.patch(f"{BASE}/draft", json={"system_prompt": prompt, "safety": SAFETY})
    assert reply.status_code == 200, reply.text


def code(reply: httpx.Response) -> tuple[int, Any]:
    """The status and the error code of an answer."""
    return reply.status_code, reply.json()["error"]["code"]


async def test_a_draft_is_published_once_per_key_and_nothing_twice(
    admin: httpx.AsyncClient,
) -> None:
    empty = (await admin.get(BASE)).json()
    await drafted(admin, "Answer plainly.")

    first = await publish(admin, "k1")
    replay = await publish(admin, "k1")
    reused = await publish(admin, "k1", comment="Another.")
    again = await publish(admin, "k2")

    assert (empty["draft"]["updated_at"], empty["published"]) == (None, None)
    assert (first.status_code, replay.status_code) == (201, 201)
    published = first.json()["published"]
    assert (published["number"], published["config"]["system_prompt"]) == (1, "Answer plainly.")
    assert replay.json()["published"]["id"] == published["id"]
    assert code(reused) == (422, "idempotency_key_reused")
    assert code(again) == (409, "nothing_to_publish")


async def test_text_a_model_reads_must_be_english_and_names_its_field(
    admin: httpx.AsyncClient,
) -> None:
    rules = {
        "rules": [{"id": "r", "text": "Отвечай кратко", "enabled": True}],
        "blocked_topics": [],
    }
    await admin.patch(f"{BASE}/draft", json={"safety": rules})

    reply = await publish(admin, "ru")

    assert code(reply) == (422, "platform_prompt_not_english")
    assert reply.json()["error"]["params"] == {"field": "safety.rules.0"}
    assert (await admin.get(BASE)).json()["published"] is None


async def test_concurrent_publishes_take_consecutive_numbers(admin: httpx.AsyncClient) -> None:
    await drafted(admin, "Answer plainly.")

    replies = await asyncio.gather(publish(admin, "a"), publish(admin, "b"))

    assert sorted(reply.status_code for reply in replies) == [201, 409]


async def test_versions_page_newest_first_and_a_restore_is_a_new_version(
    admin: httpx.AsyncClient,
) -> None:
    for index, prompt in enumerate(("One.", "Two.", "Three.")):
        await drafted(admin, prompt)
        assert (await publish(admin, f"v{index}")).status_code == 201

    first = (await admin.get(f"{BASE}/versions", params={"limit": 2})).json()
    rest = (
        await admin.get(f"{BASE}/versions", params={"limit": 2, "cursor": first["next_cursor"]})
    ).json()
    oldest = rest["items"][0]
    whole = (await admin.get(f"{BASE}/versions/{oldest['id']}")).json()
    restored = await admin.post(
        f"{BASE}/versions/{oldest['id']}/restore", json={}, headers={"Idempotency-Key": "back"}
    )
    missing = await admin.post(
        f"{BASE}/versions/{'0' * 8}-0000-7000-8000-000000000000/restore",
        json={},
        headers={"Idempotency-Key": "nowhere"},
    )

    assert [item["number"] for item in first["items"]] == [3, 2]
    assert ([item["number"] for item in rest["items"]], rest["next_cursor"]) == ([1], None)
    assert whole["config"]["system_prompt"] == "One."
    live = restored.json()["published"]
    assert (restored.status_code, live["number"], live["restored_from"]) == (201, 4, 1)
    assert restored.json()["draft"]["config"]["system_prompt"] == "One."
    assert code(missing) == (404, "version_not_found")


async def test_the_consumers_read_the_published_layer_from_the_snapshot(
    admin: httpx.AsyncClient, homes: DatabaseAccess
) -> None:
    reader = PlatformPromptReader(PlatformSnapshot(homes.transactions, CollectorRegistry()))
    before = await reader.platform_layer()
    features = {
        "meeting_summary": {"content": "Lead with decisions.", "enabled": True},
        "voice_mode": {"content": "", "enabled": False},
    }
    await admin.patch(
        f"{BASE}/draft",
        json={"system_prompt": "Answer plainly.", "safety": SAFETY, "features": features},
    )
    await publish(admin, "layer")
    fresh = PlatformPromptReader(PlatformSnapshot(homes.transactions, CollectorRegistry()))

    layer = await fresh.platform_layer()

    assert (before.version, before.text) == (None, "")
    assert layer.version == 1
    assert layer.text.startswith(
        "Answer plainly.\n\nPlatform rules, in order:\n- Cite your sources."
    )
    assert await fresh.feature_prompt(PlatformFeature.MEETING_SUMMARY) == "Lead with decisions."
    assert await fresh.feature_prompt(PlatformFeature.VOICE_MODE) == ""
