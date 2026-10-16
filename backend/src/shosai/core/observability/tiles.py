"""Single-number tiles of the dashboards: a share against its promise, a status in words.

A status tile says its state in words with a sign (Russian "no ✓", "yes ✗"); its color
only reinforces them. A tile without data says so and takes no status color: no data is
not a verdict. Only a tile that judges its value is filled with color.
"""

from dataclasses import dataclass
from typing import Any

from shosai.core.observability.grafana import CRITICAL, GOOD, NO_DATA, PROMETHEUS, Panel

# Плитка обещания — в ряд с двумя графиками; плитки состояния — по три в строке.
SHARE_TILE = (6, 9)
SMALL_TILE = (8, 5)
NEVER = 1e15
# Цвет без данных: фон панели. Пороги начинаются с -NEVER, поэтому ему достаётся только пустота.
UNKNOWN = "transparent"


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
