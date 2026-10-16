"""Grafana dashboards as JSON, built in code (target architecture §16.5, F5 plan step 7).

The owner reads them, so everything a person sees is plain Russian: titles, descriptions,
axis labels, legends, units. Series take four validated categorical colors in fixed order —
they pass the colour-blindness, lightness and contrast checks on Grafana's light and dark
surfaces — one query per series and at most four series per chart. A status tile says its
state in words with a sign (Russian "no ✓", "yes ✗"); its color only reinforces the words.

Hovering a chart lists every line's value at that moment, highest first, and the charts of a
dashboard share one crosshair. A promise is a dashed line over a faint red zone that the
axis always keeps in view, so the margin to it is visible at a glance. Each unit rounds to
the precision a person reads. Every dashboard links to the others.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

# Синий, оранжевый, бирюзовый, жёлтый: первые четыре слота проверенной палитры (навык dataviz,
# validate_palette.js: CVD ΔE ≥ 8,4, контраст ≥ 3:1 на #181b1f и #ffffff).
SERIES_COLORS = ("#3987e5", "#d95926", "#199e70", "#c98500")
GOOD = "#0ca30c"
CRITICAL = "#d03b3b"
PROMETHEUS = {"type": "prometheus", "uid": "prometheus"}
REF_IDS = "ABCD"
GRID_WIDTH = 24
# Ширина и высота панелей в клетках сетки Grafana (24 в строке, клетка ~30 px высотой).
CHART = (12, 9)
SHARE_TILE = (6, 9)
SMALL_TILE = (8, 5)
# Ось держит в виду и пунктир обещания, и запас над ним.
LIMIT_HEADROOM = 1.25
ROW_HEIGHT = 1
NO_DATA = "нет данных"
NEVER = 1e15
# Цвет без данных: фон панели. Пороги начинаются с -NEVER, поэтому ему достаётся только пустота.
UNKNOWN = "transparent"

type Panel = dict[str, Any]


@dataclass(frozen=True, slots=True)
class Unit:
    """How a value reads: Grafana's unit (a Russian suffix), the axis label, the decimals."""

    grafana: str
    axis: str
    decimals: int | None = None


# Без decimals Grafana сама подбирает точность под размах значений; целые величины — без дробей.
MILLISECONDS = Unit("suffix: мс", "миллисекунды", 0)
# Секунды — там, где на графике exemplars: их значения в секундах, как у гистограммы.
SECONDS = Unit("suffix: с", "секунды")
PER_MINUTE = Unit("suffix: в мин", "в минуту")
SHARE = Unit("percentunit", "доля")
MINUTES = Unit("suffix: мин", "минуты")
MEGABYTES = Unit("suffix: МБ", "мегабайты", 0)
DOLLARS_PER_HOUR = Unit("suffix: $ в час", "долларов в час", 2)
PIECES = Unit("suffix: шт.", "штук", 0)


@dataclass(frozen=True, slots=True)
class Series:
    """One line of a chart: its legend and its PromQL."""

    legend: str
    expr: str


@dataclass(frozen=True, slots=True)
class Chart:
    """A time series chart; `limit` draws the promise as a dashed line."""

    title: str
    description: str
    unit: Unit
    series: Sequence[Series]
    limit: float | None = None
    exemplars: bool = False
    width: int = CHART[0]
    height: int = CHART[1]

    def panel(self) -> Panel:
        """The chart as a Grafana panel."""
        return chart_panel(self)


def chart_panel(spec: Chart) -> Panel:
    """A Grafana time series panel for `spec`."""
    title, unit, series, limit = spec.title, spec.unit, spec.series, spec.limit
    if not 1 <= len(series) <= len(SERIES_COLORS):
        raise ValueError(f"«{title}»: серий {len(series)}, допустимо от 1 до 4")
    steps: list[dict[str, Any]] = [{"color": "transparent", "value": None}]
    if limit is not None:
        steps.append({"color": CRITICAL, "value": limit})
    return {
        "type": "timeseries",
        "gridPos": {"w": spec.width, "h": spec.height},
        "title": title,
        "description": spec.description,
        "datasource": PROMETHEUS,
        "targets": [
            {
                "refId": ref,
                "datasource": PROMETHEUS,
                "expr": line.expr,
                "legendFormat": line.legend,
                "range": True,
                "exemplar": spec.exemplars,
            }
            for ref, line in zip(REF_IDS, series, strict=False)
        ],
        "fieldConfig": {
            "defaults": {
                "unit": unit.grafana,
                "decimals": unit.decimals,
                "min": 0,
                "noValue": NO_DATA,
                "color": {"mode": "fixed", "fixedColor": SERIES_COLORS[0]},
                "thresholds": {"mode": "absolute", "steps": steps},
                "custom": {
                    "axisLabel": unit.axis,
                    "axisSoftMax": None if limit is None else limit * LIMIT_HEADROOM,
                    "axisBorderShow": False,
                    "lineWidth": 2,
                    # Прямые отрезки: сглаживание рисует значения, которых не было.
                    "lineInterpolation": "linear",
                    # Одна линия — с мягкой заливкой, несколько — без: заливки не перекрывают
                    # друг друга.
                    "fillOpacity": 18 if len(series) == 1 else 0,
                    "gradientMode": "opacity" if len(series) == 1 else "none",
                    "showPoints": "never",
                    "spanNulls": True,
                    "thresholdsStyle": {"mode": "dashed+area" if limit is not None else "off"},
                },
            },
            "overrides": [
                {
                    "matcher": {"id": "byFrameRefID", "options": ref},
                    "properties": [
                        {"id": "color", "value": {"mode": "fixed", "fixedColor": color}}
                    ],
                }
                for ref, color, _ in zip(REF_IDS, SERIES_COLORS, series, strict=False)
            ],
        },
        "options": {
            # Одну линию называет заголовок; у нескольких — легенда, цвет не единственный признак.
            "legend": {"showLegend": len(series) > 1, "displayMode": "list", "placement": "bottom"},
            "tooltip": {"mode": "multi", "sort": "desc"},
        },
    }


@dataclass(frozen=True, slots=True)
class Tile:
    """A single-number tile; `options` set its unit, thresholds and mappings.

    `trend` draws the value over the dashboard's range under the number. Without data the
    tile says so in words and takes no status color: no data is not a verdict.
    """

    title: str
    description: str
    expr: str
    options: dict[str, Any]
    size: tuple[int, int] = SMALL_TILE
    trend: bool = False

    @property
    def verdict(self) -> bool:
        """Whether the tile's color judges the value (thresholds) rather than names it."""
        return bool(self.options.get("color", {}).get("mode") == "thresholds")

    def panel(self) -> Panel:
        """The tile as a Grafana stat panel."""
        query: dict[str, Any] = {"refId": "A", "datasource": PROMETHEUS, "expr": self.expr}
        query |= {"range": True} if self.trend else {"instant": True}
        return {
            "type": "stat",
            "gridPos": {"w": self.size[0], "h": self.size[1]},
            "title": self.title,
            "description": self.description,
            "datasource": PROMETHEUS,
            "targets": [query],
            "fieldConfig": {"defaults": {"noValue": NO_DATA, **self.options}, "overrides": []},
            "options": {
                # Фон красит только вердикт по порогам; просто число окрашено, но не залито.
                "colorMode": "background" if self.verdict else "value",
                "graphMode": "area" if self.trend else "none",
                "textMode": "value",
                "justifyMode": "center",
                "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
            },
        }


def text_range(low: float, high: float, text: str) -> dict[str, Any]:
    """A value mapping: values from `low` to `high` read as `text`."""
    return {"type": "range", "options": {"from": low, "to": high, "result": {"text": text}}}


def status(
    title: str,
    description: str,
    expr: str,
    *,
    healthy_at_most: float = 0,
    size: tuple[int, int] = SMALL_TILE,
) -> Panel:
    """A green "no" tile while `expr` stays at or under `healthy_at_most`, a red "yes" above."""
    above = healthy_at_most + 1e-9
    return Tile(
        title,
        description,
        expr,
        {
            "color": {"mode": "thresholds"},
            "thresholds": {
                "mode": "absolute",
                "steps": [
                    {"color": UNKNOWN, "value": None},
                    {"color": GOOD, "value": -NEVER},
                    {"color": CRITICAL, "value": above},
                ],
            },
            "mappings": [
                text_range(-NEVER, healthy_at_most, "нет ✓"),
                text_range(above, NEVER, "да ✗"),
            ],
        },
        size,
    ).panel()


def share(title: str, description: str, expr: str, *, target: float) -> Panel:
    """A share in percent with its trend: green at or above `target`, red under it."""
    return Tile(
        title,
        description,
        expr,
        {
            "unit": "percentunit",
            "decimals": 2,
            "color": {"mode": "thresholds"},
            "thresholds": {
                "mode": "absolute",
                "steps": [
                    {"color": UNKNOWN, "value": None},
                    {"color": CRITICAL, "value": -NEVER},
                    {"color": GOOD, "value": target},
                ],
            },
        },
        SHARE_TILE,
        trend=True,
    ).panel()


def row(title: str) -> Panel:
    """A full-width heading; long titles fit where a tile's would be cut."""
    return {
        "type": "row",
        "gridPos": {"w": GRID_WIDTH, "h": ROW_HEIGHT},
        "title": title,
        "collapsed": False,
        "panels": [],
    }


def dashboard(uid: str, title: str, description: str, panels: Sequence[Panel]) -> dict[str, Any]:
    """A provisioned, read-only dashboard: panels flow left to right, rows start a new line."""
    placed: list[Panel] = []
    x = y = height = 0
    for number, panel in enumerate(panels, start=1):
        width, high = panel["gridPos"]["w"], panel["gridPos"]["h"]
        if panel["type"] == "row" or x + width > GRID_WIDTH:
            x, y, height = 0, y + height, 0
        placed.append({**panel, "id": number, "gridPos": {"x": x, "y": y, "w": width, "h": high}})
        x, height = x + width, max(height, high)
        if panel["type"] == "row":
            x, y, height = 0, y + high, 0
    return {
        "uid": uid,
        "title": title,
        "description": description,
        "tags": ["shosai"],
        "editable": False,
        # Общее перекрестие: наведение на один график показывает то же время на всех.
        "graphTooltip": 1,
        "links": [
            {
                "type": "dashboards",
                "tags": ["shosai"],
                "asDropdown": True,
                "title": "Другие панели",
                "includeVars": False,
                "keepTime": True,
            }
        ],
        "schemaVersion": 41,
        "time": {"from": "now-6h", "to": "now"},
        "refresh": "1m",
        "timezone": "browser",
        "panels": placed,
    }
