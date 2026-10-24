"""Leo's tool calls in numbers (Leo §11.3; agent step 6): closed label sets, no ids, no text.

`shosai_agent_tool_calls_total{toolset, effect, outcome}` counts calls by how they ended — `ok`
or the error code the model read; `shosai_agent_tool_seconds{toolset}` is how long a call took
in its slice, the bulkhead's wait included. `shosai_agent_load_toolset_total` counts the
toolsets the model had to load: each costs a round, so routing that leaves out what turns need
shows here, and a ticket fires when more than 5 % of turns load one (Leo §8.2).
"""

from typing import Final

from prometheus_client import CollectorRegistry, Counter, Histogram

LOAD_TOOLSET: Final = "shosai_agent_load_toolset_total"
TOOL_BUCKETS: Final = (0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 20)


class ToolMetrics:
    """The tool calls' counters and times, in the process's registry."""

    def __init__(self, registry: CollectorRegistry) -> None:
        self._calls = Counter(
            "shosai_agent_tool_calls",
            "Вызовы инструментов Leo по набору, действию и исходу",
            ("toolset", "effect", "outcome"),
            registry=registry,
        )
        self._seconds = Histogram(
            "shosai_agent_tool_seconds",
            "Время вызова инструмента Leo в его срезе, с ожиданием очереди вызовов",
            ("toolset",),
            buckets=TOOL_BUCKETS,
            registry=registry,
        )
        self._loads = Counter(
            LOAD_TOOLSET.removesuffix("_total"),
            "Наборы инструментов, которые модели пришлось загрузить сверх выбранных",
            registry=registry,
        )

    def called(self, toolset: str, effect: str, outcome: str, seconds: float) -> None:
        """A call ended with its outcome after `seconds`."""
        self._calls.labels(toolset=toolset, effect=effect, outcome=outcome).inc()
        self._seconds.labels(toolset=toolset).observe(seconds)

    def loaded(self) -> None:
        """The model loaded a toolset routing left out."""
        self._loads.inc()
