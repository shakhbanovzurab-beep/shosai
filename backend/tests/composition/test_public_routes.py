"""The public surface of `api` and `ws` as composed from every listed slice (§10, §14 rule 12).

Three CI gates over the apps the roles really build:

- the route snapshot: a route added, moved or removed fails the test until
  `public_routes.json` is updated in the same commit, so the change is deliberate and
  reviewed;
- the D1 gate: every draft route owned by F1 or a listed slice keeps its contract for the
  shipped clients (`contracts/README.md`);
- the OpenAPI document: `backend/openapi.json` equals the api app's document, so the web
  cabinet generates its client types from the contract the code serves (F2 plan §2.5).
"""

import json
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from fastapi import FastAPI
from opentelemetry.sdk.trace import TracerProvider
from prometheus_client import CollectorRegistry
from shosai_contracts import Candidate, Scope, check, load_baseline, parse_routes, render_text
from shosai_contracts.jsonvalue import Json

from shosai.composition.features import FEATURES, contract_slices
from shosai.composition.platform import open_platform
from shosai.composition.roles import public_app
from shosai.composition.telemetry import ProcessTelemetry
from shosai.core.config.loading import load_settings
from shosai.core.config.roles import ProcessRole
from tests.composition.public_routes import route_snapshot
from tests.harness.process_environ import slot_environ
from tests.harness.run_slot import RunSlot
from tests.harness.settings import HarnessSettings

SNAPSHOT = Path(__file__).with_name("public_routes.json")
OPENAPI_DOCUMENT = Path(__file__).parents[2] / "openapi.json"


@pytest_asyncio.fixture
async def composed_apps(
    run_slot: RunSlot, harness_settings: HarnessSettings
) -> AsyncIterator[dict[str, FastAPI]]:
    """The public apps of `api` and `ws` with every listed slice."""
    settings = load_settings(slot_environ(run_slot, harness_settings))
    async with open_platform(settings, ProcessRole.API, own_telemetry(), FEATURES) as platform:
        # Каждая роль — свой процесс со своим реестром метрик; здесь оба приложения в одном.
        yield {
            "api": public_app(platform, own_telemetry(), platform.parts.http_routers),
            "ws": public_app(platform, own_telemetry(), platform.parts.ws_routers),
        }


def own_telemetry() -> ProcessTelemetry:
    """Telemetry of one more process: its own registry and tracer provider."""
    return ProcessTelemetry(CollectorRegistry(), TracerProvider(shutdown_on_exit=False))


def test_the_public_routes_match_the_snapshot(composed_apps: dict[str, FastAPI]) -> None:
    current = {role: route_snapshot(app) for role, app in composed_apps.items()}
    recorded = json.loads(SNAPSHOT.read_text(encoding="utf-8"))

    assert current == recorded, (
        f"публичные маршруты изменились; обновите {SNAPSHOT.name} в том же коммите:\n"
        + json.dumps(current, indent=2)
    )


def test_the_composed_apps_keep_the_draft_contract_of_every_slice(
    composed_apps: dict[str, FastAPI],
) -> None:
    routes: list[Json] = [route for app in composed_apps.values() for route in route_snapshot(app)]
    candidate = Candidate(
        openapi=composed_apps["api"].openapi(), routes=parse_routes(routes, SNAPSHOT.name)
    )
    scope = Scope(slices=contract_slices(FEATURES))

    report = check(load_baseline(), candidate, scope)

    assert report.is_compatible, render_text(report, scope)


def test_the_openapi_document_matches_the_api_app(
    composed_apps: dict[str, FastAPI], request: pytest.FixtureRequest
) -> None:
    current = json.dumps(composed_apps["api"].openapi(), indent=2, ensure_ascii=False) + "\n"
    if request.config.getoption("--update-openapi"):
        OPENAPI_DOCUMENT.write_text(current, encoding="utf-8")

    recorded = OPENAPI_DOCUMENT.read_text(encoding="utf-8")

    assert current == recorded, (
        f"OpenAPI api-приложения изменился; перепишите {OPENAPI_DOCUMENT.name} опцией "
        "--update-openapi, затем в frontend/ выполните npm run api:types и закоммитьте оба файла"
    )
