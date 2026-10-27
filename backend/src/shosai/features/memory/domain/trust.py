"""How far Leo may trust a fact in a turn (Leo §7.4, ADR 0071 MM-D7).

A fact the person confirmed — an explicit request, Remember on a candidate, their own edit
or setting, a pin — is their own data: it is wrapped as data and raises nothing. A fact saved
without the person keeps its source's taint and marks the run at least external, as any text
a machine chose. A meeting's fact is wrapped as the meeting's speech; any other as memory.
"""

from typing import Final

from shosai.core.agent_tools.context import Taint
from shosai.core.agent_tools.provenance import Provenance
from shosai.features.memory.domain.facts import Fact, SourceKind

# Чужая речь встречи остаётся чужой и в памяти; остальное — данные самого человека.
LABELS: Final = {SourceKind.MEETING: Provenance.MEETING_SPEECH}


def label_of(source: SourceKind) -> Provenance:
    """The label a fact from this source is wrapped with."""
    return LABELS.get(source, Provenance.MEMORY)


def taint_of(fact: Fact) -> Taint:
    """What the fact raises a run's taint to."""
    if fact.confirmed:
        return Taint.NONE
    return max(Taint.EXTERNAL, fact.source_taint)
