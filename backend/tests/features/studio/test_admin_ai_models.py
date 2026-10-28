"""Admin > AI models on the API: the cabinet's contract over the catalogue, F6's reports and
OpenRouter's balance (studio plan §3.5, step 4)."""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest_asyncio
from pydantic import SecretStr

from shosai.core.ai.costs.entries import CostEntry
from shosai.core.ai.spend.reports import SpendReports
from shosai.core.ai.spend.standing import OpenRouterCredits
from shosai.core.kernel.homes import Home
from shosai.core.kernel.ids import new_id
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import ADMIN_COOKIE, ADMIN_GATE
from shosai.features.studio.application.ai_models_screen import AiModelsScreen
from shosai.features.studio.channels.http.admin_ai_models import build_admin_ai_models_router
from tests.core.ai.bench import USER_ID, ai_bench
from tests.core.web.probe_app import build_probe_app, client_of
from tests.doubles.business_calendar import MOSCOW
from tests.doubles.openrouter import ScriptedOpenRouter
from tests.features.billing.catalogue_bench import ADMIN_SESSION, BenchGate
from tests.features.studio.catalogue_bench import catalogue_bench, entry, openrouter_list, price
from tests.harness.database_access import DatabaseAccess

FLASH, SCRIBE = "google/gemini-3.8-flash", "elevenlabs/scribe-v2"
# Расходы пишутся в этот миг, и экран считает «сегодня» и месяц от него же: иначе прогон
# через полночь по Москве (21:00 UTC) кладёт строки во вчерашний день экрана.
NOW = datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class ScreenBench:
    """The admin's client, an anonymous one, and the scripted OpenRouter of the bench."""

    admin: httpx.AsyncClient
    anonymous: httpx.AsyncClient
    openrouter: ScriptedOpenRouter
    management: ScriptedOpenRouter


@pytest_asyncio.fixture
async def screen(homes: DatabaseAccess) -> AsyncIterator[ScreenBench]:
    """The routes over the slot, with a stand-in admin session and a management key."""
    bench = catalogue_bench(homes)
    management = ScriptedOpenRouter()
    credits = OpenRouterCredits(management.client())
    reports = SpendReports(homes.transactions, MOSCOW)
    view = AiModelsScreen(
        homes.transactions,
        (reports, credits, bench.listing),
        SecretStr("sk-or-v1-0123456789abcdef9f2c"),
        clock=lambda: NOW,
    )
    ports = PortDirectory()
    ports.install([ADMIN_GATE.bind(BenchGate())])
    app = build_probe_app(extra=(build_admin_ai_models_router((bench.admin, view), ports),)).app
    async with client_of(app) as admin, client_of(app) as anonymous:
        admin.cookies.set(ADMIN_COOKIE, ADMIN_SESSION)
        yield ScreenBench(admin, anonymous, bench.openrouter, management)


def balance(total: float, used: float) -> httpx.Response:
    """OpenRouter's answer to the credits endpoint."""
    return httpx.Response(200, json={"data": {"total_credits": total, "total_usage": used}})


async def spent(homes: DatabaseAccess, model: str, cost: str, *, when: datetime = NOW) -> None:
    """A recorded call of a person on a model."""
    entry = CostEntry.model_validate(
        {
            "home": Home.RU,
            "user_id": USER_ID,
            "cost_id": new_id(),
            "created_at": when,
            "effect_key": f"screen:{new_id().hex}",
            "provider": "openrouter",
            "model": model,
            "kind": "chat",
            "feature": "leo.turn",
            "call_class": "standard",
            "origin": "interactive",
            "outcome": "ok",
            "input_tokens": 1000,
            "output_tokens": 200,
            "cost_usd": Decimal(cost),
            "cost_source": "reported",
            "exchange_rate_used": Decimal("90.0000"),
            "cost_rub": Decimal(cost) * 90,
        }
    )
    await ai_bench(homes.transactions).writer.write(entry)


async def test_the_screen_shows_the_catalogue_its_prices_spend_and_the_balance(
    screen: ScreenBench, homes: DatabaseAccess
) -> None:
    await price(homes, FLASH, "0.000004125")
    screen.openrouter.answer("models", openrouter_list(entry(FLASH, image=True)))
    added = await screen.admin.post("/v1/admin/ai-models", json={"openrouter_id": FLASH})
    model_id = added.json()["id"]
    await screen.admin.patch(f"/v1/admin/ai-models/{model_id}", json={"enabled": True})
    await screen.admin.put("/v1/admin/ai-models/defaults/leo", json={"model_id": model_id})
    await spent(homes, FLASH, "0.40")
    await spent(homes, SCRIBE, "0.10")
    screen.management.answer("credits", balance(25.0, 5.5))

    answer = await screen.admin.get("/v1/admin/ai-models")

    body = answer.json()
    assert (added.status_code, answer.status_code) == (201, 200)
    assert body["provider"] == {
        "provider": "openrouter", "key_configured": True, "key_hint": "…9f2c",
        "credits": {"total": 25.0, "used": 5.5, "remaining": 19.5}, "source": "backend",
        "sync_error": None,
    }  # fmt: skip
    (model,) = body["models"]
    assert (model["id"], model["enabled"], model["is_default"], model["tier"]) == (
        "google-gemini-3-8-flash", True, True, "standard",
    )  # fmt: skip
    assert (model["price_output_per_m"], model["month_spend"], model["month_requests"]) == (
        4.125, 0.4, 1,
    )  # fmt: skip
    spend = body["spend"]
    assert spend["month"] == 0.5
    assert spend["outside_catalogue"] == {"spend": 0.1, "requests": 1}
    assert len(spend["daily"]) == 30
    assert spend["daily"][-1]["cost"] == spend["today"] == 0.5
    assert body["defaults"] == [
        {"role": "leo", "model_id": "google-gemini-3-8-flash", "fallback_model_id": None}
    ]


async def test_each_refusal_has_its_code_and_status(screen: ScreenBench) -> None:
    screen.openrouter.answer("models", openrouter_list(entry(FLASH)))
    screen.openrouter.answer("models", openrouter_list(entry(FLASH)))
    first = await screen.admin.post("/v1/admin/ai-models", json={"openrouter_id": FLASH})
    model_id = first.json()["id"]

    again = await screen.admin.post("/v1/admin/ai-models", json={"openrouter_id": FLASH})
    off_default = await screen.admin.put(
        "/v1/admin/ai-models/defaults/leo", json={"model_id": model_id}
    )
    missing = await screen.admin.patch("/v1/admin/ai-models/nope", json={"enabled": True})
    no_proposal = await screen.admin.post(
        f"/v1/admin/ai-models/{model_id}/tier", json={"decision": "confirm"}
    )
    retired = await screen.admin.delete(f"/v1/admin/ai-models/{model_id}")
    anonymous = await screen.anonymous.get("/v1/admin/ai-models")

    found = [
        (reply.status_code, reply.json()["error"]["code"])
        for reply in (again, off_default, missing, no_proposal)
    ]
    assert found == [
        (409, "model_already_listed"),
        (422, "model_disabled"),
        (404, "model_not_found"),
        (409, "no_tier_proposal"),
    ]
    assert retired.status_code == 204
    assert (anonymous.status_code, anonymous.json()["error"]["code"]) == (
        401,
        "admin_sign_in_required",
    )


async def test_the_check_times_a_fresh_balance_and_names_a_failure(screen: ScreenBench) -> None:
    screen.management.answer("credits", balance(10.0, 1.0))
    screen.management.answer("credits", httpx.Response(502))

    working = (await screen.admin.post("/v1/admin/ai-models/check")).json()
    failing = (await screen.admin.post("/v1/admin/ai-models/check")).json()

    assert (working["ok"], working["code"], working["provider"]["credits"]["remaining"]) == (
        True,
        None,
        9.0,
    )
    assert working["latency_ms"] is not None
    assert (failing["ok"], failing["code"], failing["latency_ms"]) == (
        False,
        "openrouter_unreachable",
        None,
    )
    assert failing["provider"]["sync_error"] == "openrouter_unreachable"


async def test_the_months_tokens_requests_and_forecast_come_from_f6(
    screen: ScreenBench, homes: DatabaseAccess
) -> None:
    await spent(homes, FLASH, "0.70")
    screen.management.answer("credits", balance(1.0, 0.0))

    spend = (await screen.admin.get("/v1/admin/ai-models")).json()["spend"]

    assert (spend["tokens_in_month"], spend["tokens_out_month"], spend["requests_month"]) == (
        1000,
        200,
        1,
    )
    assert spend["forecast_month"] >= spend["month"] == 0.7
