"""Reliability per band, as counts (decisions plan §3.5 "Online", ADR 0069 DL-D7).

A day's recorded decisions of a home, grouped with what followed them, become counts per
point, version, revision, shadow flag, band, language and source: how many decisions, and how
many of them were followed by the careful outcome's case — a declined card, a ranked toolset
the run called. The rule's and the fallback's rows are the baseline Jev's are compared with.
Nothing here holds an id or a text.
"""

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from shosai.features.decisions.domain.policy import Policy


@dataclass(frozen=True, slots=True)
class DecisionGroup:
    """Decisions of a day alike in everything counted, and what followed them."""

    point: str
    version: int
    revision: int | None
    shadow: bool
    outcome: str
    language: str
    source: str
    # Наблюдение потребителя; None — ничего не последовало или точке нечего наблюдать.
    observation: Mapping[str, object] | None
    count: int


@dataclass(frozen=True, slots=True)
class BandKey:
    """What a reliability count is kept by."""

    point: str
    version: int
    revision: int | None
    shadow: bool
    band: str
    language: str
    source: str


@dataclass(frozen=True, slots=True)
class Tally:
    """Decisions in a band, and those the careful outcome's case followed."""

    decisions: int = 0
    positives: int = 0

    def plus(self, decisions: int, positives: int) -> Tally:
        """The tally with more counted."""
        return Tally(self.decisions + decisions, self.positives + positives)


def tallied(
    groups: Iterable[DecisionGroup], policies: Mapping[str, Policy[Any, Any]]
) -> dict[BandKey, Tally]:
    """The counts per band; a version this image no longer has keeps its outcome as its band
    and counts no positives."""
    tallies: dict[BandKey, Tally] = defaultdict(Tally)
    for group in groups:
        policy = policies.get(f"{group.point}@{group.version}")
        band = policy.band(group.outcome) if policy is not None else group.outcome
        confirmed = policy is not None and policy.confirms(group.outcome, group.observation)
        key = BandKey(
            group.point, group.version, group.revision, group.shadow, band, group.language,
            group.source,
        )  # fmt: skip
        tallies[key] = tallies[key].plus(group.count, group.count if confirmed else 0)
    return dict(tallies)
