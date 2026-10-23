"""Which toolsets a turn offers the model, until `decisions` judges it (ADR 0068 AG-D7).

The schemas of the selected toolsets fill segment 2 of the context (4 000 tokens). A turn
always gets the core toolset, the toolsets of the page it was asked on, and those the
thread used in its last three turns; then, while they fit, every other toolset the person's
switches and plan allow, in a fixed order. The rest are named in `load_toolset`'s
description, so the model can still ask for one — at the cost of a round, which is why that
rate is watched. A toolset the person may not use is never offered, whatever asks for it.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Final

from shosai.features.agent.domain.budgets import SEGMENT_CAPS, Segment

CORE: Final = "core"
RULE: Final = "rules_v1"


@dataclass(frozen=True, slots=True)
class ToolsetFacts:
    """One toolset as routing sees it: its name, the size of its schemas and its gate."""

    name: str
    schema_tokens: int
    # Включено настройками человека, тарифом и правами; иначе не предлагается никогда.
    allowed: bool = True


@dataclass(frozen=True, slots=True)
class RouteFacts:
    """What a turn knows when it picks its toolsets."""

    # Наборы в постоянном порядке предпочтения; core среди них.
    toolsets: tuple[ToolsetFacts, ...]
    surface: frozenset[str] = field(default_factory=frozenset)
    sticky: frozenset[str] = field(default_factory=frozenset)
    cap: int = SEGMENT_CAPS[Segment.TOOLS]


@dataclass(frozen=True, slots=True)
class Route:
    """The toolsets sent with the turn, those only named, and the rule that chose them."""

    selected: tuple[str, ...]
    deferred: tuple[str, ...]
    rule: str = RULE


def route(facts: RouteFacts) -> Route:
    """Core, the page's and the sticky toolsets first, then others in order while they fit."""
    allowed = [toolset for toolset in facts.toolsets if toolset.allowed]
    wanted = {CORE} | facts.surface | facts.sticky
    selected = [toolset for toolset in allowed if toolset.name in wanted]
    room = facts.cap - sum(toolset.schema_tokens for toolset in selected)
    deferred: list[ToolsetFacts] = []
    for toolset in allowed:
        if toolset.name in wanted:
            continue
        if toolset.schema_tokens <= room:
            selected.append(toolset)
            room -= toolset.schema_tokens
        else:
            deferred.append(toolset)
    order = {toolset.name: position for position, toolset in enumerate(allowed)}
    return Route(
        selected=tuple(sorted((t.name for t in selected), key=order.__getitem__)),
        deferred=tuple(toolset.name for toolset in deferred),
    )


def sticky_toolsets(recent_turns: Sequence[frozenset[str]], turns: int = 3) -> frozenset[str]:
    """The toolsets the thread's last turns used, newest first in `recent_turns`."""
    used: frozenset[str] = frozenset()
    for toolsets in recent_turns[:turns]:
        used |= toolsets
    return used
