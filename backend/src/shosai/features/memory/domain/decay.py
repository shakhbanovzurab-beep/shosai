"""How a fact fades (Leo §7.2, ADR 0030; the draft's half-lives and their lesson).

Retention halves every half-life since the person last confirmed the fact. The half-life is
the kind's, stretched by how often the person confirmed it and doubled for a fact they asked
Leo to remember; a pinned fact never fades. Recall never refreshes it: only the person does
(ADR 0071). Below the expiry level the daily upkeep lets the fact go.
"""

import math
from datetime import datetime, timedelta
from typing import Final

from shosai.features.memory.domain.facts import Fact, FactKind

HALF_LIVES: Final = {
    FactKind.FACT: timedelta(days=180),
    FactKind.RELATIONSHIP: timedelta(days=180),
    FactKind.GOAL: timedelta(days=30),
    FactKind.PREFERENCE: timedelta(days=365),
    FactKind.PROCEDURE: timedelta(days=365),
}
EXPIRY_RETENTION: Final = 0.15
EXPLICIT_STRETCH: Final = 2.0


def half_life(fact: Fact) -> timedelta:
    """The fact's half-life: its kind's, times 1 + log2(1 + confirmations), doubled when
    the person asked for it."""
    stretch = 1 + math.log2(1 + max(fact.confirmations, 0))
    if fact.explicit:
        stretch *= EXPLICIT_STRETCH
    return HALF_LIVES[fact.kind] * stretch


def retention(fact: Fact, now: datetime) -> float:
    """How much of the fact is left, from 1 at its last confirmation down towards 0."""
    if fact.pinned:
        return 1.0
    age = max(now - fact.last_confirmed_at, timedelta(0))
    return float(0.5 ** (age / half_life(fact)))


def faded(fact: Fact, now: datetime) -> bool:
    """Whether a current fact has faded below the level the upkeep lets go of."""
    return fact.current and retention(fact, now) < EXPIRY_RETENTION
