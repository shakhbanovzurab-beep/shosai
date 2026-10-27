"""Which facts reach a turn, within their budget (Leo §7.2, §7.3, ADR 0071).

Recall ranks the person's nearest current facts by similarity times retention times
confidence,
keeps those above the similarity floor, and packs at most 12 facts and 600 tokens; a fact
that does not fit is skipped, not the end of the list. The profile core takes pinned facts
first, then preferences by retention, within its share of segment 4, and lists them by id so
the block's bytes stay the same while the facts do.
"""

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Final

from shosai.features.memory.domain.decay import retention
from shosai.features.memory.domain.facts import Fact, FactKind

# Та же оценка, что у сегментов контекста агента: байты UTF-8 на три, с запасом.
BYTES_PER_TOKEN: Final = 3
# Строка факта в контексте: маркер, вид и перевод строки.
LINE_TOKENS: Final = 4
RECALL_POOL: Final = 40
RECALL_FACTS: Final = 12
RECALL_TOKENS: Final = 600
PROFILE_TOKENS: Final = 400
# Ниже — явно не о том: на этом пороге все релевантные пары замера живы (план §1.4).
RECALL_FLOOR: Final = 0.55


def estimate_tokens(text: str) -> int:
    """A conservative token count of a text in any language."""
    return math.ceil(len(text.encode()) / BYTES_PER_TOKEN)


def fact_tokens(fact: Fact) -> int:
    """What a fact costs as one line of the context."""
    return estimate_tokens(fact.statement) + LINE_TOKENS


@dataclass(frozen=True, slots=True)
class Near:
    """A fact and its cosine similarity to the turn's question."""

    fact: Fact
    similarity: float


def rank(near: Iterable[Near], now: datetime, floor: float) -> list[Near]:
    """Current facts above the floor, the most useful first."""
    kept = [item for item in near if item.fact.current and item.similarity >= floor]
    return sorted(
        kept,
        key=lambda item: (
            -(item.similarity * retention(item.fact, now) * item.fact.confidence),
            str(item.fact.id),
        ),
    )


def pack(facts: Sequence[Fact], max_facts: int, max_tokens: int) -> tuple[Fact, ...]:
    """The facts in their order while the count and the tokens hold; one that does not fit
    is skipped and the next is tried."""
    chosen: list[Fact] = []
    spent = 0
    for fact in facts:
        if len(chosen) >= max_facts:
            break
        cost = fact_tokens(fact)
        if spent + cost <= max_tokens:
            chosen.append(fact)
            spent += cost
    return tuple(chosen)


def recalled(
    near: Iterable[Near], now: datetime, floor: float, max_tokens: int
) -> tuple[Fact, ...]:
    """The facts recall gives a turn."""
    ranked = [item.fact for item in rank(near, now, floor)]
    return pack(ranked, RECALL_FACTS, min(max_tokens, RECALL_TOKENS))


def profile(facts: Iterable[Fact], now: datetime, max_tokens: int) -> tuple[Fact, ...]:
    """The profile core's facts: pinned ones, then preferences by retention, by id."""
    current = [fact for fact in facts if fact.current]
    pinned = sorted((fact for fact in current if fact.pinned), key=lambda fact: str(fact.id))
    preferences = sorted(
        (fact for fact in current if not fact.pinned and fact.kind is FactKind.PREFERENCE),
        key=lambda fact: (-retention(fact, now), str(fact.id)),
    )
    budget = min(max_tokens, PROFILE_TOKENS)
    chosen = pack([*pinned, *preferences], len(pinned) + len(preferences), budget)
    return tuple(sorted(chosen, key=lambda fact: fact.id))
