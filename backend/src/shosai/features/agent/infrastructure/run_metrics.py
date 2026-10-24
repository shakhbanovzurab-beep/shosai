"""Leo's turns in numbers (agent plan §3.6, Leo §16): closed label sets, no ids, no text.

`shosai_agent_turns_total{channel, outcome}` counts runs by how they ended — the objective's
platform failures are `failed`, `process_lost` and `turn_deadline`. The platform's own time on
a turn — admission to the model's call, and the model's last word to the recorded end — is
`shosai_agent_platform_overhead_seconds{home}`, whose objective is 500 ms for 95 % of EU turns.
The person's wait for the first word is `shosai_agent_ttft_seconds{tier}`, the worker's
pickup of a sent turn `shosai_agent_queue_pickup_seconds`, the context's size by segment
`shosai_agent_context_tokens{segment}`, a turn's cost `shosai_agent_turn_cost_usd{tier}`. An
agent worker holds `shosai_agent_active_runs`; the API counts resumes by their outcome.
"""

from typing import Final

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

from shosai.core.kernel.homes import Home
from shosai.features.agent.domain.budgets import Segment
from shosai.features.agent.domain.runs import Channel

TURNS: Final = "shosai_agent_turns_total"
OVERHEAD: Final = "shosai_agent_platform_overhead_seconds"
# Границы корзин: 0.5 — цель накладных расходов платформы (§16.3), остальные — для панели.
OVERHEAD_BUCKETS: Final = (0.05, 0.1, 0.2, 0.3, 0.5, 0.75, 1, 2, 5)
FIRST_WORD_BUCKETS: Final = (0.25, 0.5, 1, 2, 3, 5, 8, 15, 30)
PICKUP_BUCKETS: Final = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 5)
TOKEN_BUCKETS: Final = (100, 250, 500, 1_000, 2_000, 4_000, 8_000)
COST_BUCKETS: Final = (0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05, 0.1, 0.5)
PLATFORM_FAILURES: Final = ("failed", "process_lost", "turn_deadline")


class RunMetrics:
    """The turns' counters and histograms, in the process's registry."""

    def __init__(self, registry: CollectorRegistry) -> None:
        self._turns = Counter(
            TURNS.removesuffix("_total"),
            "Ходы Leo по каналу и тому, как они закончились",
            ("channel", "outcome"),
            registry=registry,
        )
        self._overhead = Histogram(
            OVERHEAD,
            "Время платформы на ходе Leo без ответа модели: допуск, контекст, запись конца",
            ("home",),
            buckets=OVERHEAD_BUCKETS,
            registry=registry,
        )
        self._first_word = Histogram(
            "shosai_agent_ttft_seconds",
            "Время от вопроса до первого слова ответа Leo по уровню модели",
            ("tier",),
            buckets=FIRST_WORD_BUCKETS,
            registry=registry,
        )
        self._pickup = Histogram(
            "shosai_agent_queue_pickup_seconds",
            "Время от допуска хода до того, как его взял воркер ходов",
            buckets=PICKUP_BUCKETS,
            registry=registry,
        )
        self._tokens = Histogram(
            "shosai_agent_context_tokens",
            "Размер сегмента контекста хода Leo в оценочных токенах",
            ("segment",),
            buckets=TOKEN_BUCKETS,
            registry=registry,
        )
        self._cost = Histogram(
            "shosai_agent_turn_cost_usd",
            "Стоимость хода Leo в долларах по уровню модели",
            ("tier",),
            buckets=COST_BUCKETS,
            registry=registry,
        )
        self._active = Gauge(
            "shosai_agent_active_runs", "Ходы, которые ведёт этот воркер ходов", registry=registry
        )
        self._resumes = Counter(
            "shosai_agent_resumes",
            "Возобновления потока хода по исходу: отдан или журнал уже истёк",
            ("outcome",),
            registry=registry,
        )

    def ended(self, channel: Channel, outcome: str) -> None:
        """A turn ended with its code."""
        self._turns.labels(channel=channel.value, outcome=outcome).inc()

    def timed(self, home: Home, overhead: float, first_word: float | None, tier: str) -> None:
        """A turn's platform time and, when it had one, the wait for its first word."""
        self._overhead.labels(home=home.value).observe(overhead)
        if first_word is not None:
            self._first_word.labels(tier=tier).observe(first_word)

    def picked_up(self, seconds: float) -> None:
        """A worker took a sent turn after `seconds`."""
        self._pickup.observe(seconds)

    def context(self, sizes: dict[Segment, int]) -> None:
        """The context's segments of a turn, in estimated tokens."""
        for segment, tokens in sizes.items():
            self._tokens.labels(segment=segment.value).observe(tokens)

    def cost(self, tier: str, usd: float) -> None:
        """What a turn cost."""
        self._cost.labels(tier=tier).observe(usd)

    def active(self, runs: int) -> None:
        """How many runs this worker drives now."""
        self._active.set(runs)

    def resumed(self, outcome: str) -> None:
        """A stream was resumed (`served`) or its log was gone (`gone`)."""
        self._resumes.labels(outcome=outcome).inc()
