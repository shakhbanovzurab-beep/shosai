"""The whole check: scope, classes, accepted deviations, routes outside OpenAPI."""

import pytest

from shosai_contracts.check import check
from shosai_contracts.inputs import Baseline, BaselineOperation, Candidate, Scope, parse_routes
from shosai_contracts.jsonvalue import ContractInputError, JsonObject
from shosai_contracts.model import CompatClass, Severity
from shosai_contracts.ws_catalogue import CATALOGUE_FORMAT, parse_catalogue

ITEM: JsonObject = {"type": "object", "properties": {"id": {"type": "string"}}, "required": ["id"]}
EMPTY: JsonObject = {"type": "object", "properties": {}}


def spec(*paths: tuple[str, str, JsonObject]) -> JsonObject:
    entries: JsonObject = {}
    for path, method, schema in paths:
        content: JsonObject = {"application/json": {"schema": schema}}
        entries[path] = {method: {"responses": {"200": {"description": "ok", "content": content}}}}
    return {"openapi": "3.1.0", "paths": entries}


def op(
    method: str, path: str, slice_id: str, compat_class: CompatClass, *, in_openapi: bool = True
) -> BaselineOperation:
    return BaselineOperation(method, path, in_openapi, slice_id, compat_class)


WS = parse_catalogue(
    {
        "format": CATALOGUE_FORMAT,
        "endpoints": [
            {
                "path": "/v1/ws/user",
                "slice": "S09",
                "class": "native",
                "discriminator": "type",
                "frames": [
                    {
                        "direction": "server_to_client",
                        "type": "reminder.due",
                        "encoding": "json",
                        "class": "native",
                    }
                ],
            }
        ],
    },
    "baseline",
)

BASELINE = Baseline(
    openapi=spec(
        ("/v1/auth/me", "get", ITEM),
        ("/v1/me/hubs", "get", ITEM),
        ("/v1/me/legacy", "get", ITEM),
        ("/health", "get", ITEM),
    ),
    operations=(
        op("GET", "/v1/auth/me", "S01", CompatClass.NATIVE),
        op("GET", "/v1/me/hubs", "S16", CompatClass.WEB),
        op("GET", "/v1/me/legacy", "S16", CompatClass.UNUSED),
        op("GET", "/health", "F1", CompatClass.EXCLUDED),
        op("GET", "/j/{token}", "S06", CompatClass.EXTERNAL, in_openapi=False),
    ),
    websocket=WS,
)
BROKEN = spec(
    ("/v1/auth/me", "get", EMPTY), ("/v1/me/hubs", "get", EMPTY), ("/v1/me/legacy", "get", EMPTY)
)


def severities(candidate: Candidate, scope: Scope | None = None) -> dict[str, str]:
    report = check(BASELINE, candidate, scope)
    return {f"{item.subject} {item.rule}": item.severity.value for item in report.findings}


def test_severity_follows_the_consumer_class() -> None:
    assert severities(Candidate(openapi=BROKEN)) == {
        "GET /v1/auth/me response.property_removed": "error",
        "GET /v1/me/hubs response.property_removed": "warning",
        "GET /v1/me/legacy response.property_removed": "info",
    }


def test_excluded_operations_are_not_checked() -> None:
    report = check(BASELINE, Candidate(openapi=spec()))
    assert all(item.subject != "GET /health" for item in report.findings)
    assert report.coverage.operations == 3


def test_scope_limits_by_slice_and_prefix() -> None:
    assert set(severities(Candidate(openapi=BROKEN), Scope(slices=frozenset({"S01"})))) == {
        "GET /v1/auth/me response.property_removed"
    }
    assert set(severities(Candidate(openapi=BROKEN), Scope(path_prefixes=("/v1/me/",)))) == {
        "GET /v1/me/hubs response.property_removed",
        "GET /v1/me/legacy response.property_removed",
    }


def test_missing_operation_and_undocumented_route() -> None:
    routes = parse_routes(["GET /v1/auth/me"], "routes")
    found = severities(
        Candidate(openapi=spec(), routes=routes), Scope(slices=frozenset({"S01", "S06"}))
    )
    assert found == {
        "GET /v1/auth/me operation.not_in_openapi": "warning",
        "GET /j/{token} route.missing": "error",
    }
    found = severities(Candidate(openapi=spec()), Scope(slices=frozenset({"S01"})))
    assert found == {"GET /v1/auth/me operation.missing": "error"}


def test_route_snapshot_matches_regardless_of_parameter_names() -> None:
    routes = parse_routes(["GET /j/{invite}"], "routes")
    report = check(BASELINE, Candidate(routes=routes), Scope(slices=frozenset({"S06"})))
    assert report.findings == ()
    assert report.coverage.routes == 1


def test_acceptances_turn_errors_into_accepted_info() -> None:
    finding_id = "response.property_removed GET /v1/auth/me response.200.id"
    report = check(
        BASELINE,
        Candidate(openapi=BROKEN),
        Scope(slices=frozenset({"S01"})),
        {finding_id: "id moved to the envelope; clients updated", "unknown x": "stale"},
    )
    assert report.is_compatible
    (finding,) = report.findings
    assert finding.severity is Severity.INFO
    assert finding.accepted_reason
    assert report.unused_acceptances == ("unknown x",)


def test_websocket_endpoint_and_frames() -> None:
    report = check(BASELINE, Candidate(websocket=()))
    assert [(item.rule, item.severity.value) for item in report.findings] == [
        ("ws.endpoint_missing", "error")
    ]
    same = check(BASELINE, Candidate(websocket=WS))
    assert same.findings == ()
    assert same.coverage.websocket_frames == 1


def test_baseline_inconsistency_is_reported_not_skipped() -> None:
    inconsistent = Baseline(
        openapi=spec(),
        operations=(op("GET", "/v1/ghost", "S01", CompatClass.NATIVE),),
        websocket=(),
    )
    with pytest.raises(ContractInputError, match="not"):
        check(inconsistent, Candidate(openapi=spec()))


def test_route_snapshot_rejects_malformed_entries() -> None:
    with pytest.raises(ContractInputError, match="METHOD /path"):
        parse_routes(["/v1/me"], "routes")


def test_scope_limits_by_consumer_class() -> None:
    native = Scope(classes=frozenset({CompatClass.NATIVE}))
    assert severities(Candidate(openapi=BROKEN), native) == {
        "GET /v1/auth/me response.property_removed": "error"
    }
    report = check(BASELINE, Candidate(websocket=()), Scope(classes=frozenset({CompatClass.WEB})))
    assert report.coverage.websocket_endpoints == 0


def test_served_only_lists_what_v2_does_not_serve_instead_of_failing() -> None:
    served_only = Scope(classes=frozenset({CompatClass.NATIVE}), served_only=True)
    report = check(BASELINE, Candidate(openapi=spec(), routes=frozenset()), served_only)
    assert report.is_compatible
    assert report.unserved == ("GET /v1/auth/me", "WS /v1/ws/user")
    assert report.coverage.operations == 0

    broken = check(BASELINE, Candidate(openapi=BROKEN, routes=frozenset()), served_only)
    assert not broken.is_compatible
    assert broken.unserved == ("WS /v1/ws/user",)
    assert broken.coverage.operations == 1


def test_a_websocket_in_the_route_snapshot_without_a_catalogue_is_unverified() -> None:
    routes = parse_routes(["WS /v1/ws/user"], "routes")
    found = severities(Candidate(routes=routes), Scope(slices=frozenset({"S09"})))
    assert found == {"WS /v1/ws/user ws.not_in_catalogue": "warning"}
    assert severities(Candidate(routes=frozenset()), Scope(slices=frozenset({"S09"}))) == {
        "WS /v1/ws/user ws.endpoint_missing": "error"
    }
