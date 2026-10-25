"""Ratings of Leo's answers in numbers (ADR 0068 AG-D13; agent step 11a): closed label sets, no
ids, no text.

`shosai_agent_ratings_total{rating, model, tier, channel, language}` counts a rating each time
it is given or changed, by what made the answer; `shosai_agent_rated_toolsets_total{rating,
toolset}` counts it once per toolset the run offered. The operator sees ratings only as these
counts and the rates they make — never a conversation or a person.
"""

from collections.abc import Collection
from dataclasses import dataclass

from prometheus_client import CollectorRegistry, Counter

from shosai.features.agent.domain.feedback import Rating

# Ход до записи модели (сбой до первого слова) — без модели и языка, но с оценкой.
UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class RatedTurn:
    """What made a rated answer, as labels."""

    model: str | None
    tier: str | None
    channel: str
    language: str | None
    toolsets: Collection[str]


class FeedbackMetrics:
    """The ratings' counters, in the process's registry."""

    def __init__(self, registry: CollectorRegistry) -> None:
        self._ratings = Counter(
            "shosai_agent_ratings",
            "Оценки ответов Leo по модели, классу, каналу и языку ответа",
            ("rating", "model", "tier", "channel", "language"),
            registry=registry,
        )
        self._toolsets = Counter(
            "shosai_agent_rated_toolsets",
            "Оценки ответов Leo по наборам инструментов хода",
            ("rating", "toolset"),
            registry=registry,
        )

    def rated(self, rating: Rating, turn: RatedTurn) -> None:
        """A rating given or changed."""
        self._ratings.labels(
            rating.value,
            turn.model or UNKNOWN,
            turn.tier or UNKNOWN,
            turn.channel,
            turn.language or UNKNOWN,
        ).inc()
        for toolset in sorted(set(turn.toolsets)):
            self._toolsets.labels(rating.value, toolset).inc()
