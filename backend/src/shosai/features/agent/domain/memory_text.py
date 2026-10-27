"""What Leo remembers, as the model reads it (Leo §7.3, §7.4, ADR 0071 MM-D7).

Facts are data under the wrapper: each label's facts in one wrapped block, one line each. A
fact the person confirmed is their own data and raises nothing; any other is handed back with
its label to raise the run's taint, as any wrapped text does. The profile core's block takes a
boundary keyed to its own text, so it stays byte-identical while the facts do.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol

from shosai.core.agent_tools.context import Taint
from shosai.core.agent_tools.provenance import Provenance
from shosai.features.agent.domain.wrapper import Label, wrap


class Remembered(Protocol):
    """A fact as memory hands it to a turn (`contracts.memory.RecalledFact`)."""

    @property
    def statement(self) -> str:
        """The fact's words."""
        ...

    @property
    def kind(self) -> str:
        """What the fact is about."""
        ...

    @property
    def label(self) -> Provenance:
        """The label the fact is wrapped with."""
        ...

    @property
    def taint(self) -> Taint:
        """What the fact raises the run's taint to."""
        ...


@dataclass(frozen=True, slots=True)
class MemoryBlock:
    """The wrapped facts and the pieces that raise the run's taint, with their labels."""

    text: str
    tainting: tuple[tuple[Provenance, str], ...]
    # Включена ли память: при выключенной вспоминание не начинается вовсе.
    on: bool = True


def lines_of(facts: Sequence[Remembered], line: str) -> str:
    """One line per fact in the registered form."""
    return "\n".join(line.format(kind=fact.kind, statement=fact.statement) for fact in facts)


def memory_block(
    facts: Sequence[Remembered], forms: tuple[str, str], token: Callable[[str], str]
) -> MemoryBlock:
    """The facts under their header, one wrapped block per label in a fixed order; `token`
    gives the boundary of a block from the block's own text."""
    header, line = forms
    if not facts:
        return MemoryBlock("", ())
    blocks: list[str] = []
    tainting: list[tuple[Provenance, str]] = []
    for label in sorted({fact.label for fact in facts}, key=lambda value: value.value):
        same = [fact for fact in facts if fact.label is label]
        body = lines_of(same, line)
        wrapped = wrap(body, Label.of(label), token(body))
        blocks.append(wrapped)
        foreign = [fact for fact in same if fact.taint >= Taint.EXTERNAL]
        if foreign:
            tainting.append((label, lines_of(foreign, line)))
    return MemoryBlock("\n".join((header, *blocks)), tuple(tainting))
