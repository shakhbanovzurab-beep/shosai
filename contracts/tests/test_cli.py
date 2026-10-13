"""The command line: exit codes, output formats, the check of the baseline documents."""

import json
import shutil
from pathlib import Path

import pytest

from shosai_contracts.cli import EXIT_FAILED, EXIT_INPUT, EXIT_OK, main
from shosai_contracts.inputs import DEFAULT_BASELINE
from shosai_contracts.jsonvalue import JsonObject, as_object, load_json


@pytest.fixture
def broken_openapi(tmp_path: Path) -> Path:
    """A draft OpenAPI that has lost an operation native clients need."""
    document = as_object(load_json(DEFAULT_BASELINE / "openapi.json"), "openapi.json")
    paths: JsonObject = dict(as_object(document["paths"], "paths"))
    del paths["/v1/auth/me"]
    target = tmp_path / "openapi.json"
    target.write_text(json.dumps(document | {"paths": paths}), encoding="utf-8")
    return target


def test_compatible_candidate_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["check", "--openapi", str(DEFAULT_BASELINE / "openapi.json"), "--slice", "S01"])
    assert code == EXIT_OK
    assert "COMPATIBLE" in capsys.readouterr().out


def test_breaking_change_exits_one_and_names_the_operation(
    broken_openapi: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["check", "--openapi", str(broken_openapi), "--slice", "S01", "--format", "json"])
    assert code == EXIT_FAILED
    report = json.loads(capsys.readouterr().out)
    assert report["compatible"] is False
    assert {
        "rule": "operation.missing",
        "subject": "GET /v1/auth/me",
        "class": "native",
    }.items() <= next(
        item for item in report["findings"] if item["subject"] == "GET /v1/auth/me"
    ).items()


def test_acceptance_file_makes_the_change_pass(broken_openapi: Path, tmp_path: Path) -> None:
    accept = tmp_path / "accepted.json"
    accept.write_text(
        json.dumps(
            {
                "format": "whisperer-contract-acceptances/1",
                "accepted": [
                    {
                        "id": "operation.missing GET /v1/auth/me",
                        "reason": "served by the identity slice",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    code = main(
        ["check", "--openapi", str(broken_openapi), "--slice", "S01", "--accept", str(accept)]
    )
    assert code == EXIT_OK


def test_input_errors_exit_two(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["check"]) == EXIT_INPUT
    assert "nothing to check" in capsys.readouterr().err
    bad = tmp_path / "bad.json"
    bad.write_text("{", encoding="utf-8")
    assert main(["check", "--openapi", str(bad)]) == EXIT_INPUT
    assert main(["check", "--websocket", str(tmp_path / "missing.json")]) == EXIT_INPUT


def test_acceptance_without_reason_is_rejected(tmp_path: Path) -> None:
    accept = tmp_path / "accepted.json"
    accept.write_text(
        json.dumps(
            {
                "format": "whisperer-contract-acceptances/1",
                "accepted": [{"id": "x", "reason": " "}],
            }
        ),
        encoding="utf-8",
    )
    openapi = str(DEFAULT_BASELINE / "openapi.json")
    assert main(["check", "--openapi", openapi, "--accept", str(accept)]) == EXIT_INPUT


def test_render_check_detects_stale_documents(tmp_path: Path) -> None:
    baseline = tmp_path / "draft"
    shutil.copytree(DEFAULT_BASELINE, baseline)
    assert main(["--baseline", str(baseline), "render", "--check"]) == EXIT_OK
    (baseline / "websocket.md").write_text("stale\n", encoding="utf-8")
    assert main(["--baseline", str(baseline), "render", "--check"]) == EXIT_FAILED
    assert main(["--baseline", str(baseline), "render"]) == EXIT_OK
    assert main(["--baseline", str(baseline), "render", "--check"]) == EXIT_OK


def test_served_only_check_of_native_routes_names_the_unserved_ones(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    routes = tmp_path / "routes.json"
    routes.write_text(json.dumps(["GET /v1/health"]), encoding="utf-8")
    openapi = tmp_path / "openapi.json"
    openapi.write_text(json.dumps({"openapi": "3.1.0", "paths": {}}), encoding="utf-8")
    arguments = ["check", "--openapi", str(openapi), "--routes", str(routes)]
    arguments += ["--class", "native", "--served-only"]

    code = main([*arguments, "--format", "json"])

    assert code == EXIT_OK
    report = json.loads(capsys.readouterr().out)
    assert report["scope"]["classes"] == ["native"]
    assert "GET /v1/auth/me" in report["unserved"]
    assert "WS /v1/ws/realtime" in report["unserved"]
    assert main(arguments) == EXIT_OK
    assert "Not served by v2 yet:" in capsys.readouterr().out
