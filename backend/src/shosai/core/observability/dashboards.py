"""Dashboards rendered from the declarations: one per journey, one of every invariant monitor.

A journey's dashboard shows each of its objectives under a heading with its promise: whether
the promise holds over the last 3 days, the share of failures over the last hour and five
minutes against what the promise allows, the events per minute and, for a latency promise,
the time 95 % of events stay under, with exemplars that open a slow request's trace. The
monitors' dashboard has one tile per monitor. A slice's declarations bring its dashboards
with them; the uids are the ones the alerts link to.
"""

from collections.abc import Sequence

from shosai.core.observability.grafana import (
    CHART,
    PER_MINUTE,
    SECONDS,
    SHARE,
    Chart,
    Panel,
    Series,
    dashboard,
    row,
    share,
    status,
)
from shosai.core.observability.objectives import (
    EventRatio,
    InvariantMonitor,
    Journey,
    NeverIncreases,
    ServiceLevelObjective,
)
from shosai.core.observability.rule_files import INVARIANTS_DASHBOARD, journey_uid, recorded

RATE_WINDOW = "5m"
# По две плитки в ряд: название правила — целое предложение и не должно обрезаться.
MONITOR_TILE = (12, 5)


def promise_panels(slo: ServiceLevelObjective) -> list[Panel]:
    """The heading and the panels of one objective.

    An availability promise fits one line: its tile, failures and events. A latency promise
    gives the line to its tile and a wide latency chart, where single slow requests show as
    points, and puts failures and events on the next line.
    """
    indicator = slo.indicator
    narrow = 9 if isinstance(indicator, EventRatio) else CHART[0]
    panels = [
        row(f"Мы обещаем, что {slo.promise}"),
        share(
            "Выполнено за 3 дня",
            "Какая доля событий за последние 3 дня уложилась в обещание: зелёная плитка — обещание "
            "выполняется, красная — нарушается.",
            f"1 - {recorded(slo, '3d')}",
            target=slo.target,
        ),
        Chart(
            "Доля сбоев",
            "Какая часть событий заканчивается плохо — за последний час и за последние 5 минут. "
            "Пунктир — сколько сбоев допускает обещание.",
            SHARE,
            [Series("за час", recorded(slo, "1h")), Series("за 5 минут", recorded(slo, "5m"))],
            limit=slo.error_budget,
            width=narrow,
        ).panel(),
    ]
    if isinstance(indicator, EventRatio):
        total = f"sum(rate({indicator.total}[{RATE_WINDOW}])) * 60"
        bad = f"sum(rate({indicator.bad}[{RATE_WINDOW}])) * 60"
        events = [Series("всего", total), Series("со сбоем", bad)]
    else:
        count = f"{indicator.histogram}_count{{{indicator.matchers}}}"
        events = [Series("всего", f"sum(rate({count}[{RATE_WINDOW}])) * 60")]
        buckets = f"{indicator.histogram}_bucket{{{indicator.matchers}}}"
        panels.insert(
            2,
            Chart(
                "Время ответа: 95 % быстрее этой линии",
                "Пунктир — обещанное время. Точки — отдельные медленные или неудачные запросы: "
                "щелчок открывает их путь через систему и их журнал.",
                SECONDS,
                [
                    Series(
                        "95 % быстрее",
                        f"histogram_quantile(0.95, sum by (le) (rate({buckets}[{RATE_WINDOW}])))",
                    )
                ],
                limit=float(indicator.threshold),
                exemplars=True,
                width=18,
            ).panel(),
        )
    panels.append(
        Chart(
            "Событий в минуту",
            "Сколько раз люди проходили этот путь.",
            PER_MINUTE,
            events,
            width=narrow,
        ).panel()
    )
    return panels


def journey_dashboards(objectives: Sequence[ServiceLevelObjective]) -> dict[str, dict[str, object]]:
    """Dashboard uid → dashboard, one per journey of the objectives."""
    journeys: dict[str, tuple[Journey, list[ServiceLevelObjective]]] = {}
    for slo in objectives:
        journeys.setdefault(slo.journey.name, (slo.journey, []))[1].append(slo)
    return {
        journey_uid(journey): dashboard(
            journey_uid(journey),
            journey.title,
            f"Что Shosai обещает на пути «{journey.title}» и как это выполняется.",
            [panel for slo in members for panel in promise_panels(slo)],
        )
        for journey, members in journeys.values()
    }


def monitor_tile(monitor: InvariantMonitor) -> Panel:
    """A tile that reads a green "no" while the monitor's invariant holds."""
    condition = monitor.condition
    if isinstance(condition, NeverIncreases):
        expr = f"sum(increase({condition.metric}[{condition.window}])) or vector(0)"
        return status(monitor.summary, monitor.explanation, expr, size=MONITOR_TILE)
    expr = f"max({condition.metric}) or vector(0)"
    return status(
        monitor.summary,
        monitor.explanation,
        expr,
        healthy_at_most=condition.limit,
        size=MONITOR_TILE,
    )


def invariants_dashboard(monitors: Sequence[InvariantMonitor]) -> dict[str, object]:
    """One tile per invariant monitor; the uid the monitors' pages link to."""
    uid = INVARIANTS_DASHBOARD.removeprefix("/d/")
    return dashboard(
        uid,
        "Правила, которые не должны нарушаться",
        "Каждая плитка — правило, которое всегда должно выполняться. «Нет ✓» — всё в порядке; "
        "«да ✗» — нарушено, и уже пришло срочное сообщение.",
        [monitor_tile(monitor) for monitor in monitors],
    )
