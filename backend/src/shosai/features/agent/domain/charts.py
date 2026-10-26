"""A chart Leo shows the operator: rows computed in code and how to draw them (AG-D10; step 16b).

The tool that read the numbers builds the chart from them — the model never writes one — as
a `chart` artifact whose `spec` holds the shape (bars or a line), the column of the x axis, the
series with their labels, and at most 100 rows of numbers. The cabinet draws it from the spec
alone. The admin panel is in Russian only, so the chart's title and labels are Russian. Fewer
than two rows make no chart: one bar, or an empty frame, says nothing the answer does not.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final, Literal

from pydantic import JsonValue

from shosai.core.agent_tools.sources import ArtifactKind, ArtifactRef
from shosai.features.agent.domain.digests import compact

MAX_ROWS: Final = 100
MIN_ROWS: Final = 2
SPEC_FIELD: Final = "spec"

type Shape = Literal["bar", "line"]


@dataclass(frozen=True, slots=True)
class Series:
    """One series of a chart: the row's column it reads, and its label."""

    key: str
    label: str


def chart(
    report_id: str,
    title: str,
    drawn: tuple[Shape, str, Sequence[Series]],
    rows: Sequence[Mapping[str, JsonValue]],
    *,
    stacked: bool = False,
) -> tuple[ArtifactRef, ...]:
    """The chart of a report — the shape, the x column, the series and the rows — as the
    result's artifacts, or none for fewer than two rows."""
    if len(rows) < MIN_ROWS:
        return ()
    shape, x, series = drawn
    spec: dict[str, JsonValue] = {
        "shape": shape, "x": x, "stacked": stacked,
        "series": [{"key": item.key, "label": item.label} for item in series],
        "rows": [dict(row) for row in rows[:MAX_ROWS]],
    }  # fmt: skip
    return (
        ArtifactRef(ArtifactKind.CHART, f"chart:{report_id}", title, {SPEC_FIELD: compact(spec)}),
    )
