"""Leo's actions in numbers (Leo §11.3; agent step 9a): closed label sets, no ids, no text.

`shosai_agent_actions_total{origin, outcome}` counts actions by how they ended — succeeded,
failed, rejected, expired and the rest of the state machine's ends; `shosai_agent_approval_seconds`
is how long the person took from the card to the approval. The objective on approved actions
(executed or failed with a code within 30 s) reads `shosai_agent_action_execution_seconds`,
from the approval to the action's end.
"""

from typing import Final

from prometheus_client import CollectorRegistry, Counter, Histogram

APPROVAL_BUCKETS: Final = (1, 5, 15, 30, 60, 120, 300, 900, 1800, 3600)
EXECUTION_BUCKETS: Final = (0.25, 0.5, 1, 2.5, 5, 10, 20, 30, 60, 120)


class ActionMetrics:
    """The actions' counters and times, in the process's registry."""

    def __init__(self, registry: CollectorRegistry) -> None:
        self._actions = Counter(
            "shosai_agent_actions",
            "Действия Leo по источнику и исходу",
            ("origin", "outcome"),
            registry=registry,
        )
        self._approval = Histogram(
            "shosai_agent_approval_seconds",
            "Время от карточки до одобрения человеком",
            buckets=APPROVAL_BUCKETS,
            registry=registry,
        )
        self._execution = Histogram(
            "shosai_agent_action_execution_seconds",
            "Время от одобрения до конца действия: исполнено, отказ или исход неизвестен",
            buckets=EXECUTION_BUCKETS,
            registry=registry,
        )

    def decided(self, origin: str, outcome: str) -> None:
        """An action ended with its outcome."""
        self._actions.labels(origin=origin, outcome=outcome).inc()

    def approved(self, seconds: float) -> None:
        """The person approved a card `seconds` after it was proposed."""
        self._approval.observe(max(seconds, 0.0))

    def executed(self, seconds: float) -> None:
        """An approved action ended `seconds` after its approval."""
        self._execution.observe(max(seconds, 0.0))
