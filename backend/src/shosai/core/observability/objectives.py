"""Service level objectives and invariant monitors, declared next to the metrics they read.

Target architecture §16.3 and §16.4: pages come from error-budget burn of a journey's SLO
and from invariant monitors that must stay at zero; everything else is a ticket. A slice
lists its declarations on its `FeatureModule`, core lists its own in composition, and
`rule_files` renders them into Prometheus rules with their promtool tests. A test keeps the
rendered files in step with the declarations, another that every metric named here is one
some role exports (F5 plan §3.8).

An indicator reads counters, never a gauge of the last value: a burn over an hour is the
share of bad events among all events of that hour.
"""

import re
from dataclasses import dataclass
from enum import StrEnum

NAME = re.compile(r"[a-z][a-z0-9_]*")
WINDOW = re.compile(r"[1-9][0-9]*[mhd]")
# Метрика — имя сэмпла Prometheus, без селектора: селектор пишет индикатор.
METRIC = re.compile(r"[a-z_][a-z0-9_]*")
# Линий на графике дашборда не больше четырёх (палитра графиков, deploy/observability/README.md).
MAX_TRACKED_SERIES = 4


class AlertClass(StrEnum):
    """How an alert reaches the operator (§16.6, F5-D4): a page rings, a ticket is silent."""

    PAGE = "page"
    TICKET = "ticket"


@dataclass(frozen=True, slots=True)
class EventRatio:
    """Bad events among all events, from two counter selectors (no range, no function)."""

    total: str
    bad: str

    def bad_ratio(self, window: str) -> str:
        """The share of bad events over `window`, as PromQL.

        No bad event yet means no bad series at all: the numerator falls back to zero, so a
        healthy journey records 0 instead of nothing; no event at all still records nothing.
        """
        bad = f"(sum(rate({self.bad}[{window}])) or vector(0))"
        return f"{bad} / sum(rate({self.total}[{window}]))"


@dataclass(frozen=True, slots=True)
class LatencyRatio:
    """Events slower than a bucket boundary among all events of a classic histogram."""

    histogram: str
    matchers: str
    threshold: str

    def __post_init__(self) -> None:
        if not (METRIC.fullmatch(self.histogram) is not None):
            raise ValueError(f"гистограмма {self.histogram!r}")
        float(self.threshold)

    def bad_ratio(self, window: str) -> str:
        """The share of events slower than the threshold over `window`, as PromQL."""
        total = f"sum(rate({self.histogram}_count{{{self.matchers}}}[{window}]))"
        good = (
            f'sum(rate({self.histogram}_bucket{{{self.matchers},le="{self.threshold}"}}[{window}]))'
        )
        return f"1 - {good} / {total}"


type Indicator = EventRatio | LatencyRatio


@dataclass(frozen=True, slots=True)
class Journey:
    """A user journey of §16.3: `name` for labels and links, `title` for the owner, in Russian."""

    name: str
    title: str

    def __post_init__(self) -> None:
        if not (NAME.fullmatch(self.name) is not None):
            raise ValueError(f"путь {self.name!r} — snake_case")


@dataclass(frozen=True, slots=True)
class ServiceLevelObjective:
    """A journey's objective (§16.3): `target` of its events are good over 30 days.

    The owner reads the alert, so its texts are plain Russian without SRE terms: `summary` —
    what people experience, as a headline; `promise` — what Shosai promises them, a clause
    the message puts after its Russian "we promise that".
    """

    name: str
    journey: Journey
    summary: str
    promise: str
    target: float
    indicator: Indicator
    alerting: AlertClass = AlertClass.PAGE

    def __post_init__(self) -> None:
        if not (NAME.fullmatch(self.name) is not None):
            raise ValueError(f"имя SLO {self.name!r} — snake_case")
        if not (0.5 < self.target < 1):
            raise ValueError(f"цель {self.name}: {self.target} вне (0.5, 1)")

    @property
    def error_budget(self) -> float:
        """The share of events allowed to be bad."""
        return round(1 - self.target, 9)


@dataclass(frozen=True, slots=True)
class NeverIncreases:
    """A counter whose any increase breaks the invariant."""

    metric: str
    window: str = "15m"

    def __post_init__(self) -> None:
        if not (METRIC.fullmatch(self.metric) is not None):
            raise ValueError(f"счётчик {self.metric!r}")
        if not (WINDOW.fullmatch(self.window) is not None):
            raise ValueError(f"окно {self.window!r}")

    def expression(self) -> str:
        """PromQL that has a value exactly while the invariant is broken."""
        return f"sum(increase({self.metric}[{self.window}])) > 0"


@dataclass(frozen=True, slots=True)
class StaysAtMost:
    """A gauge that breaks the invariant above `limit`, whichever process reports it."""

    metric: str
    limit: float = 0

    def __post_init__(self) -> None:
        if not (METRIC.fullmatch(self.metric) is not None):
            raise ValueError(f"датчик {self.metric!r}")

    def expression(self) -> str:
        """PromQL that has a value exactly while the invariant is broken."""
        return f"max({self.metric}) > {self.limit:g}"


type Condition = NeverIncreases | StaysAtMost


@dataclass(frozen=True, slots=True)
class InvariantMonitor:
    """A monitor of §16.4: zero is the only healthy value, anything else pages.

    `invariant` names what it guards (`inv-8`, `§14 rule 9`) for the runbook; the owner reads
    `summary` — what broke, as a headline — and `explanation` — what it means and what it
    threatens — in plain Russian.
    """

    name: str
    invariant: str
    summary: str
    explanation: str
    condition: Condition

    def __post_init__(self) -> None:
        if not (NAME.fullmatch(self.name) is not None):
            raise ValueError(f"имя монитора {self.name!r} — snake_case")


@dataclass(frozen=True, slots=True)
class TrackedLatency:
    """A latency a journey's dashboard shows beside its promises, with no promise and no alert
    (§16.3: measured and reported, not paged): the time 95 % of events stay under, one line per
    series — a label for the owner, in Russian, and the histogram's matchers, empty for all."""

    journey: Journey
    title: str
    description: str
    histogram: str
    series: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        if not (METRIC.fullmatch(self.histogram) is not None):
            raise ValueError(f"гистограмма {self.histogram!r}")
        if not 1 <= len(self.series) <= MAX_TRACKED_SERIES:
            raise ValueError(f"«{self.title}»: серий {len(self.series)}, допустимо от 1 до 4")
