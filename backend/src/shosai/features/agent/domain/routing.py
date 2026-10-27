"""Which toolsets a turn offers the model, until `decisions` judges it (ADR 0068 AG-D7).

The schemas of the selected toolsets fill segment 2 of the context (4 000 tokens). A turn
always gets the core toolset, the toolsets of the page it was asked on, and those the thread
proposed writes to in its last three turns, whole, and the reads of those it read from; then,
while they fit, the reads of every other toolset the person's switches and plan allow, in a
fixed order, and after them the writes of the toolsets offered for reading. A thread that only read
keeps the same tools from turn to turn, so the provider's prefix cache holds. Reads come
first because most turns read and few write: a toolset offered for reading only, or not at
all, is named in `load_toolset`'s description, and loading it brings all its tools — at the
cost of a round, which is why that rate is watched. A toolset the person may not use is
never offered, whatever asks for it.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Final

from shosai.features.agent.domain.budgets import SEGMENT_CAPS, Segment

CORE: Final = "core"
RULE: Final = "rules_v2"


@dataclass(frozen=True, slots=True)
class ToolsetFacts:
    """One toolset as routing sees it: its name, the size of its schemas — all of them and
    its reads' — and its gate."""

    name: str
    schema_tokens: int
    # Включено настройками человека, тарифом и правами; иначе не предлагается никогда.
    allowed: bool = True
    # Доля чтения: набор может прийти без записей, когда целиком не помещается.
    read_tokens: int | None = None

    @property
    def reads(self) -> int:
        """The reads' share of the schemas."""
        return self.schema_tokens if self.read_tokens is None else self.read_tokens


@dataclass(frozen=True, slots=True)
class RouteFacts:
    """What a turn knows when it picks its toolsets."""

    # Наборы в постоянном порядке предпочтения; core среди них.
    toolsets: tuple[ToolsetFacts, ...]
    surface: frozenset[str] = field(default_factory=frozenset)
    # Наборы, в которые прошлые ходы треда предлагали запись: приходят целиком.
    sticky: frozenset[str] = field(default_factory=frozenset)
    # Наборы, из которых прошлые ходы читали: их чтение приходит всегда.
    recent: frozenset[str] = field(default_factory=frozenset)
    cap: int = SEGMENT_CAPS[Segment.TOOLS]


@dataclass(frozen=True, slots=True)
class Route:
    """The toolsets sent whole, those sent for reading only, those only named — the reading
    ones among them, since loading one brings its writes — and the rule that chose them."""

    selected: tuple[str, ...]
    deferred: tuple[str, ...]
    rule: str = RULE
    reading: tuple[str, ...] = ()


def route(facts: RouteFacts, ranked: Sequence[str] = ()) -> Route:
    """Core, the page's and the written-to toolsets whole, the read-from ones' reads; then
    others' reads, then their writes, while they fit — the `ranked` ones (those a judge found
    the turn needs, likeliest first) before the rest, which keep the fixed order. The route
    names them in the fixed order whatever filled the room, so the tools' order stays put."""
    allowed = [toolset for toolset in facts.toolsets if toolset.allowed]
    whole = {toolset.name for toolset in allowed if toolset.name in wanted(facts)}
    reading = [toolset.name for toolset in allowed if toolset.name in facts.recent - whole]
    room = facts.cap - used_room(allowed, whole, reading)
    filling = by_rank(allowed, ranked)
    room = fill_reads(filling, (whole, reading), room)
    add_writes(filling, (whole, reading), room)
    order = [toolset.name for toolset in allowed]
    return Route(
        selected=tuple(name for name in order if name in whole),
        deferred=tuple(name for name in order if name not in whole),
        reading=tuple(name for name in order if name in reading),
    )


def wanted(facts: RouteFacts) -> frozenset[str]:
    """The toolsets that come whole whatever their size."""
    return frozenset({CORE}) | facts.surface | facts.sticky


def candidates(facts: RouteFacts) -> tuple[str, ...]:
    """The allowed toolsets beyond the forced part — those that fill the room — in order."""
    forced = wanted(facts) | facts.recent
    return tuple(t.name for t in facts.toolsets if t.allowed and t.name not in forced)


def by_rank(allowed: Sequence[ToolsetFacts], ranked: Sequence[str]) -> list[ToolsetFacts]:
    """The ranked toolsets first, in their rank; the others after them in the fixed order."""
    rank = {name: place for place, name in enumerate(ranked)}
    return sorted(allowed, key=lambda toolset: rank.get(toolset.name, len(rank)))


def used_room(allowed: Sequence[ToolsetFacts], whole: set[str], reading: list[str]) -> int:
    """The tokens the whole toolsets and the forced reads take."""
    taken = 0
    for toolset in allowed:
        if toolset.name in whole:
            taken += toolset.schema_tokens
        elif toolset.name in reading:
            taken += toolset.reads
    return taken


def fill_reads(
    allowed: Sequence[ToolsetFacts], chosen: tuple[set[str], list[str]], room: int
) -> int:
    """Add the reads of the other toolsets in order while they fit; the room left."""
    whole, reading = chosen
    for toolset in allowed:
        free = toolset.name not in whole and toolset.name not in reading
        if free and toolset.reads <= room:
            reading.append(toolset.name)
            room -= toolset.reads
    return room


def add_writes(
    allowed: Sequence[ToolsetFacts], chosen: tuple[set[str], list[str]], room: int
) -> None:
    """Make reading toolsets whole while their writes fit; one without writes is whole."""
    whole, reading = chosen
    for toolset in allowed:
        writes = toolset.schema_tokens - toolset.reads
        if toolset.name in reading and (writes == 0 or writes <= room):
            reading.remove(toolset.name)
            whole.add(toolset.name)
            room -= writes


def sticky_toolsets(recent_turns: Sequence[frozenset[str]], turns: int = 3) -> frozenset[str]:
    """The toolsets the thread's last turns used, newest first in `recent_turns`."""
    used: frozenset[str] = frozenset()
    for toolsets in recent_turns[:turns]:
        used |= toolsets
    return used
