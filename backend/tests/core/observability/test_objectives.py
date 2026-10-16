"""Declarations of objectives and monitors, and the rules rendered from them (F5 plan §3.8)."""

import json
from collections.abc import Callable
from dataclasses import replace

import pytest

from shosai.core.observability.objectives import (
    AlertClass,
    EventRatio,
    InvariantMonitor,
    Journey,
    LatencyRatio,
    NeverIncreases,
    ServiceLevelObjective,
    StaysAtMost,
)
from shosai.core.observability.rule_files import OwnerRules, render

LATENCY = LatencyRatio("http_server_request_duration_seconds", 'home="eu"', "0.3")
ERRORS = EventRatio(total='requests_total{route="/x"}', bad='requests_total{route="/x",code="500"}')


BASE = ServiceLevelObjective(
    name="reads_latency",
    journey=Journey("cabinet_api", "Кабинет"),
    summary="Медленно",
    promise="страницы открываются быстро",
    target=0.95,
    indicator=LATENCY,
)


@pytest.mark.parametrize(
    "malformed",
    [
        lambda: replace(BASE, name="Reads"),
        lambda: replace(BASE, journey=Journey("cabinet-api", "Кабинет")),
        lambda: replace(BASE, target=1.0),
        lambda: replace(BASE, target=0.4),
    ],
    ids=["name", "journey", "target-one", "target-low"],
)
def test_a_malformed_objective_is_refused(malformed: Callable[[], ServiceLevelObjective]) -> None:
    with pytest.raises(ValueError, match=r"."):
        malformed()


def test_malformed_monitors_are_refused() -> None:
    with pytest.raises(ValueError, match="монитор"):
        InvariantMonitor("Dead letters", "inv-8", "x", "y", StaysAtMost("m"))
    with pytest.raises(ValueError, match="окно"):
        NeverIncreases("m_total", "15 minutes")
    with pytest.raises(ValueError, match="датчик"):
        StaysAtMost('m{queue="a"}')


def test_indicators_read_rates_of_counters() -> None:
    assert ERRORS.bad_ratio("5m") == (
        '(sum(rate(requests_total{route="/x",code="500"}[5m])) or vector(0))'
        ' / sum(rate(requests_total{route="/x"}[5m]))'
    )
    assert LATENCY.bad_ratio("1h") == (
        '1 - sum(rate(http_server_request_duration_seconds_bucket{home="eu",le="0.3"}[1h]))'
        ' / sum(rate(http_server_request_duration_seconds_count{home="eu"}[1h]))'
    )


def test_each_owner_gets_its_files_and_the_burn_limits_follow_the_budget() -> None:
    tracked = replace(BASE, name="reads_latency_ru", alerting=AlertClass.TICKET)
    monitor = InvariantMonitor("dead_letter_present", "inv-8", "Есть", "Плохо", StaysAtMost("dead"))
    files = render({"core": OwnerRules((BASE, tracked), (monitor,)), "empty": OwnerRules()})

    assert sorted(files) == ["core.alerts.json", "core.alerts.test.json", "core.recording.json"]
    rules = {
        rule["alert"]: rule
        for group in json.loads(files["core.alerts.json"])["groups"]
        for rule in group["rules"]
    }
    fast = rules["ReadsLatencyBudgetBurnFast"]
    assert fast["expr"] == (
        "slo:reads_latency:bad_ratio:rate1h > 0.72 and slo:reads_latency:bad_ratio:rate5m > 0.72"
    )
    assert [rules[f"ReadsLatency{kind}"]["labels"]["severity"] for kind in ("BudgetBurnFast",
            "BudgetBurnSlow", "BudgetBurnTicket")] == ["page", "page", "ticket"]  # fmt: skip
    assert rules["ReadsLatencyRuBudgetBurnFast"]["labels"]["severity"] == "ticket"
    assert rules["DeadLetterPresent"]["expr"] == "max(dead) > 0"
    assert rules["DeadLetterPresent"]["labels"] == {"severity": "page", "invariant": "inv-8"}
    assert rules["DeadLetterPresent"]["annotations"]["description"] == "Плохо"
    assert fast["annotations"]["description"].startswith(
        "Мы обещаем, что страницы открываются быстро."
    )
