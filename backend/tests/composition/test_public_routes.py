"""The public surface of `api` and `ws` as composed from every listed slice (§10, §14 rule 12).

Three CI gates over the apps the roles really build:

- the route snapshot: a route added, moved or removed fails the test until
  `public_routes.json` is updated in the same commit, so the change is deliberate and
  reviewed;
- the native-contract gate: every route of the shipped macOS and Windows clients that the
  apps serve keeps its draft contract, whichever slice serves it; the native routes not
  served yet are recorded in `native_routes_not_served.json`, which must be empty before
  cutover (F1 audit OD-2, `contracts/README.md`);
- the OpenAPI document: `backend/openapi.json` equals the api app's document, so the web
  cabinet generates its client types from the contract the code serves (F2 plan §2.5).
"""

import json
from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
import pytest_asyncio
from fastapi import FastAPI
from opentelemetry.sdk.trace import TracerProvider
from prometheus_client import CollectorRegistry
from shosai_contracts import (
    Candidate,
    CompatClass,
    Report,
    Scope,
    Severity,
    check,
    load_baseline,
    parse_routes,
    render_text,
)
from shosai_contracts.jsonvalue import Json

from shosai.composition.features import FEATURES, feature_settings_sections
from shosai.composition.platform import open_platform
from shosai.composition.roles import public_app
from shosai.composition.telemetry import ProcessTelemetry
from shosai.core.config.loading import load_settings
from shosai.core.config.roles import ProcessRole
from shosai.core.features import FeatureModule
from tests.composition.fixture_features import NATIVE_ROUTE, native_breaking_feature
from tests.composition.public_routes import route_snapshot
from tests.harness.process_environ import slot_environ
from tests.harness.run_slot import RunSlot
from tests.harness.settings import HarnessSettings

SNAPSHOT = Path(__file__).with_name("public_routes.json")
NOT_SERVED = Path(__file__).with_name("native_routes_not_served.json")
OPENAPI_DOCUMENT = Path(__file__).parents[2] / "openapi.json"
# Только маршруты выпущенных macOS и Windows 1.4.5, какой бы срез их ни обслуживал (OD-2).
NATIVE_GATE = Scope(classes=frozenset({CompatClass.NATIVE}), served_only=True)


@asynccontextmanager
async def compose(
    run_slot: RunSlot, harness_settings: HarnessSettings, features: Sequence[FeatureModule]
) -> AsyncIterator[dict[str, FastAPI]]:
    """The public apps of `api` and `ws` with the given slices."""
    settings = load_settings(
        slot_environ(run_slot, harness_settings), feature_settings_sections(features)
    )
    async with open_platform(settings, ProcessRole.API, own_telemetry(), features) as platform:
        # Каждая роль — свой процесс со своим реестром метрик; здесь оба приложения в одном.
        yield {
            "api": public_app(platform, own_telemetry(), platform.parts.http_routers),
            "ws": public_app(platform, own_telemetry(), platform.parts.ws_routers),
        }


@pytest_asyncio.fixture
async def composed_apps(
    run_slot: RunSlot, harness_settings: HarnessSettings
) -> AsyncIterator[dict[str, FastAPI]]:
    """The public apps of `api` and `ws` with every listed slice."""
    async with compose(run_slot, harness_settings, FEATURES) as apps:
        yield apps


def native_contract(apps: Mapping[str, FastAPI]) -> Report:
    """The native-contract gate over the routes of every app and the api app's OpenAPI."""
    routes: list[Json] = [route for app in apps.values() for route in route_snapshot(app)]
    candidate = Candidate(openapi=apps["api"].openapi(), routes=parse_routes(routes, SNAPSHOT.name))
    return check(load_baseline(), candidate, NATIVE_GATE)


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


def test_the_composed_apps_keep_the_native_contract(composed_apps: dict[str, FastAPI]) -> None:
    report = native_contract(composed_apps)

    assert report.is_compatible, render_text(report, NATIVE_GATE)


def test_the_native_routes_not_served_yet_are_recorded(
    composed_apps: dict[str, FastAPI],
) -> None:
    current = list(native_contract(composed_apps).unserved)
    recorded = json.loads(NOT_SERVED.read_text(encoding="utf-8"))

    assert current == recorded, (
        f"нативные маршруты без обслуживания изменились; обновите {NOT_SERVED.name} "
        "в том же коммите:\n" + json.dumps(current, indent=2)
    )


@pytest.mark.parametrize("name", ["identity", "notes"])
async def test_a_slice_breaking_a_native_route_fails_the_gate_whatever_its_name(
    run_slot: RunSlot, harness_settings: HarnessSettings, name: str
) -> None:
    # Срез-нарушитель занимает место настоящего среза с тем же именем.
    features = (*(f for f in FEATURES if f.name != name), native_breaking_feature(name))
    async with compose(run_slot, harness_settings, features) as apps:
        report = native_contract(apps)

    assert not report.is_compatible
    assert {item.subject for item in report.findings if item.severity is Severity.ERROR} == {
        f"GET {NATIVE_ROUTE}"
    }
    assert f"GET {NATIVE_ROUTE}" not in report.unserved


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
