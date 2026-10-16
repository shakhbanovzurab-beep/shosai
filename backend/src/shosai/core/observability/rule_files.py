"""Prometheus rules and their promtool tests rendered from the declarations (F5 plan §3.8).

For each owner — `core` or a slice — three JSON files (JSON is YAML to Prometheus and
promtool): `<owner>.recording.json` records each SLO's share of bad events over the burn
windows; `<owner>.alerts.json` holds the multi-window burn-rate alerts of each SLO (fast and
slow burn page, or ticket when the SLO is tracked, not paged; a 3-day burn is always a
ticket) and one page per invariant monitor; `<owner>.alerts.test.json` fires and resolves
every one of those alerts in promtool.
"""

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from shosai.core.observability.objectives import (
    AlertClass,
    InvariantMonitor,
    NeverIncreases,
    ServiceLevelObjective,
)

RUNBOOK = "docs/runbooks/alerts.md"
# Дашборд всех мониторов инвариантов (F5 шаг 7): у каждого пейджа — ссылка на панель и runbook.
INVARIANTS_DASHBOARD = "/d/invariant-monitors"
WINDOWS = ("5m", "30m", "1h", "6h", "3d")
TEST_INTERVAL = "1m"


@dataclass(frozen=True, slots=True)
class Burn:
    """One burn-rate alert: both windows above `factor` times the error budget for `wait`.

    `pace` tells the operator, in Russian, how fast the budget goes.
    """

    suffix: str
    long: str
    short: str
    factor: float
    wait: str
    always_ticket: bool
    pace: str


# Окна и множители — из книги Google SRE (multiwindow, multi-burn-rate alerts): быстрый
# расход съедает 2% месячного запаса на сбои за час, медленный — 5% за 6 часов, тикет — 10% за
# 3 дня. Оператору — без терминов: когда при таком темпе обещание будет нарушено.
BURNS = (
    Burn(
        "BudgetBurnFast", "1h", "5m", 14.4, "2m", always_ticket=False,
        pace="Сбоев сейчас очень много: если так продолжится, обещание на этот месяц будет "
        "нарушено примерно через 2 дня",
    ),
    Burn(
        "BudgetBurnSlow", "6h", "30m", 6, "15m", always_ticket=False,
        pace="Сбоев больше нормы уже несколько часов: если так продолжится, обещание на этот "
        "месяц будет нарушено примерно через 5 дней",
    ),
    Burn(
        "BudgetBurnTicket", "3d", "6h", 1, "1h", always_ticket=True,
        pace="Сбоев понемногу больше нормы уже три дня: если ничего не делать, обещание будет "
        "нарушено до конца месяца",
    ),
)  # fmt: skip


@dataclass(frozen=True, slots=True)
class OwnerRules:
    """What one owner declares."""

    objectives: Sequence[ServiceLevelObjective] = ()
    monitors: Sequence[InvariantMonitor] = ()


def camel(name: str) -> str:
    """`sign_in_latency_eu` → `SignInLatencyEu`, the style of alert names."""
    return "".join(part.capitalize() for part in name.split("_"))


def recorded(slo: ServiceLevelObjective, window: str) -> str:
    """The recorded series of an SLO's share of bad events over a window."""
    return f"slo:{slo.name}:bad_ratio:rate{window}"


def slo_labels(slo: ServiceLevelObjective) -> dict[str, str]:
    return {"slo": slo.name, "journey": slo.journey}


def series_of(name: str, labels: Mapping[str, str]) -> str:
    """A series in promtool's notation: `name{label="value",…}`."""
    return name + "{" + ",".join(f'{key}="{value}"' for key, value in labels.items()) + "}"


def burn_alert(slo: ServiceLevelObjective, burn: Burn) -> dict[str, object]:
    limit = f"{burn.factor * slo.error_budget:.6g}"
    severity = AlertClass.TICKET if burn.always_ticket else slo.alerting
    return {
        "alert": camel(slo.name) + burn.suffix,
        "expr": f"{recorded(slo, burn.long)} > {limit} and {recorded(slo, burn.short)} > {limit}",
        "for": burn.wait,
        "labels": {"severity": severity.value, **slo_labels(slo)},
        "annotations": burn_annotations(slo, burn),
    }


def burn_annotations(slo: ServiceLevelObjective, burn: Burn) -> dict[str, str]:
    """`summary` — what people experience; `description` — the promise and how soon it breaks."""
    return {
        "summary": slo.summary,
        "description": f"Мы обещаем, что {slo.promise}. {burn.pace}.",
        "runbook": f"{RUNBOOK}#slo-budget-burn",
        "dashboard": f"/d/journey-{slo.journey.replace('_', '-')}",
    }


def monitor_alert(monitor: InvariantMonitor) -> dict[str, object]:
    return {
        "alert": camel(monitor.name),
        "expr": monitor.condition.expression(),
        "labels": {"severity": AlertClass.PAGE.value, "invariant": monitor.invariant},
        "annotations": monitor_annotations(monitor),
    }


def monitor_annotations(monitor: InvariantMonitor) -> dict[str, str]:
    return {
        "summary": monitor.summary,
        "description": monitor.explanation,
        "runbook": f"{RUNBOOK}#{monitor.name.replace('_', '-')}",
        "dashboard": INVARIANTS_DASHBOARD,
    }


def recording_file(owner: str, rules: OwnerRules) -> dict[str, object]:
    return {
        "groups": [
            {
                "name": f"{owner}-slo-recording",
                "rules": [
                    {
                        "record": recorded(slo, window),
                        "expr": slo.indicator.bad_ratio(window),
                        "labels": slo_labels(slo),
                    }
                    for slo in rules.objectives
                    for window in WINDOWS
                ],
            }
        ]
    }


def alerts_file(owner: str, rules: OwnerRules) -> dict[str, object]:
    groups: list[dict[str, object]] = []
    if rules.objectives:
        burns = [burn_alert(slo, burn) for slo in rules.objectives for burn in BURNS]
        groups.append({"name": f"{owner}-slo", "rules": burns})
    if rules.monitors:
        monitors = [monitor_alert(monitor) for monitor in rules.monitors]
        groups.append({"name": f"{owner}-invariants", "rules": monitors})
    return {"groups": groups}


def slo_test(slo: ServiceLevelObjective) -> dict[str, object]:
    """All bad from 10 min to 90 min: every burn alert fires by 80 min, none is left at 150."""
    series = [
        {"series": series_of(recorded(slo, window), slo_labels(slo)), "values": "0x10 1x80 0x60"}
        for window in WINDOWS
    ]
    firing = [
        {
            "eval_time": "80m",
            "alertname": camel(slo.name) + burn.suffix,
            "exp_alerts": [
                {
                    "exp_labels": burn_alert(slo, burn)["labels"],
                    "exp_annotations": burn_annotations(slo, burn),
                }
            ],
        }
        for burn in BURNS
    ]
    resolved = [
        {"eval_time": "150m", "alertname": camel(slo.name) + burn.suffix, "exp_alerts": []}
        for burn in BURNS
    ]
    return {"interval": TEST_INTERVAL, "input_series": series, "alert_rule_test": firing + resolved}


def monitor_test(monitor: InvariantMonitor) -> dict[str, object]:
    """Broken from 10 min on, then healthy again: firing at 15 min, resolved by 45 min."""
    condition = monitor.condition
    if isinstance(condition, NeverIncreases):
        values = "0x10 1x50"
    else:
        values = f"0x10 {condition.limit + 1:g}x10 0x40"
    labels = monitor_alert(monitor)["labels"]
    return {
        "interval": TEST_INTERVAL,
        "input_series": [{"series": condition.metric, "values": values}],
        "alert_rule_test": [
            {
                "eval_time": "15m",
                "alertname": camel(monitor.name),
                "exp_alerts": [
                    {"exp_labels": labels, "exp_annotations": monitor_annotations(monitor)}
                ],
            },
            {"eval_time": "45m", "alertname": camel(monitor.name), "exp_alerts": []},
        ],
    }


def tests_file(owner: str, rules: OwnerRules) -> dict[str, object]:
    tests = [slo_test(slo) for slo in rules.objectives]
    tests += [monitor_test(monitor) for monitor in rules.monitors]
    return {
        "rule_files": [f"{owner}.alerts.json"],
        "evaluation_interval": TEST_INTERVAL,
        "tests": tests,
    }


def render(owners: Mapping[str, OwnerRules]) -> dict[str, str]:
    """File name → JSON text of every rule and test file; owners without rules have none."""
    files: dict[str, object] = {}
    for owner, rules in sorted(owners.items()):
        if rules.objectives:
            files[f"{owner}.recording.json"] = recording_file(owner, rules)
        if rules.objectives or rules.monitors:
            files[f"{owner}.alerts.json"] = alerts_file(owner, rules)
            files[f"{owner}.alerts.test.json"] = tests_file(owner, rules)
    return {
        name: json.dumps(content, indent=2, ensure_ascii=False) + "\n"
        for name, content in files.items()
    }
