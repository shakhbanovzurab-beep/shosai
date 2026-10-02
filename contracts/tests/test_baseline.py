"""The recorded draft baseline: completeness, consistent classes, up-to-date documents."""

import json
from pathlib import Path

import pytest

from whisperer_contracts.check import check
from whisperer_contracts.inputs import DEFAULT_BASELINE, Candidate, load_baseline, parse_routes
from whisperer_contracts.jsonvalue import Json, JsonObject, as_list, as_object, load_json
from whisperer_contracts.model import CompatClass
from whisperer_contracts.render_docs import render_baseline_documents

# Рабочие клиенты по решению владельца (2026-10-01): Linux 0.1.0 заморожен, iOS не выпущен.
SHIPPED_APPS = frozenset({"macos", "windows"})


def _objects(value: Json) -> list[JsonObject]:
    return [as_object(item, "item") for item in as_list(value, "list")]


@pytest.fixture(scope="module")
def consumers() -> JsonObject:
    return as_object(load_json(DEFAULT_BASELINE / "consumers.json"), "consumers.json")


@pytest.fixture(scope="module")
def routes() -> list[JsonObject]:
    return _objects(load_json(DEFAULT_BASELINE / "routes.json"))


def test_every_http_route_is_classified_once(
    consumers: JsonObject, routes: list[JsonObject]
) -> None:
    expected = {(row["method"], row["path"]) for row in routes if row["kind"] != "websocket"}
    listed = [(item["method"], item["path"]) for item in _objects(consumers["operations"])]
    assert len(listed) == len(set(listed)), "an operation is classified twice"
    assert set(listed) == expected


def test_every_websocket_route_is_catalogued(routes: list[JsonObject]) -> None:
    expected = {row["path"] for row in routes if row["kind"] == "websocket"}
    assert {endpoint.path for endpoint in load_baseline().websocket} == expected


def test_in_openapi_flags_match_the_document(consumers: JsonObject) -> None:
    openapi = as_object(load_json(DEFAULT_BASELINE / "openapi.json"), "openapi.json")
    documented = {
        (method.upper(), path)
        for path, item in as_object(openapi["paths"], "paths").items()
        for method in as_object(item, path)
    }
    flagged = {
        (item["method"], item["path"])
        for item in _objects(consumers["operations"])
        if item["in_openapi"] is True
    }
    assert flagged == documented


def test_routes_outside_openapi_are_explained(consumers: JsonObject) -> None:
    """A route outside OpenAPI (page, link, service endpoint) must explain who expects it."""
    for item in _objects(consumers["operations"]):
        if item["in_openapi"] is not True:
            assert str(item["reason"]).strip(), f"{item['method']} {item['path']}"


def test_shipped_app_usage_is_always_must_keep(consumers: JsonObject) -> None:
    """A live call from the code of a working app makes the endpoint native, no exceptions."""
    for item in _objects(consumers["operations"]):
        clients = {ref["client"] for ref in _objects(item["consumers"]) if not ref.get("dead")}
        if clients & SHIPPED_APPS:
            assert item["class"] == CompatClass.NATIVE.value, f"{item['method']} {item['path']}"


def test_shipped_app_frames_are_must_keep() -> None:
    document = as_object(load_json(DEFAULT_BASELINE / "websocket.json"), "websocket.json")
    for endpoint in _objects(document["endpoints"]):
        for frame in _objects(endpoint["frames"]):
            clients = {ref["client"] for ref in _objects(frame["consumers"])}
            if clients & SHIPPED_APPS:
                assert frame["class"] == CompatClass.NATIVE.value, (
                    f"{endpoint['path']} {frame['type']}"
                )


def test_dead_call_sites_carry_evidence_and_never_raise_the_class(consumers: JsonObject) -> None:
    """Dead code is not carried over: its call is recorded with evidence, not raising the class."""
    for item in _objects(consumers["operations"]):
        refs = _objects(item["consumers"])
        for ref in refs:
            if "dead" in ref:
                assert str(ref["dead"]).startswith("Dead code: "), ref
        if refs and all(ref.get("dead") for ref in refs):
            assert item["class"] in {CompatClass.UNUSED.value, CompatClass.EXTERNAL.value}, item[
                "path"
            ]


def test_every_consumer_reference_names_a_known_client(consumers: JsonObject) -> None:
    known = {client["id"] for client in _objects(consumers["clients"])}
    used = {
        ref["client"]
        for item in _objects(consumers["operations"])
        for ref in _objects(item["consumers"])
    }
    assert used <= known


def test_baseline_is_compatible_with_itself(routes: list[JsonObject]) -> None:
    baseline = load_baseline()
    snapshot: list[Json] = [f"{row['method']} {row['path']}" for row in routes]
    report = check(
        baseline,
        Candidate(
            openapi=baseline.openapi,
            routes=parse_routes(snapshot, "routes"),
            websocket=baseline.websocket,
        ),
    )
    assert report.findings == ()
    assert report.coverage.operations > 500
    assert report.coverage.websocket_endpoints == len(baseline.websocket)


def test_markdown_documents_are_rendered_from_the_json() -> None:
    for name, content in render_baseline_documents(DEFAULT_BASELINE).items():
        committed = (DEFAULT_BASELINE / name).read_text(encoding="utf-8")
        assert committed == content, f"{name} is stale: run `uv run whisperer-contracts render`"


def test_openapi_is_stored_in_canonical_form() -> None:
    """The canonical form (sorted keys) keeps the baseline diff readable on updates."""
    path: Path = DEFAULT_BASELINE / "openapi.json"
    raw = path.read_text(encoding="utf-8")
    assert raw == json.dumps(json.loads(raw), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
