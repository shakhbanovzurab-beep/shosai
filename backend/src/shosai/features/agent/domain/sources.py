"""The numbered sources of one run (ADR 0068 AG-D1).

Tools return their sources as `SourceRef`s; the agent numbers each new one in the order the
results arrive, so the model can cite `[n]` and the cabinet can draw the marker. A number
never changes within a run: the same place in the same thing keeps its number however many
tools return it, and a new source is appended. The list is capped, so a run that reads a
great many things still sends a list the cabinet can show; references past the cap are not
numbered and the model is not offered them to cite.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Final

from shosai.core.agent_tools.sources import SourceKind, SourceRef

SOURCES_MAX: Final = 60


@dataclass(frozen=True, slots=True)
class NumberedSource:
    """A source with the number the answer cites it by, counting from one."""

    number: int
    ref: SourceRef


@dataclass(frozen=True, slots=True)
class SourceLedger:
    """The run's sources so far; adding returns a new ledger and the numbers given."""

    sources: tuple[SourceRef, ...] = ()

    def add(self, refs: Iterable[SourceRef]) -> tuple[SourceLedger, tuple[int | None, ...]]:
        """Number each reference: an earlier number for a known source, the next for a new one.

        A reference past the cap gets None.
        """
        sources = list(self.sources)
        known = {source.identity: position + 1 for position, source in enumerate(sources)}
        numbers: list[int | None] = []
        for ref in refs:
            number = known.get(ref.identity)
            if number is None and len(sources) < SOURCES_MAX:
                sources.append(ref)
                number = known[ref.identity] = len(sources)
            numbers.append(number)
        return SourceLedger(tuple(sources)), tuple(numbers)

    def numbered(self) -> tuple[NumberedSource, ...]:
        """Every source with its number, in order."""
        return tuple(
            NumberedSource(position + 1, source) for position, source in enumerate(self.sources)
        )

    def kinds(self) -> frozenset[SourceKind]:
        """What kinds of things the run read."""
        return frozenset(source.kind for source in self.sources)
